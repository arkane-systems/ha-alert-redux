"""Tests for the config flow and the alert subentry flow."""

from __future__ import annotations

from datetime import timedelta
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
    SUBENTRY_GENERATOR,
    SUBENTRY_NOTIFIER_GROUP,
)

from .conftest import (
    SetupAlerts,
    alert_state_alert,
    alert_subentry,
    generator_subentry,
    group_subentry,
    state_alert,
)

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
    "supersession": {},
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
    assert result["menu_options"] == [
        "manual",
        "state",
        "on_off",
        "threshold",
        "template",
        "alert_state",
        "trigger",
        "event",
    ]

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
            "supersession": {},
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
        "supersession": {},
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
            "supersession": {},
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
        "generator_grace": {"hours": 0, "minutes": 5, "seconds": 0},
        "retry_timeout": {"hours": 0, "minutes": 5, "seconds": 0},
        "snooze_reminder_window": {"hours": 0, "minutes": 5, "seconds": 0},
        "button_snooze_duration": {"hours": 1, "minutes": 0, "seconds": 0},
    }
    assert _suggested(schema) == {"default_reminder_schedule": "10, 20, 30, 60"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "no_data_grace": {"hours": 0, "minutes": 1, "seconds": 0},
            "startup_delay": {"hours": 0, "minutes": 0, "seconds": 30},
            "generator_grace": {"hours": 0, "minutes": 10, "seconds": 0},
            "snooze_reminder_window": {"hours": 0, "minutes": 2, "seconds": 0},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("alert_redux.back_door_open").attributes[
        "no_data_grace"
    ] == 60
    assert entry.options["snooze_reminder_window"] == {
        "hours": 0,
        "minutes": 2,
        "seconds": 0,
    }
    assert hass.data["alert_redux"]["settings"].generator_grace == timedelta(
        minutes=10
    )


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
            "supersession": {},
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


async def test_buttons_saved_and_prefilled(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Notification buttons and the Snooze duration are saved, and pre-filled."""
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    close = [{"action": "cover.close_cover", "target": {"entity_id": "cover.garage"}}]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "supersession": {},
            "notifications": {
                "buttons": [
                    {"label": " Close door ", "action": close, "require_unlock": False},
                    {"label": "Unlock", "action": close, "require_unlock": True},
                ],
                "button_snooze_duration": {"hours": 0, "minutes": 30, "seconds": 0},
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    (subentry,) = entry.subentries.values()
    assert subentry.data["buttons"] == [
        {"label": "Close door", "action": close},
        {"label": "Unlock", "action": close, "require_unlock": True},
    ]
    assert subentry.data["button_snooze_duration"] == {
        "hours": 0,
        "minutes": 30,
        "seconds": 0,
    }

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    suggested = _suggested(result["data_schema"].schema["notifications"].schema.schema)
    assert suggested["buttons"] == subentry.data["buttons"]
    # A zero duration isn't kept: it means the default.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "supersession": {},
            "notifications": {
                "button_snooze_duration": {"hours": 0, "minutes": 0, "seconds": 0}
            },
        },
    )
    assert "button_snooze_duration" not in entry.subentries[subentry.subentry_id].data


@pytest.mark.parametrize(
    ("button", "error"),
    [
        ({"label": " ", "action": [{"action": "test.x"}]}, "button_incomplete"),
        ({"label": "Close", "action": []}, "button_incomplete"),
        ({"label": "Close", "action": [{"nonsense": 1}]}, "invalid_button_action"),
    ],
)
async def test_invalid_buttons(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    button: dict[str, Any],
    error: str,
) -> None:
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**FORM, "supersession": {}, "notifications": {"buttons": [button]}},
    )
    assert result["errors"] == {"base": error}


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


async def test_group_quiet_hours_settings(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A loud group's quiet-hours overrides are stored when they aren't the
    defaults, and pre-filled when editing (spec §9.9)."""
    entry = await setup_alerts()
    result = await _start_group(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **GROUP_FORM,
            "name": "Speaker",
            "loud": True,
            "quiet_entity": "input_boolean.bedroom",
            "quiet_threshold": "critical",
            "quiet_behaviour": "soften",
            "actions": [
                {"action": "notify.speaker", "quiet_data": {"volume": 0.2}},
            ],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.data["quiet_entity"] == "input_boolean.bedroom"
    assert subentry.data["quiet_threshold"] == "critical"
    assert subentry.data["quiet_behaviour"] == "soften"
    assert subentry.data["actions"] == [
        {"action": "notify.speaker", "quiet_data": {"volume": 0.2}}
    ]

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_NOTIFIER_GROUP),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    schema = result["data_schema"].schema
    defaults = {str(key): key.default() for key in schema if key.default is not vol.UNDEFINED}
    assert defaults["quiet_threshold"] == "critical"
    assert defaults["quiet_behaviour"] == "soften"
    assert _suggested(schema)["quiet_entity"] == "input_boolean.bedroom"

    # Back to the defaults: nothing is stored.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **GROUP_FORM,
            "name": "Speaker",
            "loud": True,
            "quiet_threshold": "default",
            "quiet_behaviour": "hold",
            "actions": [{"action": "notify.speaker"}],
        },
    )
    subentry = entry.subentries[subentry.subentry_id]
    for key in ("quiet_entity", "quiet_threshold", "quiet_behaviour"):
        assert key not in subentry.data


async def test_options_quiet_hours(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts()
    form = {
        "no_data_grace": {"hours": 0, "minutes": 10, "seconds": 0},
        "startup_delay": {"hours": 0, "minutes": 0, "seconds": 0},
    }
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], form)
    # Unsent, the section keeps the settings: no entity, Warning.
    assert entry.options["quiet_entity"] is None
    assert entry.options["quiet_threshold"] == "warning"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            **form,
            "quiet_hours": {
                "quiet_entity": "schedule.night",
                "quiet_threshold": "critical",
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["quiet_entity"] == "schedule.night"
    assert entry.options["quiet_threshold"] == "critical"


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
                {
                    "action": "notify.telegram",
                    "target": " 123 ",
                    "mobile": "no_buttons",
                    "keep_on_ack": True,
                    "clear_when_ended": False,
                },
            ],
            "persistent_clear_when_ended": True,
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
            # Only settings that differ from the defaults are kept.
            {
                "action": "notify.telegram",
                "target": "123",
                "mobile": "no_buttons",
                "keep_on_ack": True,
            },
        ],
        "persistent": False,
        "persistent_clear_on_ack": True,
        "persistent_clear_when_ended": True,
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
        "persistent_clear_on_ack": True,
        # Pre-filled from the stored group.
        "persistent_clear_when_ended": True,
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
            "supersession": {},
            "notifications": {
                "use_default_groups": False,
                "use_default_reminders": False,
                "reminder_schedule": "5, 15",
                "use_default_throttle": False,
                "throttle_count": 3,
                "throttle_minutes": 10,
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
    assert subentry.data["throttle"] == [3, 10]
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
    assert defaults == {
        "use_default_groups": False,
        "use_default_reminders": False,
        "use_default_throttle": False,
    }
    assert _suggested(section_schema)["reminder_schedule"] == "5, 15"
    assert _suggested(section_schema)["throttle_count"] == 3
    assert _suggested(section_schema)["throttle_minutes"] == 10

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "supersession": {},
            "notifications": {
                "use_default_groups": True,
                "use_default_reminders": True,
                "use_default_throttle": True,
            },
        },
    )
    assert result["type"] is FlowResultType.ABORT
    subentry = entry.subentries[subentry.subentry_id]
    assert "notifier_groups" not in subentry.data
    assert "reminder_schedule" not in subentry.data
    assert "throttle" not in subentry.data


@pytest.mark.parametrize(
    ("count", "minutes"),
    [(3, None), (None, 5), (2.5, 5), (3, 0)],
)
async def test_alert_invalid_throttle(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    count: float | None,
    minutes: float | None,
) -> None:
    """A throttle needs a whole count of at least one and positive minutes."""
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    notifications: dict[str, object] = {"use_default_throttle": False}
    if count is not None:
        notifications["throttle_count"] = count
    if minutes is not None:
        notifications["throttle_minutes"] = minutes
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**FORM, "supersession": {}, "notifications": notifications},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_throttle"}


async def test_alert_no_throttle(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An alert's own throttle left empty means it isn't throttled at all."""
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "supersession": {},
            "notifications": {"use_default_throttle": False},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(
        s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_ALERT
    )
    assert subentry.data["throttle"] == []


async def test_alert_invalid_schedule(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts()
    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "supersession": {},
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
    assert entry.options["default_throttle"] == []


async def test_options_default_throttle(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The default throttle is stored as [count, minutes], and pre-filled."""
    entry = await setup_alerts()
    form = {
        "no_data_grace": {"hours": 0, "minutes": 10, "seconds": 0},
        "startup_delay": {"hours": 0, "minutes": 0, "seconds": 0},
    }
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**form, "throttle_count": 3}
    )
    assert result["errors"] == {"base": "invalid_throttle"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**form, "throttle_count": 3, "throttle_minutes": 5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["default_throttle"] == [3, 5]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    suggested = _suggested(result["data_schema"].schema)
    assert suggested["throttle_count"] == 3
    assert suggested["throttle_minutes"] == 5


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
    "supersession": {},
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


CONDITION_FORM = {
    "name": "Server Room Hot",
    "priority": "critical",
    "acknowledgeable": True,
    "supersession": {},
    "notifications": {},
}


async def test_create_threshold_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set("sensor.server_room", "25")
    entry = await setup_alerts()
    result = await _start(hass, entry, "threshold")
    assert result["step_id"] == "threshold"

    for fields, error in (
        ({"maximum": "30"}, "value_source"),
        (
            {
                "entity_id": "sensor.server_room",
                "value_template": "{{ 1 }}",
                "maximum": "30",
            },
            "value_source",
        ),
        (
            {"attribute": "x", "value_template": "{{ 1 }}", "maximum": "30"},
            "value_source",
        ),
        ({"entity_id": "sensor.server_room"}, "limit_required"),
        (
            {"entity_id": "sensor.server_room", "minimum": "30", "maximum": "10"},
            "invalid_limits",
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**CONDITION_FORM, **fields}
        )
        assert result["errors"] == {"base": error}, fields

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **CONDITION_FORM,
            "entity_id": "sensor.server_room",
            "maximum": " {{ states('input_number.max') }} ",
            "hysteresis": 1.5,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert dict(subentry.data) == {
        "kind": "threshold",
        "priority": "critical",
        "acknowledgeable": True,
        "entity_id": "sensor.server_room",
        "maximum": "{{ states('input_number.max') }}",
        "hysteresis": 1.5,
    }

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    assert result["step_id"] == "reconfigure_threshold"
    assert _suggested(result["data_schema"].schema)["maximum"] == (
        "{{ states('input_number.max') }}"
    )


async def test_create_on_off_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts()
    result = await _start(hass, entry, "on_off")
    assert result["step_id"] == "on_off"
    triggers = [{"trigger": "event", "event_type": "garage_alarm"}]

    for fields, error in (
        ({"on_template": "{{ true }}"}, "criterion_required"),
        (
            {
                "on_triggers": triggers,
                "off_template": "{{ false }}",
                "delay_on": {"minutes": 1},
            },
            "delay_needs_template",
        ),
        (
            {
                "on_template": "{{ true }}",
                "off_triggers": triggers,
                "delay_off": {"minutes": 1},
            },
            "delay_needs_template",
        ),
        (
            {
                "on_triggers": [{"trigger": "state", "entity_id": "x.y", "to": 5}],
                "off_template": "{{ false }}",
            },
            "invalid_trigger",
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**CONDITION_FORM, **fields}
        )
        assert result["errors"] == {"base": error}, fields

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **CONDITION_FORM,
            "on_triggers": triggers,
            "off_template": "{{ false }}",
            "delay_off": {"minutes": 1},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    data = dict(subentry.data)
    assert data["kind"] == "on_off"
    assert data["off_template"] == "{{ false }}"
    assert data["on_triggers"][0]["event_type"] == "garage_alarm"
    assert "on_template" not in data


async def test_create_alert_state_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The alert state form watches another alert; it can't watch itself."""
    entry = await setup_alerts(alert_subentry("Back Door Open"))
    result = await _start(hass, entry, "alert_state")
    assert result["step_id"] == "alert_state"
    schema = result["data_schema"].schema
    (states_key,) = [key for key in schema if str(key) == "alert_states"]
    assert states_key.default() == ["active"]
    form = {
        "name": "Back Door Unacknowledged",
        "priority": "critical",
        "alert": "alert_redux.back_door_open",
        "alert_states": ["active"],
        "delay_on": {"hours": 0, "minutes": 30, "seconds": 0},
        "acknowledgeable": True,
        "supersession": {},
        "notifications": {},
    }
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**form, "alert_states": []}
    )
    assert result["errors"] == {"base": "alert_states_missing"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**form, "alert": "alert_redux.back_door_unacknowledged"}
    )
    assert result["errors"] == {"base": "alert_state_self"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], form
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentry = next(
        sub for sub in entry.subentries.values() if sub.title == form["name"]
    )
    assert dict(subentry.data) == {
        "kind": "alert_state",
        "priority": "critical",
        "acknowledgeable": True,
        "alert": "alert_redux.back_door_open",
        "alert_states": ["active"],
        "delay_on": {"hours": 0, "minutes": 30, "seconds": 0},
    }
    assert hass.states.get("alert_redux.back_door_unacknowledged").state == "idle"


async def test_reconfigure_alert_state_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Editing excludes the alert itself from its alert selectors."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_state_alert(
            "Back Door Unacknowledged", "alert_redux.back_door_open", ["active"], "u"
        ),
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "u"},
    )
    assert result["step_id"] == "reconfigure_alert_state"
    schema = result["data_schema"].schema
    (alert_key,) = [key for key in schema if str(key) == "alert"]
    assert alert_key.default() == "alert_redux.back_door_open"
    assert schema[alert_key].config["exclude_entities"] == [
        "alert_redux.back_door_unacknowledged"
    ]


async def test_supersession_section(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Supersedes is stored as relationships; self, repeats, and cycles are refused."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open", "open"),
        alert_subentry(
            "Back Door Left Open",
            "left",
            supersedes=[{"alert": "alert_redux.back_door_open"}],
        ),
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "left"},
    )
    section_schema = result["data_schema"].schema["supersession"].schema.schema
    assert _suggested(section_schema) == {
        "supersedes": [{"alert": "alert_redux.back_door_open"}]
    }

    form = {**FORM, "name": "Back Door Left Open"}
    # The selector leaves the alert itself out.
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                **form,
                "supersession": {
                    "supersedes": [{"alert": "alert_redux.back_door_left_open"}]
                },
            },
        )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **form,
            "supersession": {
                "supersedes": [{"alert": "alert_redux.back_door_open"}] * 2
            },
        },
    )
    assert result["errors"] == {"base": "supersedes_duplicate"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**form, "supersession": {"supersedes": []}}
    )
    assert result["type"] is FlowResultType.ABORT
    assert "supersedes" not in entry.subentries["left"].data

    # Left Open supersedes Open again, so Open can't supersede Left Open.
    hass.config_entries.async_update_subentry(
        entry,
        entry.subentries["left"],
        data={
            **entry.subentries["left"].data,
            "supersedes": [{"alert": "alert_redux.back_door_open"}],
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "open"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "supersession": {
                "supersedes": [{"alert": "alert_redux.back_door_left_open"}]
            },
        },
    )
    assert result["errors"] == {"base": "supersedes_cycle"}


async def test_options_supersession_section(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"].schema
    (key,) = [key for key in schema if str(key) == "supersession"]
    fields = {str(k): k.default() for k in schema[key].schema.schema}
    assert fields == {"supersession_debounce": 0.5, "done_window": 5.0}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "no_data_grace": {"hours": 0, "minutes": 10, "seconds": 0},
            "startup_delay": {"hours": 0, "minutes": 0, "seconds": 0},
            "supersession": {"supersession_debounce": 1, "done_window": 8},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["supersession_debounce"] == 1
    assert entry.options["done_window"] == 8


async def test_new_alert_cant_supersede_itself(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A new alert's own entity ID is the one its name will give it."""
    entry = await setup_alerts(alert_subentry("Back Door Open"))
    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "name": "Back Door Left Open",
            "supersession": {
                "supersedes": [{"alert": "alert_redux.back_door_left_open"}]
            },
        },
    )
    assert result["errors"] == {"base": "supersedes_self"}


async def test_supersession_propagation_fields(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Propagation is stored per relationship; none is left out (spec §8.2)."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open"), alert_subentry("Garage Door Open")
    )
    form = {**FORM, "name": "Doors Left Open"}

    async def submit(relationships: list[dict[str, Any]], **extra: Any):
        result = await _start(hass, entry, "manual")
        return await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {**form, **extra, "supersession": {"supersedes": relationships}},
        )

    snooze = {"alert": "alert_redux.back_door_open", "propagation": "snooze"}
    result = await submit([snooze])
    assert result["errors"] == {"base": "snooze_duration_missing"}
    result = await submit(
        [{**snooze, "snooze_duration": {"hours": 0, "minutes": 0, "seconds": 0}}]
    )
    assert result["errors"] == {"base": "snooze_duration_missing"}
    result = await submit(
        [{"alert": "alert_redux.back_door_open", "propagation": "acknowledge"}],
        acknowledgeable=False,
    )
    assert result["errors"] == {"base": "propagation_unacknowledgeable"}
    # With no propagation, an unacknowledgeable alert can supersede.
    result = await submit(
        [{"alert": "alert_redux.back_door_open", "propagation": "none"}],
        acknowledgeable=False,
        name="Doors Left Open Unacknowledgeable",
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await submit(
        [
            {**snooze, "snooze_duration": {"hours": 1, "minutes": 0, "seconds": 0}},
            {
                "alert": "alert_redux.garage_door_open",
                "propagation": "none",
                "snooze_duration": {"hours": 1, "minutes": 0, "seconds": 0},
            },
        ]
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(
        sub for sub in entry.subentries.values() if sub.title == "Doors Left Open"
    )
    assert subentry.data["supersedes"] == [
        {
            "alert": "alert_redux.back_door_open",
            "propagation": "snooze",
            "snooze_duration": {"hours": 1, "minutes": 0, "seconds": 0},
        },
        {"alert": "alert_redux.garage_door_open"},
    ]


# Generators (spec §12.3).


async def _start_generator(
    hass: HomeAssistant, entry: MockConfigEntry, kind: str
) -> dict[str, Any]:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_GENERATOR), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [
        "state",
        "on_off",
        "threshold",
        "template",
        "alert_state",
    ]
    return await _choose(hass, result, kind)


GENERATOR_FORM = {
    "name": "Unlocked",
    "priority": "warning",
    "acknowledgeable": True,
    "target_state": "unlocked",
    "targets": {"domains": ["lock", " "], "pattern": " lock.*_door "},
    "notifications": {},
    "supersession": {},
}


async def test_create_generator(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The generator flow stores the alert configuration and the targets."""
    hass.states.async_set("lock.front_door", "unlocked")
    entry = await setup_alerts()
    result = await _start_generator(hass, entry, "state")
    assert result["type"] is FlowResultType.FORM
    fields = {str(key) for key in result["data_schema"].schema}
    # The target is the kind's entity, and the subject.
    assert "entity_id" not in fields
    assert "subject_entity" not in fields
    assert {"name_template", "targets"} <= fields

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**GENERATOR_FORM, "name_template": "{{ target_name }} is unlocked"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = entry.subentries.values()
    assert subentry.subentry_type == SUBENTRY_GENERATOR
    assert subentry.title == "Unlocked"
    assert dict(subentry.data) == {
        "kind": "state",
        "priority": "warning",
        "acknowledgeable": True,
        "target_state": "unlocked",
        "name_template": "{{ target_name }} is unlocked",
        "targets": {"domains": ["lock"], "pattern": "lock.*_door"},
    }
    assert hass.states.get("alert_redux.front_door_unlocked").state == "active"


async def test_reconfigure_generator(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Editing a generator pre-fills its form and lists its current targets."""
    hass.states.async_set("lock.front_door", "unlocked")
    entry = await setup_alerts(
        generator_subentry(
            "Unlocked",
            subentry_id="gen",
            targets={"domains": ["lock"]},
            target_state="unlocked",
        )
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_GENERATOR),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "gen"},
    )
    assert result["step_id"] == "reconfigure_state"
    assert result["description_placeholders"] == {
        "targets": "lock.front_door",
        "referrers": "none",
    }
    targets = result["data_schema"].schema["targets"].schema.schema
    assert _suggested(targets) == {"domains": ["lock"]}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**GENERATOR_FORM, "target_state": "jammed"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries["gen"].data["target_state"] == "jammed"
    assert hass.states.get("alert_redux.front_door_unlocked").state == "idle"


@pytest.mark.parametrize(
    ("form", "errors"),
    [
        ({"targets": {}}, {"base": "targets_required"}),
        ({"targets": {"exclude": ["lock.a"]}}, {"base": "targets_required"}),
        ({"name": "Existing"}, {"name": "name_exists"}),
    ],
)
async def test_generator_errors(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    form: dict[str, Any],
    errors: dict[str, str],
) -> None:
    entry = await setup_alerts(
        generator_subentry("Existing", targets={"domains": ["lock"]}, target_state="x")
    )
    result = await _start_generator(hass, entry, "state")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**GENERATOR_FORM, **form}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_threshold_generator_value(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A threshold generator's value is the target's, so it needs only a limit,
    and can't have both an attribute and a value template."""
    entry = await setup_alerts()
    base = {
        "name": "Low",
        "priority": "warning",
        "acknowledgeable": True,
        "hysteresis": 0,
        "targets": {"device_classes": ["battery"]},
        "notifications": {},
        "supersession": {},
    }
    result = await _start_generator(hass, entry, "threshold")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], base
    )
    assert result["errors"] == {"base": "limit_required"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **base,
            "minimum": "20",
            "attribute": "level",
            "value_template": "{{ states(target) }}",
        },
    )
    assert result["errors"] == {"base": "value_source"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**base, "minimum": "20"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_generator_supersession(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A generator's relationships are to generators or fixed alerts, and are
    checked like an alert's (spec §12.3)."""
    entry = await setup_alerts(
        alert_subentry("Insecure", subentry_id="insecure"),
        generator_subentry(
            "Open", subentry_id="open", targets={"domains": ["lock"]}, target_state="x"
        ),
    )
    result = await _start_generator(hass, entry, "state")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **GENERATOR_FORM,
            "name": "Left Open",
            "supersession": {
                "supersedes": [
                    {"generator": "open", "propagation": "acknowledge"},
                    {"alert": "alert_redux.insecure"},
                ]
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (left,) = [s for s in entry.subentries.values() if s.title == "Left Open"]
    assert left.data["supersedes"] == [
        {"generator": "open", "propagation": "acknowledge"},
        {"alert": "alert_redux.insecure"},
    ]

    # Open can't supersede Left Open back: that's a cycle for every target.
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_GENERATOR),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "open"},
    )
    assert result["description_placeholders"]["referrers"] == "Left Open"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **GENERATOR_FORM,
            "name": "Open",
            "supersession": {"supersedes": [{"generator": left.subentry_id}]},
        },
    )
    assert result["errors"] == {"base": "supersedes_cycle"}


@pytest.mark.parametrize(
    ("supersedes", "error"),
    [
        (
            [{"generator": "open", "alert": "alert_redux.insecure"}],
            "relationship_target",
        ),
        ([{"propagation": "acknowledge"}], "relationship_target"),
        ([{"generator": "open"}, {"generator": "open"}], "supersedes_duplicate"),
        ([{"generator": "open", "propagation": "snooze"}], "snooze_duration_missing"),
    ],
)
async def test_generator_supersession_errors(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    supersedes: list[dict[str, Any]],
    error: str,
) -> None:
    entry = await setup_alerts(
        alert_subentry("Insecure", subentry_id="insecure"),
        generator_subentry(
            "Open", subentry_id="open", targets={"domains": ["lock"]}, target_state="x"
        ),
    )
    result = await _start_generator(hass, entry, "state")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**GENERATOR_FORM, "name": "Left", "supersession": {"supersedes": supersedes}},
    )
    assert result["errors"] == {"base": error}


async def test_fixed_alert_cycle_through_generator(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A fixed alert can't supersede a generated alert whose generator
    supersedes that fixed alert."""
    hass.states.async_set("lock.front_door", "x")
    entry = await setup_alerts(
        alert_subentry("Insecure", subentry_id="insecure"),
        generator_subentry(
            "Open",
            subentry_id="open",
            targets={"domains": ["lock"]},
            target_state="x",
            supersedes=[{"alert": "alert_redux.insecure"}],
        ),
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "insecure"},
    )
    assert result["description_placeholders"] == {"referrers": "Open"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "name": "Insecure",
            "supersession": {"supersedes": [{"alert": "alert_redux.front_door_open"}]},
        },
    )
    assert result["errors"] == {"base": "supersedes_cycle"}
