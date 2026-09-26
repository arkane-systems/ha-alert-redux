"""Tests for persisting alert state across restarts (spec §15.1)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import CoreState, HomeAssistant
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_CREATED,
    EVENT_DELETED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_NO_DATA,
    EVENT_UNACKED,
    STORAGE_KEY,
)

from .conftest import (
    SetupAlerts,
    alert_subentry,
    group_subentry,
    state_alert,
    trigger_alert,
)

DOOR = "alert_redux.back_door_open"


async def test_state_survives_reload(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """A fired and acknowledged alert comes back as it was, silently."""
    entry = await setup_alerts(alert_subentry("Back Door Open", subentry_id="door"))
    await hass.services.async_call(
        DOMAIN, "fire", {"entity_id": DOOR, "data": {"x": 1}}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": DOOR}, blocking=True)
    before = hass.states.get(DOOR)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # Unloading flushed the store.
    stored = hass_storage[STORAGE_KEY]["data"]["alerts"]["door"]
    assert stored["runtime"]["acked"] is True

    events = [
        async_capture_events(hass, event)
        for event in (EVENT_CREATED, EVENT_FIRED, EVENT_ACKED)
    ]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = hass.states.get(DOOR)
    assert after.state == "ack"
    for attribute in ("firing_since", "fire_count", "fire_data", "last_acked"):
        assert after.attributes[attribute] == before.attributes[attribute]
    assert all(not captured for captured in events)


async def test_cold_start_from_storage(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """Stored state is restored at startup; only new alerts are announced, and
    stored alerts with no subentry are announced as deleted."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            "alerts": {
                "door": {
                    "entity_id": DOOR,
                    "name": "Back Door Open",
                    "kind": "manual",
                    "priority": "warning",
                    "runtime": {
                        "firing": True,
                        "acked": False,
                        "firing_since": "2026-01-01T12:00:00+00:00",
                        "last_fired": "2026-01-01T12:00:00+00:00",
                        "fire_count": 3,
                    },
                },
                "gone": {
                    "entity_id": "alert_redux.gone",
                    "name": "Gone",
                    "kind": "manual",
                    "priority": "notice",
                    "runtime": {"firing": False},
                },
            }
        },
    }
    created = async_capture_events(hass, EVENT_CREATED)
    deleted = async_capture_events(hass, EVENT_DELETED)

    await setup_alerts(
        alert_subentry("Back Door Open", subentry_id="door"),
        alert_subentry("Leak", subentry_id="leak"),
    )

    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["fire_count"] == 3
    assert state.attributes["firing_since"].isoformat() == "2026-01-01T12:00:00+00:00"
    assert [event.data["entity_id"] for event in created] == ["alert_redux.leak"]
    assert [event.data["entity_id"] for event in deleted] == ["alert_redux.gone"]
    assert deleted[0].data["old_state"] == "idle"


# Condition alerts across restarts (spec §15.1, §15.3).

SENSOR = "binary_sensor.back_door"


async def _restart(hass: HomeAssistant, entry) -> None:
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_condition_alert_resumes_quietly(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Still firing after a restart: same firing, acknowledgement kept, no events."""
    hass.states.async_set(SENSOR, "on")
    entry = await setup_alerts(state_alert("Back Door Open", SENSOR))
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": DOOR}, blocking=True)
    firing_since = hass.states.get(DOOR).attributes["firing_since"]

    events = [
        async_capture_events(hass, event)
        for event in (EVENT_FIRED, EVENT_ENDED, EVENT_NO_DATA, EVENT_CREATED)
    ]
    await _restart(hass, entry)

    state = hass.states.get(DOOR)
    assert state.state == "ack"
    assert state.attributes["firing_since"] == firing_since
    assert state.attributes["no_data_since"] is None
    assert all(not captured for captured in events)


async def test_condition_alert_ends_after_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The condition cleared during the restart: it ends normally, after delay_off."""
    hass.states.async_set(SENSOR, "on")
    entry = await setup_alerts(
        state_alert("Back Door Open", SENSOR, delay_off={"seconds": 30})
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set(SENSOR, "off")
    ended = async_capture_events(hass, EVENT_ENDED)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(DOOR).state == "active"
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "idle"
    assert [event.data["reason"] for event in ended] == ["resolved"]


async def test_pending_delay_survives_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A delay_on under way isn't restarted from zero, even if the entity loads late."""
    hass.states.async_set(SENSOR, "on")
    entry = await setup_alerts(
        state_alert("Back Door Open", SENSOR, delay_on={"minutes": 10})
    )
    freezer.tick(timedelta(minutes=8))
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_remove(SENSOR)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "no_data"
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set(SENSOR, "on")
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "idle"

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "active"


async def test_startup_delay(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """While HA starts, the startup delay holds back the first evaluation."""
    hass.set_state(CoreState.starting)
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR),
        options={"startup_delay": {"seconds": 30}},
    )
    assert hass.states.get(DOOR).state == "no_data"
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "active"


async def test_no_startup_delay_once_running(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The startup delay doesn't apply when HA is already running."""
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR),
        options={"startup_delay": {"seconds": 30}},
    )
    assert hass.states.get(DOOR).state == "active"


# Event alerts across restarts (spec §15.1).

BELL = "binary_sensor.doorbell"
DOORBELL = "alert_redux.doorbell"
BELL_TRIGGERS = [{"trigger": "state", "entity_id": BELL, "to": "on"}]


async def test_event_alert_resumes(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A firing that hasn't run out resumes, and ends when it does."""
    hass.states.async_set(BELL, "off")
    entry = await setup_alerts(
        trigger_alert("Doorbell", BELL_TRIGGERS, duration={"minutes": 10})
    )
    hass.states.async_set(BELL, "on")
    await hass.async_block_till_done()
    expires = hass.states.get(DOORBELL).attributes["event_expires"]

    fired = async_capture_events(hass, EVENT_FIRED)
    await _restart(hass, entry)
    state = hass.states.get(DOORBELL)
    assert state.state == "active"
    assert state.attributes["event_expires"] == expires
    assert not fired

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOORBELL).state == "idle"


async def test_event_alert_expired_during_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A duration that ran out while HA was down ends at once, with a done event."""
    calls = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(BELL, "off")
    entry = await setup_alerts(
        trigger_alert("Doorbell", BELL_TRIGGERS, duration={"minutes": 10}),
        group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}]),
        options={"default_groups": ["phones"]},
    )
    hass.states.async_set(BELL, "on")
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=15))
    ended = async_capture_events(hass, EVENT_ENDED)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(DOORBELL).state == "idle"
    assert [event.data["reason"] for event in ended] == ["resolved"]
    assert calls[-1].data["message"] == "Doorbell stopped firing after 10 minutes."


async def test_snooze_resumes(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A snooze still running after a restart runs out on time."""
    entry = await setup_alerts(alert_subentry("Back Door Open"))
    await hass.services.async_call(DOMAIN, "fire", {"entity_id": DOOR}, blocking=True)
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"entity_id": DOOR, "duration": {"minutes": 30}},
        blocking=True,
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=10))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "ack"

    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "active"


async def test_snooze_expired_during_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A snooze that ran out while HA was down ends at once, with its reminder."""
    calls = async_mock_service(hass, "notify", "phone")
    entry = await setup_alerts(
        alert_subentry("Back Door Open"),
        group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}]),
        options={"default_groups": ["phones"]},
    )
    await hass.services.async_call(DOMAIN, "fire", {"entity_id": DOOR}, blocking=True)
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"entity_id": DOOR, "duration": {"minutes": 15}},
        blocking=True,
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=40))
    unacked = async_capture_events(hass, EVENT_UNACKED)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(DOOR).state == "active"
    assert len(unacked) == 1
    assert calls[-1].data["message"] == "Back Door Open is still firing (40 minutes)."


async def test_disabled_survives_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A disabled condition alert comes back disabled, ignoring its input."""
    hass.states.async_set("binary_sensor.back_door", "off")
    entry = await setup_alerts(
        state_alert("Back Door Open", "binary_sensor.back_door")
    )
    await hass.services.async_call(
        DOMAIN, "disable", {"entity_id": DOOR}, blocking=True
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "disabled"

    hass.states.async_set("binary_sensor.back_door", "on")
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "disabled"


async def test_suspension_ended_during_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A suspension that ran out while HA was down ends when it's back."""
    hass.states.async_set("binary_sensor.back_door", "on")
    entry = await setup_alerts(
        state_alert("Back Door Open", "binary_sensor.back_door")
    )
    await hass.services.async_call(
        DOMAIN,
        "suspend",
        {"entity_id": DOOR, "duration": {"minutes": 10}},
        blocking=True,
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=30))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["disabled_until"] is None
    assert state.attributes["last_enabled_by"] is None
