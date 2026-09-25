"""Tests for snoozing (spec §6.2)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant, ServiceCall
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
    EVENT_SNOOZE_EXPIRED,
    EVENT_SNOOZED,
    EVENT_UNACKED,
)

from .conftest import SetupAlerts, alert_subentry, event_alert, group_subentry

DOOR = "alert_redux.back_door_open"
PHONE = group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}])
DEFAULTS = {"default_groups": ["phones"]}


async def _call(
    hass: HomeAssistant, service: str, entity_id: str = DOOR, **data: Any
) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": entity_id, **data}, blocking=True
    )
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _messages(calls: list[ServiceCall]) -> list[str]:
    return [call.data["message"] for call in calls]


async def test_snooze_acks_and_expires(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    freezer: FrozenDateTimeFactory,
    hass_admin_user,
) -> None:
    """Snoozing acknowledges; when it runs out, the alert is active and reminds."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(alert_subentry("Back Door Open"), PHONE, options=DEFAULTS)
    events: dict[str, list] = {
        name: async_capture_events(hass, name)
        for name in (EVENT_SNOOZED, EVENT_ACKED, EVENT_SNOOZE_EXPIRED, EVENT_UNACKED)
    }
    order: list[str] = []
    for name in events:
        hass.bus.async_listen(name, lambda event: order.append(event.event_type))
    await _call(hass, "fire")

    await _tick(hass, freezer, 2)
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"entity_id": DOOR, "duration": {"minutes": 30}},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()
    state = hass.states.get(DOOR)
    assert state.state == "ack"
    until = dt_util.utcnow() + timedelta(minutes=30)
    assert state.attributes["snoozed_until"] == until
    assert state.attributes["last_snoozed_by"] == hass_admin_user.id
    assert state.attributes["next_reminder"] is None
    assert order == [EVENT_SNOOZED, EVENT_ACKED]
    assert events[EVENT_SNOOZED][0].data["snoozed_until"] == until
    assert events[EVENT_SNOOZED][0].data["user_id"] == hass_admin_user.id
    assert events[EVENT_ACKED][0].data["old_state"] == "active"

    # No reminders while snoozed: the 10-minute slot passes silently.
    await _tick(hass, freezer, 20)
    assert len(calls) == 1

    # Snooze ends at 32 min; the next slot (60) is far off, so remind now.
    await _tick(hass, freezer, 10)
    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["snoozed_until"] is None
    assert order[2:] == [EVENT_SNOOZE_EXPIRED, EVENT_UNACKED]
    assert events[EVENT_UNACKED][0].data["user_id"] is None
    assert _messages(calls)[1:] == ["Back Door Open is still firing (32 minutes)."]
    assert state.attributes["next_reminder"] == (
        dt_util.parse_datetime(state.attributes["firing_since"].isoformat())
        + timedelta(minutes=60)
    )

    # Then the original schedule carries on.
    await _tick(hass, freezer, 28)
    assert _messages(calls)[2:] == ["Back Door Open is still firing (1 hour)."]


async def test_snooze_end_skips_reminder_near_a_slot(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A slot within the window does the job instead (spec §6.2)."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(alert_subentry("Back Door Open"), PHONE, options=DEFAULTS)
    await _call(hass, "fire")
    await _call(hass, "snooze", duration={"minutes": 27})

    await _tick(hass, freezer, 27)
    assert hass.states.get(DOOR).state == "active"
    assert len(calls) == 1
    await _tick(hass, freezer, 3)
    assert _messages(calls)[1:] == ["Back Door Open is still firing (30 minutes)."]


async def test_window_option(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The window is a global option."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open"),
        PHONE,
        options=DEFAULTS | {"snooze_reminder_window": {"minutes": 2}},
    )
    await _call(hass, "fire")
    await _call(hass, "snooze", duration={"minutes": 27})
    await _tick(hass, freezer, 27)
    assert len(calls) == 2


async def test_resnooze_and_keep_acknowledged(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Re-snoozing moves the deadline; ack makes it lasting; unack clears it."""
    await setup_alerts(alert_subentry("Back Door Open"))
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    acked = async_capture_events(hass, EVENT_ACKED)
    await _call(hass, "fire")
    await _call(hass, "snooze", duration={"hours": 1})
    await _call(hass, "snooze", duration={"minutes": 5})
    assert len(snoozed) == 2 and len(acked) == 1
    assert hass.states.get(DOOR).attributes["snoozed_until"] == (
        dt_util.utcnow() + timedelta(minutes=5)
    )

    await _call(hass, "ack")
    assert len(acked) == 2
    assert acked[1].data["old_state"] == "ack"
    assert hass.states.get(DOOR).attributes["snoozed_until"] is None
    await _tick(hass, freezer, 10)
    assert hass.states.get(DOOR).state == "ack"

    await _call(hass, "snooze", duration={"minutes": 5})
    await _call(hass, "unack")
    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["snoozed_until"] is None
    expired = async_capture_events(hass, EVENT_SNOOZE_EXPIRED)
    await _tick(hass, freezer, 10)
    assert not expired


async def test_ending_cancels_the_snooze(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A new firing starts unacknowledged; the old snooze is gone."""
    await setup_alerts(alert_subentry("Back Door Open"))
    await _call(hass, "fire")
    await _call(hass, "snooze", duration={"minutes": 30})
    await _call(hass, "dismiss")
    assert hass.states.get(DOOR).attributes["snoozed_until"] is None
    await _call(hass, "fire")
    expired = async_capture_events(hass, EVENT_SNOOZE_EXPIRED)
    await _tick(hass, freezer, 40)
    assert hass.states.get(DOOR).state == "active"
    assert not expired


async def test_snooze_needs_firing_and_acknowledgeable(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_subentry("Fire Alarm", acknowledgeable=False),
    )
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    await _call(hass, "snooze", duration={"minutes": 5})
    assert hass.states.get(DOOR).state == "idle"
    assert not snoozed

    with pytest.raises(ServiceValidationError):
        await _call(hass, "snooze", "alert_redux.fire_alarm", duration={"minutes": 5})


async def test_event_alert_without_reminders(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """With no reminders, a snooze ending just makes the alert active."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        event_alert("Doorbell", "doorbell", duration={"minutes": 30}),
        PHONE,
        options=DEFAULTS | {"default_reminder_schedule": []},
    )
    hass.bus.async_fire("doorbell")
    await hass.async_block_till_done()
    await _call(hass, "snooze", "alert_redux.doorbell", duration={"minutes": 10})
    await _tick(hass, freezer, 10)
    state = hass.states.get("alert_redux.doorbell")
    assert state.state == "active"
    assert state.attributes["next_reminder"] is None
    assert len(calls) == 1
