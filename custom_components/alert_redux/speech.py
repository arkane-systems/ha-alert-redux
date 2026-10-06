"""What voice commands hear and say (spec §14.1), without Home Assistant.

Matching a spoken alert name, understanding a spoken duration, and the English
replies. The intents in voice.py use them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta

from .messages import readable_duration

# The query names this many alerts, then says how many more there are.
QUERY_LIMIT = 5
# Asking which alert was meant names at most this many.
WHICH_LIMIT = 4


@dataclass(frozen=True, slots=True)
class Candidate:
    """An alert a voice command could mean: its entity ID, name, and aliases."""

    entity_id: str
    name: str
    aliases: tuple[str, ...] = ()

    def spoken_names(self) -> set[str]:
        """Return the alert's names as they'd be matched."""
        return {normalise(name) for name in (self.name, *self.aliases)} - {""}


def normalise(text: str) -> str:
    """Return a name as matched: lower case, no punctuation, no "the" or "alert".

    "The Back-Door alert" and "back door" are the same. An empty result means
    no alert was named: "acknowledge the alert" names none.
    """
    words = _without_courtesy(re.sub(r"[^\w\s]", " ", text.lower()).split())
    if words and words[0] == "the":
        words = words[1:]
    if words and words[-1] in ("alert", "alerts"):
        words = words[:-1]
    return " ".join(words)


def _without_courtesy(words: list[str]) -> list[str]:
    """Return words without a trailing "please", "thanks", or "thank you".

    A sentence's wildcard takes everything to the end, so "snooze the back door
    for ten minutes please" would otherwise end its duration with "please".
    """
    while words and words[-1] in ("please", "thanks"):
        words = words[:-1]
    if words[-2:] == ["thank", "you"]:
        words = words[:-2]
    return words


def match(spoken: str, candidates: Iterable[Candidate]) -> list[Candidate]:
    """Return the alerts a spoken name means.

    An exact match on a name or alias wins; failing that, the alerts whose name
    contains the spoken words. More than one means the name is ambiguous.
    """
    wanted = normalise(spoken)
    candidates = list(candidates)
    if not wanted:
        return []
    if exact := [c for c in candidates if wanted in c.spoken_names()]:
        return exact
    return [
        c
        for c in candidates
        if any(f" {wanted} " in f" {name} " for name in c.spoken_names())
    ]


_UNITS = {
    "second": 1,
    "seconds": 1,
    "sec": 1,
    "secs": 1,
    "minute": 60,
    "minutes": 60,
    "min": 60,
    "mins": 60,
    "hour": 3600,
    "hours": 3600,
    "hr": 3600,
    "hrs": 3600,
}

_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_NUMBER_WORDS = {word: value for value, word in enumerate(_ONES)} | {
    word: 20 + 10 * index for index, word in enumerate(_TENS)
}


def parse_duration(text: str) -> timedelta | None:
    """Return a spoken duration, or None if it can't be understood.

    Takes digits or English number words with seconds, minutes, or hours, and
    "an hour", "half an hour", "an hour and a half", "one and a half hours",
    "two hours thirty minutes", "twenty-five minutes", "1.5 hours".
    """
    text = re.sub(r"[^\w\s.]", " ", text.lower().replace("-", " "))
    # A dot only counts in a number ("1.5"): speech-to-text may end with one.
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    text = re.sub(r"\bhalf (?:an|a) hour\b", "30 minutes", text)
    text = re.sub(r"\bhalf (?:an|a) minute\b", "30 seconds", text)
    words = _without_courtesy(text.split())
    total = 0.0
    number: float | None = None
    last_unit: int | None = None
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        if word in ("and", "for"):
            continue
        if word in ("a", "an") and index < len(words) and words[index] == "half":
            index += 1
            word = "half"
        if word == "half":
            # "one and a half hours", or "an hour and a half".
            if number is not None:
                number += 0.5
            elif last_unit is not None:
                total += 0.5 * last_unit
            else:
                return None
        elif word in ("a", "an"):
            if number is not None:
                return None
            number = 1
        elif re.fullmatch(r"\d+(?:\.\d+)?", word):
            if number is not None:
                return None
            number = float(word)
        elif word in _NUMBER_WORDS:
            value = _NUMBER_WORDS[word]
            if number is None:
                number = value
            elif number >= 20 and number % 10 == 0 and 0 < value < 10:
                number += value  # "twenty five"
            else:
                return None
        elif word in _UNITS:
            if number is None:
                return None
            last_unit = _UNITS[word]
            total += number * last_unit
            number = None
        else:
            return None
    if number is not None or total <= 0:
        return None
    return timedelta(seconds=round(total))


def acknowledged(name: str) -> str:
    """Reply to an alert acknowledged."""
    return f"Acknowledged {name}."


def already_acknowledged(name: str) -> str:
    """Reply to acknowledging an alert that already is."""
    return f"{name} is already acknowledged."


def unacknowledged(name: str) -> str:
    """Reply to an acknowledgement removed."""
    return f"Removed the acknowledgement from {name}."


def not_acknowledged(name: str) -> str:
    """Reply to removing an acknowledgement an alert doesn't have."""
    return f"{name} isn't acknowledged."


def snoozed(name: str, duration: timedelta) -> str:
    """Reply to an alert snoozed."""
    return f"Snoozed {name} for {readable_duration(duration.total_seconds())}."


def not_firing(name: str) -> str:
    """Reply to acknowledging or snoozing an alert that isn't firing."""
    return f"{name} isn't firing."


def not_acknowledgeable(name: str) -> str:
    """Reply to acknowledging or snoozing an unacknowledgeable alert (§6.1)."""
    return f"{name} can't be acknowledged or snoozed."


def no_such_alert(spoken: str) -> str:
    """Reply to a name that matches no alert."""
    return f"I don't know an alert called {normalise(spoken)}."


def which_one(names: Sequence[str]) -> str:
    """Ask which of several alerts was meant; past a few, ask for more of it."""
    names = sorted(names)
    if len(names) > WHICH_LIMIT:
        shown = ", ".join(names[:WHICH_LIMIT])
        return f"{len(names)} alerts match that, like {shown}. Say more of the name."
    return f"Which one: {_join(names, 'or')}?"


def nothing_to(action: str) -> str:
    """Reply to a command with no name when no alert fits it."""
    return {
        "acknowledge": "No alert needs acknowledging.",
        "unacknowledge": "No alert is acknowledged.",
        "snooze": "No alert can be snoozed.",
    }[action]


def how_long() -> str:
    """Ask for a snooze duration that wasn't understood."""
    return "How long should I snooze it for?"


@dataclass(frozen=True, slots=True)
class Firing:
    """A firing alert, as the query reports it."""

    name: str
    acknowledged: bool
    snoozed_for: timedelta | None = None


def firing_alerts(alerts: Sequence[Firing], latched: Sequence[str] = ()) -> str:
    """Reply to "what alerts are firing?", given them highest priority first.

    latched names the alerts that stopped firing unacknowledged (spec §10),
    highest priority first; they follow.
    """
    reply = _firing(alerts)
    if latched:
        names = list(latched[:QUERY_LIMIT])
        if (more := len(latched) - QUERY_LIMIT) > 0:
            names.append(f"{more} more")
        verb = "hasn't" if len(latched) == 1 else "haven't"
        reply += (
            f" {_join(names, 'and')} stopped firing but {verb} been acknowledged."
        )
    return reply


def _firing(alerts: Sequence[Firing]) -> str:
    if not alerts:
        return "No alerts are firing."
    parts = [_describe(alert) for alert in alerts[:QUERY_LIMIT]]
    if (more := len(alerts) - QUERY_LIMIT) > 0:
        parts.append(f"{more} more")
    if len(alerts) == 1:
        return f"One alert is firing: {parts[0]}."
    return f"{len(alerts)} alerts are firing: {_join(parts, 'and', '; ')}."


def _describe(alert: Firing) -> str:
    if alert.snoozed_for is not None:
        seconds = max(alert.snoozed_for.total_seconds(), 1)
        return f"{alert.name}, snoozed for another {readable_duration(seconds)}"
    if alert.acknowledged:
        return f"{alert.name}, acknowledged"
    return alert.name


def _join(parts: Sequence[str], word: str, separator: str = ", ") -> str:
    if len(parts) < 2:
        return "".join(parts)
    # "A or B", "A, B, or C"; with another separator, always "A; and B".
    before = separator if len(parts) > 2 or separator != ", " else " "
    return f"{separator.join(parts[:-1])}{before}{word} {parts[-1]}"
