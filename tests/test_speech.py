"""Tests for what voice commands hear and say (spec §14.1), without HA."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.alert_redux import speech
from custom_components.alert_redux.speech import Candidate, Firing

BACK = Candidate("alert_redux.back_door_open", "Back Door Open", ("Back door",))
GARAGE = Candidate("alert_redux.garage_door_open", "Garage Door Open")
SERVER = Candidate("alert_redux.server_room_hot", "Server Room Hot")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The Back-Door alert", "back door"),
        ("back door open", "back door open"),
        ("the alert", ""),
        ("alerts", ""),
        ("", ""),
        ("Server room, hot!", "server room hot"),
        ("the back door alert please", "back door"),
        ("back door, thank you", "back door"),
    ],
)
def test_normalise(text: str, expected: str) -> None:
    """Case, punctuation, a leading "the", and a trailing "alert" don't count."""
    assert speech.normalise(text) == expected


def test_match_exact_and_alias() -> None:
    """A name or alias matches exactly, whatever its case and punctuation."""
    candidates = [BACK, GARAGE, SERVER]
    assert speech.match("the back door open alert", candidates) == [BACK]
    assert speech.match("Back door", candidates) == [BACK]


def test_match_containment() -> None:
    """Failing an exact match, a name containing the words matches."""
    assert speech.match("server room", [BACK, GARAGE, SERVER]) == [SERVER]
    # Whole words only.
    assert speech.match("serve", [SERVER]) == []


def test_match_ambiguous_and_none() -> None:
    """Several matches are returned for the caller to ask; none is empty."""
    assert speech.match("door open", [BACK, GARAGE, SERVER]) == [BACK, GARAGE]
    assert speech.match("kitchen", [BACK, GARAGE]) == []
    assert speech.match("the alert", [BACK]) == []


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("30 minutes", 1800),
        ("thirty minutes", 1800),
        ("twenty-five minutes", 1500),
        ("an hour", 3600),
        ("1 hour", 3600),
        ("half an hour", 1800),
        ("an hour and a half", 5400),
        ("one and a half hours", 5400),
        ("1.5 hours", 5400),
        ("two hours thirty minutes", 9000),
        ("2 hours and 15 minutes", 8100),
        ("90 seconds", 90),
        ("a minute", 60),
        ("Ten mins", 600),
        ("ten minutes please", 600),
        ("an hour, thanks", 3600),
    ],
)
def test_parse_duration(text: str, seconds: int) -> None:
    """Spoken durations in digits or words."""
    assert speech.parse_duration(text) == timedelta(seconds=seconds)


@pytest.mark.parametrize(
    "text", ["", "a while", "30", "minutes", "a couple of minutes", "zero minutes"]
)
def test_parse_duration_not_understood(text: str) -> None:
    """Anything else isn't a duration."""
    assert speech.parse_duration(text) is None


def test_replies() -> None:
    """The replies name the alert."""
    assert speech.acknowledged("Back Door Open") == "Acknowledged Back Door Open."
    assert (
        speech.snoozed("Back Door Open", timedelta(minutes=30))
        == "Snoozed Back Door Open for 30 minutes."
    )
    assert speech.not_firing("Back Door Open") == "Back Door Open isn't firing."
    assert speech.which_one(["Garage", "Back"]) == "Which one: Back or Garage?"
    assert speech.which_one(["A", "C", "B"]) == "Which one: A, B, or C?"
    assert speech.which_one([f"Door {n}" for n in range(6)]) == (
        "6 alerts match that, like Door 0, Door 1, Door 2, Door 3. "
        "Say more of the name."
    )
    assert (
        speech.no_such_alert("the Kitchen Fire alert")
        == "I don't know an alert called kitchen fire."
    )


def test_firing_alerts() -> None:
    """The query names the alerts, and how they're acknowledged."""
    assert speech.firing_alerts([]) == "No alerts are firing."
    assert (
        speech.firing_alerts([Firing("A", True), Firing("B", True)])
        == "2 alerts are firing: A, acknowledged; and B, acknowledged."
    )
    assert (
        speech.firing_alerts([Firing("Back Door Open", False)])
        == "One alert is firing: Back Door Open."
    )
    assert speech.firing_alerts(
        [
            Firing("Server Room Hot", False),
            Firing("Back Door Open", True),
            Firing("Garage Door Open", True, timedelta(minutes=20)),
        ]
    ) == (
        "3 alerts are firing: Server Room Hot; Back Door Open, acknowledged; "
        "and Garage Door Open, snoozed for another 20 minutes."
    )


def test_firing_alerts_capped() -> None:
    """Past the limit, the rest are counted."""
    alerts = [Firing(f"Alert {n}", False) for n in range(7)]
    assert speech.firing_alerts(alerts).endswith("Alert 4; and 2 more.")
