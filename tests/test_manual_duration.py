"""Tests for manual alerts that end by themselves (spec §4.3, 1.1.0)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import DOMAIN, EVENT_ENDED, EVENT_FIRED

from .conftest import SetupAlerts, alert_subentry, group_subentry

DOOR = "alert_redux.back_door_open"
PHONE = group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}])
DEFAULTS: dict[str, Any] = {"default_groups": ["phones"]}
TEN_MINUTES = {"hours": 0, "minutes": 10, "seconds": 0}


async def _fire(hass: HomeAssistant, entity_id: str = DOOR) -> None:
    await hass.services.async_call(
        DOMAIN, "fire", {"entity_id": entity_id}, blocking=True
    )


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str = DOOR) -> str:
    return hass.states.get(entity_id).state


def _sent(calls: list[ServiceCall]) -> list[str]:
    return [call.data["message"] for call in calls]


async def test_off_by_default(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Without the option, a manual alert has no duration and never expires."""
    await setup_alerts(alert_subentry("Back Door Open"))
    state = hass.states.get(DOOR)
    assert "duration" not in state.attributes
    assert "event_expires" not in state.attributes

    await _fire(hass)
    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert "event_expires" not in state.attributes


async def test_fires_and_expires(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Fired by the action, a self-ending alert ends when its duration runs out."""
    calls = async_mock_service(hass, "notify", "phone")
    fired = async_capture_events(hass, EVENT_FIRED)
    ended = async_capture_events(hass, EVENT_ENDED)
    await setup_alerts(
        alert_subentry("Back Door Open", ends_by_itself=True, duration=TEN_MINUTES),
        PHONE,
        options=DEFAULTS,
    )
    state = hass.states.get(DOOR)
    assert state.attributes["duration"] == 600
    assert state.attributes["event_expires"] is None

    await _fire(hass)
    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["fire_count"] == 1
    assert state.attributes["event_expires"] == dt_util.utcnow() + timedelta(minutes=10)
    assert len(fired) == 1
    assert _sent(calls) == ["Back Door Open is firing."]

    await _tick(hass, freezer, 9)
    assert _state(hass) == "active"
    await _tick(hass, freezer, 1)
    state = hass.states.get(DOOR)
    assert state.state == "idle"
    assert state.attributes["event_expires"] is None
    assert len(ended) == 1
    assert ended[0].data["reason"] == "resolved"
    assert ended[0].data["duration_seconds"] == 600
    assert _sent(calls)[-1] == "Back Door Open stopped firing after 10 minutes."


async def test_dismiss_ends_it_early(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The dismiss action always works, even mid-duration (spec §4.3)."""
    ended = async_capture_events(hass, EVENT_ENDED)
    await setup_alerts(
        alert_subentry("Back Door Open", ends_by_itself=True, duration=TEN_MINUTES)
    )
    await _fire(hass)
    await _tick(hass, freezer, 2)

    await hass.services.async_call(DOMAIN, "dismiss", {"entity_id": DOOR}, blocking=True)
    state = hass.states.get(DOOR)
    assert state.state == "idle"
    assert state.attributes["event_expires"] is None
    assert ended[0].data["reason"] == "dismissed"

    # Nothing left running to expire later.
    await _tick(hass, freezer, 10)
    assert _state(hass) == "idle"
    assert len(ended) == 1


async def test_fire_again_restarts_duration(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Firing again restarts the duration and counts, keeping the ack (§4.3)."""
    calls = async_mock_service(hass, "notify", "phone")
    ended = async_capture_events(hass, EVENT_ENDED)
    await setup_alerts(
        alert_subentry("Back Door Open", ends_by_itself=True, duration=TEN_MINUTES),
        PHONE,
        options=DEFAULTS,
    )
    await _fire(hass)
    await _tick(hass, freezer, 6)
    await _fire(hass)
    assert hass.states.get(DOOR).attributes["fire_count"] == 2
    assert len(calls) == 2  # Still active, so the on message is sent again.

    await hass.services.async_call(DOMAIN, "ack", {"entity_id": DOOR}, blocking=True)
    await _fire(hass)
    state = hass.states.get(DOOR)
    assert state.state == "ack"
    assert state.attributes["fire_count"] == 3
    assert len(calls) == 2  # Acknowledged: firing again doesn't nag.

    # The duration runs from the latest fire.
    await _tick(hass, freezer, 9)
    assert _state(hass) == "ack"
    await _tick(hass, freezer, 1)
    assert _state(hass) == "idle"
    assert ended[0].data["duration_seconds"] == 16 * 60


async def test_priority_default_duration(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Without its own duration, a self-ending alert uses its priority's default."""
    await setup_alerts(
        alert_subentry("Back Door Open", priority="critical", ends_by_itself=True),
        options={
            "event_durations": {"critical": {"hours": 0, "minutes": 2, "seconds": 0}}
        },
    )
    assert hass.states.get(DOOR).attributes["duration"] == 120
    await _fire(hass)
    await _tick(hass, freezer, 2)
    assert _state(hass) == "idle"


async def test_short_duration_sends_no_reminders(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Reminders only if the duration outlasts the first interval (§9.6)."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open", ends_by_itself=True, duration=TEN_MINUTES),
        alert_subentry(
            "Leak",
            subentry_id="leak",
            ends_by_itself=True,
            duration={"hours": 1, "minutes": 0, "seconds": 0},
        ),
        PHONE,
        options=DEFAULTS,
    )
    assert hass.states.get(DOOR).attributes["reminder_schedule"] == []
    assert hass.states.get("alert_redux.leak").attributes["reminder_schedule"] == [
        10,
        20,
        30,
        60,
    ]

    await _fire(hass)
    assert hass.states.get(DOOR).attributes["next_reminder"] is None
    await hass.services.async_call(
        DOMAIN, "fire", {"entity_id": "alert_redux.leak"}, blocking=True
    )
    await _tick(hass, freezer, 10)
    assert _sent(calls).count("Leak is still firing (10 minutes).") == 1
    assert not any(
        message.startswith("Back Door Open is still") for message in _sent(calls)
    )


async def test_turning_off_mid_firing_cancels_the_expiry(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Turning the option off while firing clears the pending expiry.

    Without this, the alert would still silently end at the old deadline even
    though its attributes no longer show any expiry pending.
    """
    entry = await setup_alerts(
        alert_subentry(
            "Back Door Open",
            subentry_id="door",
            ends_by_itself=True,
            duration=TEN_MINUTES,
        )
    )
    await _fire(hass)
    assert hass.states.get(DOOR).attributes["event_expires"] is not None

    subentry = entry.subentries["door"]
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, "ends_by_itself": False}
    )
    await hass.async_block_till_done()
    state = hass.states.get(DOOR)
    assert "duration" not in state.attributes
    assert "event_expires" not in state.attributes

    await _tick(hass, freezer, 10)
    assert _state(hass) == "active"
