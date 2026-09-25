"""Tests for the config flow and the alert subentry flow."""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol
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
    SUBENTRY_NOTIFIER_GROUP,
)

from .conftest import SetupAlerts, alert_subentry, group_subentry, state_alert

def _suggested(schema: dict) -> dict[str, Any]:
    """Return the suggested values of a form's fields."""
    return {
        str(key): key.description["suggested_value"]
        for key in schema
        if key.description and "suggested_value" in key.description
    }


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


# The frontend always submits the notifications section, filled from its fields'
# defaults; an empty one gets those defaults here too.
FORM = {
    "name": "Back Door Open",
    "priority": "critical",
    "acknowledgeable": True,
    "user_dismissable": True,
    "notifications": {},
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
    assert result["menu_options"] == ["manual", "state", "template", "trigger", "event"]

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
            "notifications": {},
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
        "notifications": {},
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
            "notifications": {},
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
    schema = result["data_schema"].schema
    defaults = {
        str(key): key.default() for key in schema if key.default is not vol.UNDEFINED
    }
    assert defaults == {
        "no_data_grace": {"hours": 0, "minutes": 10, "seconds": 0},
        "startup_delay": {"hours": 0, "minutes": 0, "seconds": 0},
        "retry_timeout": {"hours": 0, "minutes": 5, "seconds": 0},
    }
    assert _suggested(schema) == {"default_reminder_schedule": "10, 20, 30, 60"}

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
        {
            **FORM,
            "notifications": {
                "message": "{{ name }} opened",
                "display_message": "Close it",
            },
        },
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
    suggested = _suggested(result["data_schema"].schema["notifications"].schema.schema)
    assert suggested["message"] == "{{ name }} opened"
    assert suggested["display_message"] == "Close it"


async def _start_group(
    hass: HomeAssistant, entry: MockConfigEntry, subentry_id: str | None = None
) -> dict[str, Any]:
    context: dict[str, Any] = {"source": SOURCE_USER}
    if subentry_id is not None:
        context = {"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id}
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_NOTIFIER_GROUP), context=context
    )


GROUP_FORM = {"name": "Phones", "loud": False, "persistent": False}


async def test_create_and_edit_group(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The notifier group flow saves members, and pre-fills them when editing."""
    hass.services.async_register("notify", "mobile_app_phone", lambda call: None)
    entry = await setup_alerts()
    result = await _start_group(hass, entry)
    assert result["type"] is FlowResultType.FORM
    actions = result["data_schema"].schema
    (action_key,) = [key for key in actions if str(key) == "actions"]
    options = actions[action_key].config["fields"]["action"]["selector"]
    assert options.config["options"] == ["notify.mobile_app_phone"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **GROUP_FORM,
            "name": " Phones ",
            "entities": ["notify.kitchen"],
            "actions": [
                {"action": "mobile_app_phone", "data": {"channel": "alarm"}},
                {"action": "notify.telegram", "target": " 123 "},
            ],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.title == "Phones"
    assert dict(subentry.data) == {
        "loud": False,
        "entities": ["notify.kitchen"],
        "actions": [
            {"action": "notify.mobile_app_phone", "data": {"channel": "alarm"}},
            {"action": "notify.telegram", "target": "123"},
        ],
        "persistent": False,
    }

    result = await _start_group(hass, entry, subentry.subentry_id)
    assert result["step_id"] == "reconfigure"
    suggested = _suggested(result["data_schema"].schema)
    assert suggested["entities"] == ["notify.kitchen"]
    assert len(suggested["actions"]) == 2
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**GROUP_FORM, "loud": True, "persistent": True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert dict(entry.subentries[subentry.subentry_id].data) == {
        "loud": True,
        "entities": [],
        "actions": [],
        "persistent": True,
    }


@pytest.mark.parametrize(
    ("form", "error"),
    [
        ({}, "no_members"),
        ({"actions": [{"action": " "}]}, "action_missing"),
        ({"actions": [{"action": "phone", "data": ["x"]}]}, "invalid_data"),
    ],
)
async def test_group_errors(
    hass: HomeAssistant, setup_alerts: SetupAlerts, form: dict, error: str
) -> None:
    entry = await setup_alerts()
    result = await _start_group(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**GROUP_FORM, **form}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_group_name_unique_among_groups(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Group names are unique among groups; an alert may share one."""
    entry = await setup_alerts(
        alert_subentry("Phones"), group_subentry("Phones", persistent=True)
    )
    result = await _start_group(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**GROUP_FORM, "name": "phones", "persistent": True}
    )
    assert result["errors"] == {"name": "name_exists"}


async def test_alert_notification_settings_round_trip(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Turning the defaults off stores the alert's own (possibly empty) settings;
    leaving them on stores nothing."""
    entry = await setup_alerts(group_subentry("Phones", "phones", persistent=True))
    result = await _start(hass, entry, "manual")
    section_schema = result["data_schema"].schema["notifications"].schema.schema
    (groups_key,) = [key for key in section_schema if str(key) == "notifier_groups"]
    assert section_schema[groups_key].config["options"] == [
        {"value": "phones", "label": "Phones"}
    ]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "notifications": {
                "use_default_groups": False,
                "use_default_reminders": False,
                "reminder_schedule": "5, 15",
                "reminder_message": "Still {{ duration }}",
                "done_message": "Done",
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(
        s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_ALERT
    )
    assert subentry.data["notifier_groups"] == []
    assert subentry.data["reminder_schedule"] == [5, 15]
    assert subentry.data["reminder_message"] == "Still {{ duration }}"
    assert subentry.data["done_message"] == "Done"

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    section_schema = result["data_schema"].schema["notifications"].schema.schema
    defaults = {
        str(key): key.default()
        for key in section_schema
        if key.default is not vol.UNDEFINED
    }
    assert defaults == {"use_default_groups": False, "use_default_reminders": False}
    assert _suggested(section_schema)["reminder_schedule"] == "5, 15"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "notifications": {
                "use_default_groups": True,
                "use_default_reminders": True,
            },
        },
    )
    assert result["type"] is FlowResultType.ABORT
    subentry = entry.subentries[subentry.subentry_id]
    assert "notifier_groups" not in subentry.data
    assert "reminder_schedule" not in subentry.data


async def test_alert_invalid_schedule(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "notifications": {"use_default_reminders": False, "reminder_schedule": "0"},
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_schedule"}


async def test_options_notification_defaults(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(group_subentry("Phones", "phones", persistent=True))
    result = await hass.config_entries.options.async_init(entry.entry_id)
    form = {
        "no_data_grace": {"hours": 0, "minutes": 10, "seconds": 0},
        "startup_delay": {"hours": 0, "minutes": 0, "seconds": 0},
        "default_groups": ["phones"],
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**form, "default_reminder_schedule": "x"}
    )
    assert result["errors"] == {"base": "invalid_schedule"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**form, "default_reminder_schedule": ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["default_groups"] == ["phones"]
    assert entry.options["default_reminder_schedule"] == []
    assert entry.options["fallback_group"] is None
    assert entry.options["retry_timeout"] == {"hours": 0, "minutes": 5, "seconds": 0}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    (fallback_key,) = [
        key for key in result["data_schema"].schema if str(key) == "fallback_group"
    ]
    assert result["data_schema"].schema[fallback_key].config["multiple"] is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            **form,
            "fallback_group": "phones",
            "retry_timeout": {"hours": 0, "minutes": 2, "seconds": 0},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["fallback_group"] == "phones"


async def test_notifications_section_is_required_without_default(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The frontend builds a section's value from its fields only when the
    section has no default; with one, it showed empty and saving wiped it."""
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    (key,) = [k for k in result["data_schema"].schema if str(k) == "notifications"]
    assert isinstance(key, vol.Required)
    assert key.default is vol.UNDEFINED


EVENT_FORM = {
    "name": "Doorbell",
    "priority": "notice",
    "acknowledgeable": True,
    "notifications": {},
}


async def test_create_trigger_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A trigger alert is created from its form, and edited with it."""
    entry = await setup_alerts()
    result = await _start(hass, entry, "trigger")
    assert result["step_id"] == "trigger"

    triggers = [{"trigger": "state", "entity_id": "binary_sensor.bell", "to": "on"}]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **EVENT_FORM,
            "triggers": triggers,
            "condition": "{{ true }}",
            "duration": {"hours": 0, "minutes": 3, "seconds": 0},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    (subentry,) = entry.subentries.values()
    data = dict(subentry.data)
    assert data["kind"] == "trigger"
    assert data["condition"] == "{{ true }}"
    assert data["duration"] == {"hours": 0, "minutes": 3, "seconds": 0}
    assert len(data["triggers"]) == 1
    assert data["triggers"][0]["entity_id"] == "binary_sensor.bell"
    assert hass.states.get("alert_redux.doorbell").attributes["duration"] == 180

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    assert result["step_id"] == "reconfigure_trigger"
    assert _suggested(result["data_schema"].schema)["duration"] == data["duration"]


async def test_invalid_trigger(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    entry = await setup_alerts()
    result = await _start(hass, entry, "trigger")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**EVENT_FORM, "triggers": [{"trigger": "state", "entity_id": "x.y", "to": 5}]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_trigger"}


async def test_create_bus_event_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts()
    result = await _start(hass, entry, "event")
    assert result["step_id"] == "event"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**EVENT_FORM, "event_type": "  ", "event_data": {}},
    )
    assert result["errors"] == {"base": "event_type_missing"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**EVENT_FORM, "event_type": "doorbell_pressed", "event_data": ["x"]},
    )
    assert result["errors"] == {"base": "invalid_event_data"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**EVENT_FORM, "event_type": " doorbell_pressed ", "event_data": {}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert dict(subentry.data) == {
        "kind": "event",
        "priority": "notice",
        "acknowledgeable": True,
        "event_type": "doorbell_pressed",
    }


async def test_options_event_durations(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The per-priority durations are a section, pre-filled and saved."""
    entry = await setup_alerts()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"].schema
    (key,) = [key for key in schema if str(key) == "event_durations"]
    fields = {str(k): k.default() for k in schema[key].schema.schema}
    assert fields["emergency"] == {"hours": 1, "minutes": 0, "seconds": 0}
    assert fields["informational"] == {"hours": 0, "minutes": 5, "seconds": 0}

    durations = {**fields, "warning": {"hours": 0, "minutes": 20, "seconds": 0}}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "no_data_grace": {"hours": 0, "minutes": 10, "seconds": 0},
            "startup_delay": {"hours": 0, "minutes": 0, "seconds": 0},
            "event_durations": durations,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["event_durations"]["warning"] == {
        "hours": 0,
        "minutes": 20,
        "seconds": 0,
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"].schema
    (key,) = [key for key in schema if str(key) == "event_durations"]
    fields = {str(k): k.default() for k in schema[key].schema.schema}
    assert fields["warning"] == {"hours": 0, "minutes": 20, "seconds": 0}
