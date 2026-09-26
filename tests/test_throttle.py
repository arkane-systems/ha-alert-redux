"""Tests for throttling alerts' notifications (spec §9.8)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import DOMAIN

from .conftest import SetupAlerts, alert_subentry, group_subentry

DOOR = "alert_redux.back_door_open"
PHONE = group_subentry("Phones", "phones", actions=[{"action": "notify.mobile_app_phone"}])
DEFAULTS = {"default_groups": ["phones"]}


async def _call(hass: HomeAssistant, service: str, **data: Any) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": DOOR, **data}, blocking=True
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


async def test_throttling_holds_and_summarises(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The notification that reaches the limit is marked; later on and done
    notifications are held; one summary follows when the rate drops."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        alert_subentry("Back Door Open", throttle=[3, 10]), PHONE, options=DEFAULTS
    )
    assert hass.states.get(DOOR).attributes["throttle"] == [3, 10]
    for _ in range(5):
        await _call(hass, "fire")
        await _tick(hass, freezer, 0.5)
        await _call(hass, "dismiss")
        await _tick(hass, freezer, 0.5)

    assert _messages(calls) == [
        "Back Door Open is firing.",
        "Back Door Open stopped firing after 30 seconds.",
        "Back Door Open is firing.",
        "Back Door Open stopped firing after 30 seconds.",
        "[Throttling starts] Back Door Open is firing.",
    ]
    throttled_since = hass.states.get(DOOR).attributes["throttled_since"]
    assert throttled_since is not None

    # The last three on notifications were at 2, 3, and 4 minutes: throttling
    # ends when the one at 2 leaves the ten-minute window, at 12.
    await _tick(hass, freezer, 6.9)
    assert len(calls) == 5
    await _tick(hass, freezer, 0.2)
    assert _messages(calls)[5:] == [
        "[Throttling ends] Fired 2× while throttled, most recently 8 minutes ago; "
        "stopped firing 7 minutes ago after 30 seconds."
    ]
    # It's final, like the done notification: no buttons.
    assert "actions" not in calls[5].data.get("data", {})
    assert hass.states.get(DOOR).attributes["throttled_since"] is None

    # Held notifications count: those at 3 and 4 minutes are still in the window,
    # so another firing now reaches the limit again.
    await _call(hass, "fire")
    await _call(hass, "dismiss")
    assert _messages(calls)[6] == "[Throttling starts] Back Door Open is firing."
    # Once things are calm, notifications go out as usual.
    await _tick(hass, freezer, 11)
    await _call(hass, "fire")
    assert _messages(calls)[7:] == [
        "[Throttling ends] Stopped firing 11 minutes ago after 0 seconds.",
        "Back Door Open is firing.",
    ]


async def test_summary_of_a_firing_that_goes_on(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Firing again counts; a summary while still firing isn't final."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        alert_subentry("Back Door Open", throttle=[2, 5], reminder_schedule=[]),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    await _call(hass, "fire")
    await _call(hass, "fire")
    assert _messages(calls) == [
        "Back Door Open is firing.",
        "[Throttling starts] Back Door Open is firing.",
    ]
    await _tick(hass, freezer, 5)
    assert _messages(calls)[2] == (
        "[Throttling ends] Fired 1× while throttled, most recently 5 minutes ago; "
        "still firing."
    )
    # Not final: it keeps the Acknowledge and Snooze buttons.
    assert calls[2].data["data"]["actions"]


async def test_reminders_are_not_throttled(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        alert_subentry("Back Door Open", throttle=[1, 60], reminder_schedule=[1]),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    await _tick(hass, freezer, 1)
    await _tick(hass, freezer, 1)
    assert _messages(calls) == [
        "[Throttling starts] Back Door Open is firing.",
        "Back Door Open is still firing (1 minute).",
        "Back Door Open is still firing (2 minutes).",
    ]


async def test_nothing_held_sends_no_summary(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        alert_subentry("Back Door Open", throttle=[1, 5], reminder_schedule=[]),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    await _tick(hass, freezer, 6)
    assert _messages(calls) == ["[Throttling starts] Back Door Open is firing."]
    assert hass.states.get(DOOR).attributes["throttled_since"] is None


async def test_default_throttle_and_turning_it_off(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Alerts without their own use the default; turning it off while throttled
    ends throttling at once, with the summary."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = await setup_alerts(
        alert_subentry("Back Door Open"),
        PHONE,
        options={**DEFAULTS, "default_throttle": [1, 60]},
    )
    assert hass.states.get(DOOR).attributes["throttle"] == [1, 60]
    await _call(hass, "fire")
    await _tick(hass, freezer, 2)
    await _call(hass, "dismiss")
    assert len(calls) == 1

    hass.config_entries.async_update_entry(entry, options=DEFAULTS)
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).attributes["throttle"] is None
    assert _messages(calls)[1] == (
        "[Throttling ends] Stopped firing just now after 2 minutes."
    )


async def test_own_empty_throttle_overrides_the_default(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        alert_subentry("Back Door Open", throttle=[]),
        PHONE,
        options={**DEFAULTS, "default_throttle": [1, 60]},
    )
    assert hass.states.get(DOOR).attributes["throttle"] is None
    for _ in range(3):
        await _call(hass, "fire")
        await _call(hass, "dismiss")
    assert len(calls) == 6
    assert not any("Throttling" in message for message in _messages(calls))


async def test_throttling_survives_a_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Throttle state is stored; an end that fell due while Home Assistant was
    down is dealt with as soon as it's back."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = await setup_alerts(
        alert_subentry("Back Door Open", throttle=[1, 5]), PHONE, options=DEFAULTS
    )
    await _call(hass, "fire")
    await _call(hass, "dismiss")
    assert len(calls) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=10))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _messages(calls)[1:] == [
        "[Throttling ends] Stopped firing 10 minutes ago after 0 seconds."
    ]
    assert hass.states.get(DOOR).attributes["throttled_since"] is None
