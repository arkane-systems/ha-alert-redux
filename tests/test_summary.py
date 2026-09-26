"""Tests for the summary sensors (spec §11.2)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import EVENT_STATE_CHANGED, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, label_registry as lr
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.alert_redux.const import DOMAIN, AlertState, Priority
from custom_components.alert_redux.summary import AlertReport, summarise

from .conftest import SetupAlerts, alert_subentry, state_alert

HIGHEST = "sensor.alert_redux_highest_priority"
UNACKED = "sensor.alert_redux_highest_unacked_priority"
FIRING = "sensor.alert_redux_firing"
ACTIVE = "sensor.alert_redux_active"
ACKNOWLEDGED = "sensor.alert_redux_acknowledged"
NO_DATA = "sensor.alert_redux_no_data"
DISABLED = "sensor.alert_redux_disabled"
SENSORS = (HIGHEST, UNACKED, FIRING, ACTIVE, ACKNOWLEDGED, NO_DATA, DISABLED)

LEAK = "alert_redux.leak"
DOOR = "alert_redux.back_door_open"
FRIDGE = "alert_redux.fridge_open"
SENSOR = "binary_sensor.back_door"


def _report(
    entity_id: str,
    state: AlertState,
    priority: Priority = Priority.WARNING,
    missing_data: bool = False,
) -> AlertReport:
    return AlertReport(entity_id, state, priority, missing_data)


def test_summarise_nothing() -> None:
    summary = summarise(())
    assert summary.highest_priority is None
    assert summary.highest_unacked_priority is None
    assert summary.firing == ()
    assert summary.firing_by_priority == dict.fromkeys(Priority, 0)


def test_summarise() -> None:
    summary = summarise(
        [
            _report("alert_redux.b", AlertState.ACTIVE, Priority.WARNING),
            _report("alert_redux.a", AlertState.ACTIVE, Priority.NOTICE),
            _report("alert_redux.c", AlertState.ACK, Priority.CRITICAL, True),
            _report("alert_redux.d", AlertState.NO_DATA, missing_data=True),
            _report("alert_redux.e", AlertState.DISABLED),
            _report("alert_redux.f", AlertState.IDLE),
        ]
    )
    assert summary.highest_priority is Priority.CRITICAL
    assert summary.highest_unacked_priority is Priority.WARNING
    assert summary.firing == ("alert_redux.a", "alert_redux.b", "alert_redux.c")
    assert summary.active == ("alert_redux.a", "alert_redux.b")
    assert summary.acknowledged == ("alert_redux.c",)
    # A firing alert in its grace period counts as no data too.
    assert summary.no_data == ("alert_redux.c", "alert_redux.d")
    assert summary.disabled == ("alert_redux.e",)
    assert summary.firing_by_priority[Priority.CRITICAL] == 1
    assert summary.firing_by_priority[Priority.WARNING] == 1
    assert summary.active_by_priority[Priority.CRITICAL] == 0
    assert summary.active_by_priority[Priority.NOTICE] == 1


async def _call(hass: HomeAssistant, service: str, entity_id: str, **data: Any) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": entity_id, **data}, blocking=True
    )
    await hass.async_block_till_done()


def _value(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_sensors_exist(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    await setup_alerts(alert_subentry("Leak"))
    registry = er.async_get(hass)
    for entity_id in SENSORS:
        entry = registry.async_get(entity_id)
        assert entry is not None, entity_id
        # No device, and not the alerts' label (spec §11.5).
        assert entry.device_id is None
        assert not entry.labels
    assert registry.async_get(DISABLED).entity_category is EntityCategory.DIAGNOSTIC
    assert registry.async_get(FIRING).entity_category is None
    assert _value(hass, HIGHEST) == "none"
    assert _value(hass, UNACKED) == "none"
    assert _value(hass, FIRING) == "0"
    assert hass.states.get(FIRING).attributes["entity_ids"] == []
    assert hass.states.get(FIRING).attributes["warning"] == 0
    assert hass.states.get(HIGHEST).attributes["options"] == [
        *Priority,
        "none",
    ]
    # The alerts label exists, and only the alert has it.
    label = next(
        label
        for label in lr.async_get(hass).async_list_labels()
        if label.name == "Alert Redux"
    )
    assert label.label_id in registry.async_get(LEAK).labels


async def test_sensors_follow_alerts(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user
) -> None:
    await setup_alerts(
        alert_subentry("Leak", priority="critical"),
        alert_subentry("Fridge Open", priority="notice"),
    )

    await _call(hass, "fire", LEAK)
    await _call(hass, "fire", FRIDGE)
    assert _value(hass, HIGHEST) == "critical"
    assert _value(hass, UNACKED) == "critical"
    assert _value(hass, FIRING) == "2"
    assert _value(hass, ACTIVE) == "2"
    firing = hass.states.get(FIRING).attributes
    assert firing["entity_ids"] == [FRIDGE, LEAK]
    assert firing["critical"] == 1
    assert firing["notice"] == 1

    await _call(hass, "ack", LEAK)
    assert _value(hass, HIGHEST) == "critical"
    assert _value(hass, UNACKED) == "notice"
    assert _value(hass, ACTIVE) == "1"
    assert hass.states.get(ACTIVE).attributes["critical"] == 0
    assert _value(hass, ACKNOWLEDGED) == "1"
    assert hass.states.get(ACKNOWLEDGED).attributes["entity_ids"] == [LEAK]

    await _call(hass, "snooze", FRIDGE, duration={"minutes": 30})
    assert _value(hass, UNACKED) == "none"
    assert _value(hass, ACKNOWLEDGED) == "2"

    await _call(hass, "dismiss", LEAK)
    assert _value(hass, HIGHEST) == "notice"
    assert _value(hass, FIRING) == "1"

    await _call(hass, "disable", LEAK)
    await _call(hass, "suspend", FRIDGE, duration={"hours": 1})
    assert _value(hass, DISABLED) == "2"
    assert hass.states.get(DISABLED).attributes["entity_ids"] == [FRIDGE, LEAK]
    assert _value(hass, FIRING) == "0"
    assert _value(hass, HIGHEST) == "none"


async def test_no_data_count(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Every alert missing data counts, firing in its grace period or not."""
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR, no_data_grace={"minutes": 2})
    )
    assert _value(hass, NO_DATA) == "0"
    hass.states.async_set(SENSOR, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "active"
    assert _value(hass, NO_DATA) == "1"
    assert _value(hass, FIRING) == "1"

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "no_data"
    assert _value(hass, NO_DATA) == "1"
    assert _value(hass, FIRING) == "0"
    assert hass.states.get(NO_DATA).attributes["entity_ids"] == [DOOR]

    hass.states.async_set(SENSOR, "off")
    await hass.async_block_till_done()
    assert _value(hass, NO_DATA) == "0"


async def test_priority_edit_and_deletion(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(alert_subentry("Leak", "leak", priority="notice"))
    await _call(hass, "fire", LEAK)
    assert _value(hass, HIGHEST) == "notice"

    subentry = entry.subentries["leak"]
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, "priority": "emergency"}
    )
    await hass.async_block_till_done()
    assert _value(hass, HIGHEST) == "emergency"
    assert hass.states.get(FIRING).attributes["emergency"] == 1

    hass.config_entries.async_remove_subentry(entry, "leak")
    await hass.async_block_till_done()
    assert _value(hass, HIGHEST) == "none"
    assert _value(hass, FIRING) == "0"


async def test_rename_follows(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    await setup_alerts(alert_subentry("Leak"))
    await _call(hass, "fire", LEAK)
    er.async_get(hass).async_update_entity(LEAK, new_entity_id="alert_redux.flood")
    await hass.async_block_till_done()
    assert hass.states.get(FIRING).attributes["entity_ids"] == ["alert_redux.flood"]
    assert _value(hass, FIRING) == "1"


async def test_one_write_per_burst(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Several alerts changing together update the sensors once."""
    hass.states.async_set(SENSOR, "off")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR),
        state_alert("Back Door Open Too", SENSOR),
        state_alert("Back Door Open Again", SENSOR),
    )
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set(SENSOR, "on")
    await hass.async_block_till_done()
    assert _value(hass, FIRING) == "3"
    firing_writes = [event for event in changes if event.data["entity_id"] == FIRING]
    assert len(firing_writes) == 1
