"""Tests for event alerts: trigger and bus event kinds (spec §4.2)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_ENDED,
    EVENT_FIRED,
)

from .conftest import SetupAlerts, event_alert, group_subentry, trigger_alert

BELL = "binary_sensor.doorbell"
ALERT = "alert_redux.doorbell"
PARCEL = "alert_redux.parcel"
TRIGGERS = [{"trigger": "state", "entity_id": BELL, "to": "on"}]
PHONE = group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}])
DEFAULTS: dict[str, Any] = {"default_groups": ["phones"]}
TEN_MINUTES = {"hours": 0, "minutes": 10, "seconds": 0}


async def _set(hass: HomeAssistant, entity_id: str, state: str) -> None:
    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()


async def _ring(hass: HomeAssistant) -> None:
    await _set(hass, BELL, "on")
    await _set(hass, BELL, "off")


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str = ALERT) -> str:
    return hass.states.get(entity_id).state


def _sent(calls: list[ServiceCall]) -> list[str]:
    return [call.data["message"] for call in calls]


@pytest.fixture
def events(hass: HomeAssistant) -> dict[str, list]:
    return {
        name: async_capture_events(hass, event)
        for name, event in (
            ("fired", EVENT_FIRED),
            ("ended", EVENT_ENDED),
            ("acked", EVENT_ACKED),
        )
    }


async def test_trigger_fires_and_expires(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    freezer: FrozenDateTimeFactory,
    events: dict[str, list],
) -> None:
    """A trigger fires the alert, which ends when its duration runs out."""
    calls = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(BELL, "off")
    await setup_alerts(
        trigger_alert("Doorbell", TRIGGERS, duration=TEN_MINUTES),
        PHONE,
        options=DEFAULTS,
    )
    state = hass.states.get(ALERT)
    assert state.state == "idle"
    assert state.attributes["kind"] == "trigger"
    assert state.attributes["triggers"] == TRIGGERS
    assert state.attributes["duration"] == 600
    assert state.attributes["event_expires"] is None
    assert "no_data_since" not in state.attributes

    await _ring(hass)
    state = hass.states.get(ALERT)
    assert state.state == "active"
    assert state.attributes["fire_count"] == 1
    assert state.attributes["event_expires"] == (
        dt_util.utcnow() + timedelta(minutes=10)
    )
    assert state.attributes["trigger_data"]["to_state"]["state"] == "on"
    assert len(events["fired"]) == 1
    assert events["fired"][0].data["trigger_data"]["entity_id"] == BELL
    assert _sent(calls) == ["Doorbell is firing."]

    await _tick(hass, freezer, 9)
    assert _state(hass) == "active"
    await _tick(hass, freezer, 1)
    assert _state(hass) == "idle"
    assert hass.states.get(ALERT).attributes["event_expires"] is None
    assert len(events["ended"]) == 1
    assert events["ended"][0].data["reason"] == "resolved"
    assert events["ended"][0].data["duration_seconds"] == 600
    assert _sent(calls)[-1] == "Doorbell stopped firing after 10 minutes."


async def test_fire_again(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    freezer: FrozenDateTimeFactory,
    events: dict[str, list],
) -> None:
    """Firing again restarts the duration and counts, keeping the ack (§4.2)."""
    calls = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(BELL, "off")
    await setup_alerts(
        trigger_alert("Doorbell", TRIGGERS, duration=TEN_MINUTES),
        PHONE,
        options=DEFAULTS,
    )
    await _ring(hass)
    await _tick(hass, freezer, 6)
    await _ring(hass)
    assert hass.states.get(ALERT).attributes["fire_count"] == 2
    assert len(calls) == 2  # Still active, so the on message is sent again.

    await hass.services.async_call(DOMAIN, "ack", {"entity_id": ALERT}, blocking=True)
    await _ring(hass)
    state = hass.states.get(ALERT)
    assert state.state == "ack"
    assert state.attributes["fire_count"] == 3
    assert len(calls) == 2  # Acknowledged: firing again doesn't nag.

    # The duration runs from the latest fire.
    await _tick(hass, freezer, 9)
    assert _state(hass) == "ack"
    await _tick(hass, freezer, 1)
    assert _state(hass) == "idle"
    assert events["ended"][0].data["duration_seconds"] == 16 * 60


async def test_manual_actions_refused(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(trigger_alert("Doorbell", TRIGGERS))
    for service in ("fire", "dismiss"):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, service, {"entity_id": ALERT}, blocking=True
            )


async def test_condition(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The condition is judged when the trigger fires; no data fires anyway."""
    hass.states.async_set(BELL, "off")
    hass.states.async_set("input_boolean.home", "off")
    await setup_alerts(
        trigger_alert(
            "Doorbell",
            TRIGGERS,
            condition="{{ is_state('input_boolean.home', 'on') "
            "and trigger.to_state.state == 'on' }}",
        ),
        trigger_alert(
            "Parcel",
            [{"trigger": "state", "entity_id": BELL, "to": "on"}],
            condition="{{ states('sensor.missing') | float > 1 }}",
        ),
    )
    await _ring(hass)
    assert _state(hass) == "idle"
    assert _state(hass, PARCEL) == "active"
    assert "condition has no data" in caplog.text

    await _set(hass, "input_boolean.home", "on")
    await _ring(hass)
    assert _state(hass) == "active"


async def test_bus_event(
    hass: HomeAssistant, setup_alerts: SetupAlerts, events: dict[str, list]
) -> None:
    """A bus event alert fires on matching events, with trigger.event."""
    await setup_alerts(
        event_alert(
            "Parcel",
            "parcel_delivered",
            event_data={"carrier": "post"},
            message="Parcel from {{ trigger.event.data.carrier }} "
            "at {{ trigger.event.data.door }}",
        )
    )
    state = hass.states.get(PARCEL)
    assert state.attributes["kind"] == "event"
    assert state.attributes["event_type"] == "parcel_delivered"
    assert state.attributes["event_data"] == {"carrier": "post"}

    hass.bus.async_fire("parcel_delivered", {"carrier": "courier", "door": "front"})
    await hass.async_block_till_done()
    assert _state(hass, PARCEL) == "idle"

    hass.bus.async_fire("parcel_delivered", {"carrier": "post", "door": "front"})
    await hass.async_block_till_done()
    state = hass.states.get(PARCEL)
    assert state.state == "active"
    assert state.attributes["message"] == "Parcel from post at front"
    assert state.attributes["trigger_data"]["event"]["data"]["door"] == "front"


async def test_trigger_in_done_message(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The done message sees the trigger of the firing that ended."""
    calls = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(BELL, "off")
    await setup_alerts(
        trigger_alert(
            "Doorbell",
            TRIGGERS,
            duration=TEN_MINUTES,
            done_message="{{ trigger.entity_id }} quiet after {{ duration }}",
        ),
        PHONE,
        options=DEFAULTS,
    )
    await _ring(hass)
    await _tick(hass, freezer, 10)
    assert _sent(calls)[-1] == f"{BELL} quiet after 10 minutes"


async def test_priority_default_duration(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Without its own duration, an alert uses its priority's default."""
    hass.states.async_set(BELL, "off")
    await setup_alerts(
        trigger_alert("Doorbell", TRIGGERS, priority="critical"),
        options={
            "event_durations": {"critical": {"hours": 0, "minutes": 2, "seconds": 0}}
        },
    )
    assert hass.states.get(ALERT).attributes["duration"] == 120
    await _ring(hass)
    await _tick(hass, freezer, 2)
    assert _state(hass) == "idle"


async def test_default_durations(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(BELL, "off")
    await setup_alerts(
        trigger_alert("Doorbell", TRIGGERS, priority="emergency"),
        event_alert("Parcel", "parcel_delivered", priority="informational"),
    )
    assert hass.states.get(ALERT).attributes["duration"] == 3600
    assert hass.states.get(PARCEL).attributes["duration"] == 300


async def test_short_alerts_send_no_reminders(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Reminders only if the duration outlasts the first interval (§9.6)."""
    calls = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(BELL, "off")
    await setup_alerts(
        trigger_alert("Doorbell", TRIGGERS, duration=TEN_MINUTES),
        trigger_alert(
            "Parcel",
            [{"trigger": "state", "entity_id": BELL, "to": "on"}],
            duration={"hours": 1, "minutes": 0, "seconds": 0},
        ),
        PHONE,
        options=DEFAULTS,
    )
    assert hass.states.get(ALERT).attributes["reminder_schedule"] == []
    assert hass.states.get(PARCEL).attributes["reminder_schedule"] == [10, 20, 30, 60]

    await _ring(hass)
    assert hass.states.get(ALERT).attributes["next_reminder"] is None
    await _tick(hass, freezer, 10)
    assert _sent(calls).count("Parcel is still firing (10 minutes).") == 1
    assert not any(message.startswith("Doorbell is still") for message in _sent(calls))


async def test_triggers_wait_for_start_and_startup_delay(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Triggers attach once HA has started and the startup delay is over."""
    hass.set_state(CoreState.starting)
    await setup_alerts(
        event_alert("Parcel", "parcel_delivered"),
        options={"startup_delay": {"hours": 0, "minutes": 1, "seconds": 0}},
    )

    async def deliver() -> None:
        hass.bus.async_fire("parcel_delivered", {})
        await hass.async_block_till_done()

    await deliver()
    assert _state(hass, PARCEL) == "idle"

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    await deliver()
    assert _state(hass, PARCEL) == "idle"

    await _tick(hass, freezer, 1)
    await deliver()
    assert _state(hass, PARCEL) == "active"


async def test_invalid_trigger_unavailable(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An alert whose triggers can't be attached shows as unavailable (§7.1)."""
    await setup_alerts(
        trigger_alert("Doorbell", [{"trigger": "no_such_platform"}]),
    )
    assert _state(hass) == "unavailable"
