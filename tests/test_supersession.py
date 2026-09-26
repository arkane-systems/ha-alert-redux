"""Tests for supersession (spec §8.1) and the done window (§9.7)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import DOMAIN, EVENT_SUPERSEDED
from custom_components.alert_redux.supersession import SupersessionGraph, find_cycle

from .conftest import SetupAlerts, alert_subentry, group_subentry, state_alert

OPEN = "alert_redux.back_door_open"
LEFT_OPEN = "alert_redux.back_door_left_open"
OVERNIGHT = "alert_redux.back_door_open_overnight"
DOOR = "binary_sensor.back_door"
PHONE = group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}])
DEFAULTS = {"default_groups": ["phones"]}


def _supersedes(*entity_ids: str) -> list[dict[str, Any]]:
    return [{"alert": entity_id} for entity_id in entity_ids]


async def _call(hass: HomeAssistant, service: str, entity_id: str) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _sent(calls: list[ServiceCall]) -> list[tuple[str, str]]:
    return [(call.data["title"], call.data["message"]) for call in calls]


async def _manual_pair(setup_alerts: SetupAlerts, **options: Any) -> None:
    """Set up Back Door Open, superseded by Back Door Left Open."""
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_subentry("Back Door Left Open", supersedes=_supersedes(OPEN)),
        PHONE,
        options={**DEFAULTS, **options},
    )


def test_graph_closure() -> None:
    graph = SupersessionGraph(
        {
            "a": _supersedes("b"),
            "b": _supersedes("c"),
            "d": _supersedes("c"),
        }
    )
    assert graph.superseders("c") == {"a", "b", "d"}
    assert graph.superseders("b") == {"a"}
    assert graph.superseders("a") == set()
    assert graph.superseded("a") == {"b", "c"}
    assert graph.direct_superseders("c") == {"b", "d"}
    assert graph.has_superseders("c")
    assert not graph.has_superseders("a")


def test_graph_survives_a_cycle() -> None:
    graph = SupersessionGraph({"a": _supersedes("b"), "b": _supersedes("a")})
    assert graph.superseders("a") == {"b"}
    assert graph.superseded("a") == {"b"}


def test_find_cycle() -> None:
    assert find_cycle({"a": ["b"], "b": ["c"]}) is None
    assert find_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}) == ["a", "b", "c", "a"]
    assert find_cycle({"a": ["a"]}) == ["a", "a"]


async def test_on_notification_waits_for_the_debounce(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A superseded alert's on notification waits 0.5 s, then goes if alone."""
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)

    await _call(hass, "fire", OPEN)
    assert calls == []
    await _tick(hass, freezer, 0.6)
    assert _sent(calls) == [("Back Door Open", "Back Door Open is firing.")]


async def test_on_notification_superseded(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Two alerts firing together: only the superseding one notifies."""
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)

    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _tick(hass, freezer, 1)
    assert _sent(calls) == [("Back Door Left Open", "Back Door Left Open is firing.")]
    # It isn't sent late either.
    await _call(hass, "dismiss", LEFT_OPEN)
    await _tick(hass, freezer, 10)
    assert [title for title, _ in _sent(calls)] == [
        "Back Door Left Open",
        "Back Door Left Open",
    ]


async def test_no_debounce_without_superseders(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An alert nothing supersedes notifies at once, as before."""
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)
    await _call(hass, "fire", LEFT_OPEN)
    assert len(calls) == 1


async def test_zero_debounce(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts, supersession_debounce=0)
    await _call(hass, "fire", OPEN)
    assert len(calls) == 1


async def test_superseded_by_and_event(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """superseded_by lists the firing superseders; _superseded announces them."""
    events = async_capture_events(hass, EVENT_SUPERSEDED)
    await _manual_pair(setup_alerts)
    assert hass.states.get(OPEN).attributes["superseded_by"] == []
    assert hass.states.get(LEFT_OPEN).attributes["supersedes"] == [OPEN]

    # Superseded while idle: shown, but not announced.
    await _call(hass, "fire", LEFT_OPEN)
    assert hass.states.get(OPEN).attributes["superseded_by"] == [LEFT_OPEN]
    assert events == []
    await _call(hass, "fire", OPEN)
    assert events == []
    await _call(hass, "dismiss", LEFT_OPEN)
    assert hass.states.get(OPEN).attributes["superseded_by"] == []

    # A superseder starting to fire while this one is firing is announced.
    await _call(hass, "fire", LEFT_OPEN)
    assert len(events) == 1
    assert events[0].data["entity_id"] == OPEN
    assert events[0].data["superseded_by"] == [LEFT_OPEN]
    assert events[0].data["old_state"] == events[0].data["new_state"] == "active"


async def test_transitive(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A supersedes B supersedes C: A firing suppresses C too."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_subentry("Back Door Left Open", supersedes=_supersedes(OPEN)),
        alert_subentry(
            "Back Door Open Overnight",
            priority="critical",
            supersedes=_supersedes(LEFT_OPEN),
        ),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire", OVERNIGHT)
    await _call(hass, "fire", LEFT_OPEN)
    await _call(hass, "fire", OPEN)
    await _tick(hass, freezer, 1)
    assert [title for title, _ in _sent(calls)] == ["Back Door Open Overnight"]
    assert hass.states.get(OPEN).attributes["superseded_by"] == [OVERNIGHT, LEFT_OPEN]


async def test_reminders_skipped_while_superseded(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Reminders keep their schedule, but aren't sent while superseded."""
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)
    await _call(hass, "fire", OPEN)
    await _tick(hass, freezer, 1)
    await _call(hass, "fire", LEFT_OPEN)
    calls.clear()

    # Open's 10-minute reminder is skipped; Left Open's own is sent.
    await _tick(hass, freezer, 10 * 60)
    assert [title for title, _ in _sent(calls)] == ["Back Door Left Open"]
    calls.clear()

    # Once Left Open ends, Open's reminders resume on its schedule (30 minutes).
    await _call(hass, "dismiss", LEFT_OPEN)
    calls.clear()
    await _tick(hass, freezer, 20 * 60)
    assert _sent(calls) == [
        ("Back Door Open", "Back Door Open is still firing (30 minutes).")
    ]


async def test_done_window_superseder_ends_first(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _tick(hass, freezer, 1)
    calls.clear()

    await _call(hass, "dismiss", LEFT_OPEN)
    await _tick(hass, freezer, 3)
    await _call(hass, "dismiss", OPEN)
    await _tick(hass, freezer, 10)
    assert [title for title, _ in _sent(calls)] == ["Back Door Left Open"]


async def test_done_window_superseded_ends_first(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _tick(hass, freezer, 1)
    calls.clear()

    await _call(hass, "dismiss", OPEN)
    assert calls == []
    await _tick(hass, freezer, 3)
    await _call(hass, "dismiss", LEFT_OPEN)
    await _tick(hass, freezer, 10)
    assert [title for title, _ in _sent(calls)] == ["Back Door Left Open"]


async def test_done_window_separate_ends(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Ending at different times sends both done notifications."""
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _tick(hass, freezer, 1)
    calls.clear()

    await _call(hass, "dismiss", OPEN)
    await _tick(hass, freezer, 6)
    assert _sent(calls) == [
        ("Back Door Open", "Back Door Open stopped firing after 1 second.")
    ]
    await _call(hass, "dismiss", LEFT_OPEN)
    assert [title for title, _ in _sent(calls)] == [
        "Back Door Open",
        "Back Door Left Open",
    ]


async def test_done_sent_without_a_firing_superseder(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    await _manual_pair(setup_alerts)
    await _call(hass, "fire", OPEN)
    await _tick(hass, freezer, 1)
    await _call(hass, "dismiss", OPEN)
    assert [title for title, _ in _sent(calls)] == ["Back Door Open", "Back Door Open"]


async def test_held_done_sent_on_unload(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A held done notification isn't lost when Alert Redux unloads."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_subentry("Back Door Left Open", supersedes=_supersedes(OPEN)),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _tick(hass, freezer, 1)
    await _call(hass, "dismiss", OPEN)
    calls.clear()
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert [title for title, _ in _sent(calls)] == ["Back Door Open"]


async def test_door_left_open_example(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Spec §8, §9.7: Door Open, then Door Left Open, then one "closed" message."""
    hass.states.async_set(DOOR, "off")
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        state_alert("Back Door Open", DOOR, done_message="Back door closed."),
        state_alert(
            "Back Door Left Open",
            DOOR,
            delay_on={"minutes": 5},
            supersedes=_supersedes(OPEN),
            done_message="Back door closed.",
        ),
        PHONE,
        options=DEFAULTS,
    )

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _tick(hass, freezer, 1)
    assert [title for title, _ in _sent(calls)] == ["Back Door Open"]

    await _tick(hass, freezer, 5 * 60)
    assert [title for title, _ in _sent(calls)] == [
        "Back Door Open",
        "Back Door Left Open",
    ]
    assert hass.states.get(OPEN).attributes["superseded_by"] == [LEFT_OPEN]

    # Open's 10-minute reminder is suppressed.
    await _tick(hass, freezer, 5 * 60)
    assert len(calls) == 2

    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    await _tick(hass, freezer, 10)
    assert _sent(calls)[2:] == [("Back Door Left Open", "Back door closed.")]
    assert hass.states.get(OPEN).state == "idle"
    assert hass.states.get(LEFT_OPEN).state == "idle"


async def test_editing_supersession_applies_in_place(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Adding a relationship by editing an alert updates superseded_by at once."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_subentry("Back Door Left Open", "left"),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire", LEFT_OPEN)
    assert hass.states.get(OPEN).attributes["superseded_by"] == []

    subentry = entry.subentries["left"]
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, "supersedes": _supersedes(OPEN)}
    )
    await hass.async_block_till_done()
    assert hass.states.get(OPEN).attributes["superseded_by"] == [LEFT_OPEN]


async def test_restart_keeps_suppression(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A reminder that fell due while down isn't sent if still superseded, and
    restoring doesn't announce supersession afresh."""
    calls = async_mock_service(hass, "notify", "phone")
    # The superseded alert comes first, so it's restored before its superseder.
    entry = await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_subentry("Back Door Left Open", supersedes=_supersedes(OPEN)),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _tick(hass, freezer, 1)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    calls.clear()

    # Down across both alerts' 10-minute reminders.
    freezer.tick(timedelta(minutes=15))
    events = async_capture_events(hass, EVENT_SUPERSEDED)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer, 1)
    assert [title for title, _ in _sent(calls)] == ["Back Door Left Open"]
    assert hass.states.get(OPEN).attributes["superseded_by"] == [LEFT_OPEN]
    assert events == []
