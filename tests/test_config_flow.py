"""Tests for the config flow and the alert subentry flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.alert_redux.const import (
    EVENT_CREATED,
    EVENT_DELETED,
    SUBENTRY_ALERT,
)

from .conftest import SetupAlerts, alert_subentry

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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

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

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT), context={"source": SOURCE_USER}
    )
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
        "alert_redux", "fire", {"entity_id": "alert_redux.back_door_open"}, blocking=True
    )

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "door"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

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
        "alert_redux", "fire", {"entity_id": "alert_redux.back_door_open"}, blocking=True
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
