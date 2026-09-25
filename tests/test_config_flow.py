"""Tests for the config flow and the alert subentry flow."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.alert_redux.const import (
    EVENT_CREATED,
    EVENT_DELETED,
    SUBENTRY_ALERT,
)

from .conftest import SetupAlerts, alert_subentry, state_alert

async def _choose(
    hass: HomeAssistant, result: dict[str, Any], kind: str
) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": kind}
    )


async def _start(
    hass: HomeAssistant, entry: MockConfigEntry, kind: str
) -> dict[str, Any]:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT), context={"source": SOURCE_USER}
    )
    return await _choose(hass, result, kind)


FORM = {
    "name": "Back Door Open",
    "priority": "critical",
    "acknowledgeable": True,
    "user_dismissable": True,
}


async def test_create_alert(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The subentry flow creates a manual alert and its entity."""
    entry = await setup_alerts()
    created = async_capture_events(hass, EVENT_CREATED)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["manual", "state", "template"]

    result = await _choose(hass, result, "manual")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**FORM, "name": "  Back Door Open "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = entry.subentries.values()
    assert subentry.title == "Back Door Open"
    assert dict(subentry.data) == {
        "kind": "manual",
        "priority": "critical",
        "acknowledgeable": True,
        "user_dismissable": True,
    }

    state = hass.states.get("alert_redux.back_door_open")
    assert state is not None
    assert state.state == "idle"
    assert state.attributes["user_dismissable"] is True
    assert len(created) == 1
    assert created[0].data["entity_id"] == "alert_redux.back_door_open"
    assert created[0].data["old_state"] is None
    assert created[0].data["new_state"] == "idle"


async def test_duplicate_name(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Names must be unique among alerts, ignoring case."""
    entry = await setup_alerts(alert_subentry("Back Door Open"))

    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**FORM, "name": "back door open"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"name": "name_exists"}


async def test_reconfigure_keeps_state(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Editing an alert updates its config, keeping its entity ID and state."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open", subentry_id="door"),
        alert_subentry("Leak"),
    )
    await hass.services.async_call(
        "alert_redux",
        "fire",
        {"entity_id": "alert_redux.back_door_open"},
        blocking=True,
    )

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "door"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_manual"

    # Another alert's name is refused; its own name (in any case) isn't.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**FORM, "name": "Leak"}
    )
    assert result["errors"] == {"name": "name_exists"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**FORM, "name": "Rear Door Open", "icon": "mdi:door"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.subentries["door"].title == "Rear Door Open"
    state = hass.states.get("alert_redux.back_door_open")
    assert state.state == "active"
    assert state.name == "Rear Door Open"
    assert state.attributes["priority"] == "critical"
    assert state.attributes["icon"] == "mdi:door"
    assert state.attributes["fire_count"] == 1


async def test_remove_alert(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Removing a subentry removes the entity and announces the deletion."""
    entry = await setup_alerts(alert_subentry("Back Door Open", subentry_id="door"))
    deleted = async_capture_events(hass, EVENT_DELETED)
    await hass.services.async_call(
        "alert_redux",
        "fire",
        {"entity_id": "alert_redux.back_door_open"},
        blocking=True,
    )

    assert hass.config_entries.async_remove_subentry(entry, "door")
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get("alert_redux.back_door_open") is None
    assert len(deleted) == 1
    assert deleted[0].data == {
        "entity_id": "alert_redux.back_door_open",
        "name": "Back Door Open",
        "priority": "warning",
        "kind": "manual",
        "old_state": "active",
        "new_state": None,
        "user_id": None,
    }


async def test_create_state_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The state form creates a state alert; empty optional fields aren't stored."""
    hass.states.async_set("binary_sensor.back_door", "on")
    entry = await setup_alerts()
    result = await _start(hass, entry, "state")
    assert result["step_id"] == "state"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Back Door Open",
            "priority": "warning",
            "entity_id": "binary_sensor.back_door",
            "target_state": " on ",
            "delay_on": {"hours": 0, "minutes": 5, "seconds": 0},
            "condition": "",
            "acknowledgeable": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = entry.subentries.values()
    assert dict(subentry.data) == {
        "kind": "state",
        "priority": "warning",
        "acknowledgeable": True,
        "entity_id": "binary_sensor.back_door",
        "target_state": "on",
        "delay_on": {"hours": 0, "minutes": 5, "seconds": 0},
    }
    state = hass.states.get("alert_redux.back_door_open")
    assert state.state == "idle"
    assert state.attributes["delay_on_until"] is not None


async def test_create_template_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The template form creates a template alert."""
    entry = await setup_alerts()
    result = await _start(hass, entry, "template")
    assert result["step_id"] == "template"
    form = {
        "name": "Server Room Hot",
        "priority": "critical",
        "template": "{{ states('sensor.server_room') | float(0) > 30 }}",
        "condition": "{{ is_state('input_boolean.away', 'on') }}",
        "acknowledgeable": False,
        "subject_entity": "sensor.server_room",
        "no_data_grace": {"hours": 0, "minutes": 2, "seconds": 0},
    }

    # The template selector refuses templates that don't parse.
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**form, "template": "{{ 1 >"}
        )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], form
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    (subentry,) = entry.subentries.values()
    assert dict(subentry.data) == {
        "kind": "template",
        "priority": "critical",
        "acknowledgeable": False,
        "template": form["template"],
        "condition": form["condition"],
        "subject_entity": "sensor.server_room",
        "no_data_grace": {"hours": 0, "minutes": 2, "seconds": 0},
    }
    state = hass.states.get("alert_redux.server_room_hot")
    assert state.attributes["subject_entity"] == "sensor.server_room"
    assert state.attributes["no_data_grace"] == 120


async def test_reconfigure_state_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A state alert is edited with its own form, pre-filled, and in place."""
    hass.states.async_set("binary_sensor.back_door", "on")
    entry = await setup_alerts(
        state_alert(
            "Back Door Open",
            "binary_sensor.back_door",
            subentry_id="door",
            delay_off={"seconds": 30},
        )
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "door"},
    )
    assert result["step_id"] == "reconfigure_state"
    defaults = {
        str(key): key.default() if callable(key.default) else None
        for key in result["data_schema"].schema
    }
    assert defaults["entity_id"] == "binary_sensor.back_door"
    assert defaults["target_state"] == "on"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Back Door Open",
            "priority": "critical",
            "entity_id": "binary_sensor.back_door",
            "target_state": "on",
            "acknowledgeable": True,
        },
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert "delay_off" not in entry.subentries["door"].data
    state = hass.states.get("alert_redux.back_door_open")
    assert state.state == "active"
    assert state.attributes["priority"] == "critical"
    assert state.attributes["delay_off"] == 0


async def test_options_flow(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    hass.states.async_set("binary_sensor.back_door", "on")
    entry = await setup_alerts(
        state_alert("Back Door Open", "binary_sensor.back_door")
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults == {
        "no_data_grace": {"hours": 0, "minutes": 10, "seconds": 0},
        "startup_delay": {"hours": 0, "minutes": 0, "seconds": 0},
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "no_data_grace": {"hours": 0, "minutes": 1, "seconds": 0},
            "startup_delay": {"hours": 0, "minutes": 0, "seconds": 30},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("alert_redux.back_door_open").attributes[
        "no_data_grace"
    ] == 60


async def test_messages_saved_and_prefilled(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The on and card messages are saved, and pre-filled when editing."""
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**FORM, "message": "{{ name }} opened", "display_message": "Close it"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = entry.subentries.values()
    assert subentry.data["message"] == "{{ name }} opened"
    assert subentry.data["display_message"] == "Close it"

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested["message"] == "{{ name }} opened"
    assert suggested["display_message"] == "Close it"
