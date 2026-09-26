"""Tests for quiet hours (spec §9.9)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import DOMAIN

from .conftest import SetupAlerts, alert_subentry, group_subentry

QUIET = "input_boolean.quiet_hours"
PHONES = group_subentry(
    "Phones", "phones", actions=[{"action": "notify.mobile_app_phone"}]
)
SPEAKER = group_subentry(
    "Speaker", "speaker", actions=[{"action": "notify.speaker"}], loud=True
)
BOTH = ["phones", "speaker"]
OPTIONS = {"quiet_entity": QUIET}


def _alert(title: str, subentry_id: str, **data: Any) -> dict[str, Any]:
    return alert_subentry(
        title,
        subentry_id,
        priority="notice",
        notifier_groups=BOTH,
        reminder_schedule=[],
        **data,
    )


def _entity_id(title: str) -> str:
    return f"{DOMAIN}.{title.lower().replace(' ', '_')}"


async def _call(hass: HomeAssistant, service: str, title: str) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": _entity_id(title)}, blocking=True
    )
    await hass.async_block_till_done()


async def _quiet(hass: HomeAssistant, state: str) -> None:
    hass.states.async_set(QUIET, state)
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _messages(calls: list[ServiceCall]) -> list[str]:
    return [call.data["message"] for call in calls]


def _shown(calls: list[ServiceCall]) -> list[str]:
    """Return the messages shown, leaving out clearing ones."""
    return [m for m in _messages(calls) if m != "clear_notification"]


def _clock(when: datetime) -> str:
    return dt_util.as_local(when).strftime("%H:%M")


async def test_a_night_of_quiet_hours(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The phones hear everything as it happens; the loud speaker hears, when
    quiet hours end, one reminder for what's still firing and one summary of
    what stopped, and nothing about what was acknowledged (spec §9.9)."""
    await hass.config.async_set_time_zone("America/Chicago")
    freezer.move_to("2030-03-05 06:00:00+00:00")  # 00:00 local
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    speaker = async_mock_service(hass, "notify", "speaker")
    await _quiet(hass, "on")
    await setup_alerts(
        _alert("Back Door Open", "door"),
        _alert("Garage Open", "garage"),
        _alert("Laundry Ready", "laundry"),
        PHONES,
        SPEAKER,
        options=OPTIONS,
    )
    start = dt_util.utcnow()

    # The back door opens twice and is closed each time.
    await _call(hass, "fire", "Back Door Open")
    await _tick(hass, freezer, 8)
    await _call(hass, "dismiss", "Back Door Open")
    await _tick(hass, freezer, 60)
    await _call(hass, "fire", "Back Door Open")
    await _tick(hass, freezer, 4)
    await _call(hass, "dismiss", "Back Door Open")
    # The garage opens and stays open; the laundry is acknowledged.
    await _call(hass, "fire", "Garage Open")
    await _call(hass, "fire", "Laundry Ready")
    await _call(hass, "ack", "Laundry Ready")
    assert len(_shown(phone)) == 6
    assert speaker == []

    await _tick(hass, freezer, 30)
    await _quiet(hass, "off")
    assert _messages(speaker) == [
        "Garage Open is still firing (30 minutes).",
        "While quiet hours were on:\n"
        f"Back Door Open: first started {_clock(start)}, last stopped "
        f"{_clock(start + timedelta(minutes=72))}, fired 2 times for 12 minutes "
        "in all.",
    ]
    assert speaker[1].data["title"] == "Quiet hours summary"
    # The phones heard nothing more.
    assert len(_shown(phone)) == 6

    # Quiet hours are over: the speaker hears things as they happen again.
    await _call(hass, "fire", "Back Door Open")
    assert _messages(speaker)[2] == "Back Door Open is firing."


async def test_threshold(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Alerts at the threshold or above get through; a group can have its own."""
    speaker = async_mock_service(hass, "notify", "speaker")
    strict = group_subentry(
        "Strict", "strict", actions=[{"action": "notify.speaker"}], loud=True
    )
    strict["data"]["quiet_threshold"] = "critical"
    await _quiet(hass, "on")
    await setup_alerts(
        alert_subentry("Leak", "leak", priority="warning", notifier_groups=["speaker"]),
        alert_subentry("Smoke", "smoke", priority="warning", notifier_groups=["strict"]),
        SPEAKER,
        strict,
        options=OPTIONS,
    )
    await _call(hass, "fire", "Leak")
    await _call(hass, "fire", "Smoke")
    assert _messages(speaker) == ["Leak is firing."]


async def test_quiet_groups_and_no_entity(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Quiet groups deliver as normal; with no entity, there are no quiet hours."""
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    speaker = async_mock_service(hass, "notify", "speaker")
    await _quiet(hass, "on")
    await setup_alerts(_alert("Back Door Open", "door"), PHONES, SPEAKER)
    await _call(hass, "fire", "Back Door Open")
    assert len(phone) == len(speaker) == 1


async def test_group_entity_overrides_the_global_one(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    speaker = async_mock_service(hass, "notify", "speaker")
    bedroom = group_subentry(
        "Bedroom", "speaker", actions=[{"action": "notify.speaker"}], loud=True
    )
    bedroom["data"]["quiet_entity"] = "input_boolean.bedroom_quiet"
    hass.states.async_set("input_boolean.bedroom_quiet", "on")
    await _quiet(hass, "off")
    await setup_alerts(_alert("Back Door Open", "door"), bedroom, options=OPTIONS)
    await _call(hass, "fire", "Back Door Open")
    assert speaker == []
    hass.states.async_set("input_boolean.bedroom_quiet", "off")
    await hass.async_block_till_done()
    assert _messages(speaker) == ["Back Door Open is still firing (0 seconds)."]


async def test_soften(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """A softening group sends with the quiet-hours data of members that have
    some; the others hold, and only they hear when quiet hours end."""
    speaker = async_mock_service(hass, "notify", "speaker")
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    soft = group_subentry(
        "Soft",
        "speaker",
        actions=[
            {"action": "notify.mobile_app_phone", "data": {"channel": "loud"},
             "quiet_data": {"channel": "quiet"}},
            {"action": "notify.speaker"},
        ],
        loud=True,
    )
    soft["data"]["quiet_behaviour"] = "soften"
    await _quiet(hass, "on")
    await setup_alerts(_alert("Back Door Open", "door"), soft, options=OPTIONS)
    await _call(hass, "fire", "Back Door Open")
    assert len(phone) == 1
    assert phone[0].data["data"]["channel"] == "quiet"
    assert speaker == []

    await _quiet(hass, "off")
    assert len(phone) == 1
    assert _messages(speaker) == ["Back Door Open is still firing (0 seconds)."]


async def test_unavailable_entity_is_not_quiet_but_keeps_holding(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An unavailable entity can't say it's quiet hours, so new notifications
    go out (fail loud), but what's held stays held until it's off."""
    speaker = async_mock_service(hass, "notify", "speaker")
    await _quiet(hass, "on")
    await setup_alerts(
        _alert("Back Door Open", "door"),
        _alert("Garage Open", "garage"),
        SPEAKER,
        options=OPTIONS,
    )
    await _call(hass, "fire", "Back Door Open")
    await _quiet(hass, "unavailable")
    await _call(hass, "fire", "Garage Open")
    assert _messages(speaker) == ["Garage Open is firing."]
    await _quiet(hass, "off")
    assert _messages(speaker)[1] == "Back Door Open is still firing (0 seconds)."


async def test_missing_entity_is_raised(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A quiet-hours entity that doesn't exist once integrations have had time
    to set up is a Repairs issue; it clears when the entity appears."""
    speaker = async_mock_service(hass, "notify", "speaker")
    await setup_alerts(_alert("Back Door Open", "door"), SPEAKER, options=OPTIONS)
    await _call(hass, "fire", "Back Door Open")
    assert len(speaker) == 1

    issues = ir.async_get(hass)
    ident = f"quiet_entity_missing_{QUIET}"
    await _tick(hass, freezer, 6)
    issue = issues.async_get_issue(DOMAIN, ident)
    assert issue is not None
    assert issue.translation_placeholders == {"entity": QUIET, "used_by": "Speaker"}

    await _quiet(hass, "off")
    assert issues.async_get_issue(DOMAIN, ident) is None


async def test_deleted_alert_drops_held(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    speaker = async_mock_service(hass, "notify", "speaker")
    await _quiet(hass, "on")
    entry = await setup_alerts(_alert("Back Door Open", "door"), SPEAKER, options=OPTIONS)
    await _call(hass, "fire", "Back Door Open")
    await _call(hass, "dismiss", "Back Door Open")
    hass.config_entries.async_remove_subentry(entry, "door")
    await hass.async_block_till_done()
    await _quiet(hass, "off")
    assert speaker == []


async def test_held_notifications_survive_a_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Held notifications are stored; quiet hours that ended while Home
    Assistant was down end as soon as it's back."""
    speaker = async_mock_service(hass, "notify", "speaker")
    await _quiet(hass, "on")
    entry = await setup_alerts(_alert("Back Door Open", "door"), SPEAKER, options=OPTIONS)
    await _call(hass, "fire", "Back Door Open")
    await _call(hass, "dismiss", "Back Door Open")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await _quiet(hass, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(speaker) == 1
    assert speaker[0].data["title"] == "Quiet hours summary"
    assert "Back Door Open: started" in speaker[0].data["message"]


@pytest.mark.parametrize("final", [True, False])
async def test_throttling_summary_during_quiet_hours(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    freezer: FrozenDateTimeFactory,
    final: bool,
) -> None:
    """A throttling summary held for a firing that ended is listed in the
    quiet-hours summary (throttling held the done notification itself); one
    for a firing that goes on gives way to the reminder."""
    speaker = async_mock_service(hass, "notify", "speaker")
    await _quiet(hass, "on")
    await setup_alerts(
        _alert("Back Door Open", "door", throttle=[1, 5]), SPEAKER, options=OPTIONS
    )
    await _call(hass, "fire", "Back Door Open")
    await _call(hass, "fire", "Back Door Open")
    if final:
        await _call(hass, "dismiss", "Back Door Open")
    await _tick(hass, freezer, 5)
    await _quiet(hass, "off")
    messages = _messages(speaker)
    if final:
        assert messages == [
            "While quiet hours were on:\nBack Door Open: [Throttling ends] Fired "
            "1× while throttled, most recently 5 minutes ago; stopped firing 5 "
            "minutes ago after 0 seconds."
        ]
    else:
        assert messages == ["Back Door Open is still firing (5 minutes)."]
