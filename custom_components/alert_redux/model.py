"""The runtime state of an alert and its transitions.

This module is deliberately free of Home Assistant dependencies: it holds what an
alert remembers (and persists across restarts) and applies the state machine of spec
§7, including the delay and no-data rules of condition alerts (§4.1, §4.4). The
entity wraps it, adding configuration checks, timers, events, and persistence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from .const import (
    CONF_NO_DATA_GRACE,
    CONF_STARTUP_DELAY,
    DEFAULT_NO_DATA_GRACE,
    DEFAULT_STARTUP_DELAY,
    AlertState,
    EndReason,
)


def to_timedelta(value: Any) -> timedelta | None:
    """Convert a stored duration (a duration selector's dict) to a timedelta."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return value
    if isinstance(value, dict):
        return timedelta(**{unit: float(amount) for unit, amount in value.items()})
    return timedelta(seconds=float(value))


@dataclass(slots=True)
class Settings:
    """The global defaults, from the config entry's options (spec §12.1)."""

    no_data_grace: timedelta = DEFAULT_NO_DATA_GRACE
    startup_delay: timedelta = DEFAULT_STARTUP_DELAY

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> Settings:
        """Read the settings from the entry's options, defaulting what's unset."""
        grace = to_timedelta(options.get(CONF_NO_DATA_GRACE))
        startup = to_timedelta(options.get(CONF_STARTUP_DELAY))
        return cls(
            no_data_grace=DEFAULT_NO_DATA_GRACE if grace is None else grace,
            startup_delay=DEFAULT_STARTUP_DELAY if startup is None else startup,
        )


@dataclass(frozen=True, slots=True)
class Transition:
    """What an applied change did."""

    old_state: AlertState
    new_state: AlertState
    fire_count: int
    # How long the firing lasted, and why it ended, for a transition that ends one.
    duration_seconds: float | None = None
    reason: EndReason | None = None


class Change(StrEnum):
    """A change found by evaluating a condition alert, each announced by an event."""

    FIRED = "fired"
    ENDED = "ended"
    NO_DATA = "no_data"


@dataclass(frozen=True, slots=True)
class Timing:
    """A condition alert's delays and no-data grace period."""

    delay_on: timedelta = timedelta(0)
    delay_off: timedelta = timedelta(0)
    no_data_grace: timedelta = timedelta(0)


@dataclass(slots=True)
class AlertRuntime:
    """Mutable, persisted state of one alert."""

    firing: bool = False
    acked: bool = False
    firing_since: datetime | None = None
    last_fired: datetime | None = None
    last_ended: datetime | None = None
    fire_count: int = 0
    fire_data: dict[str, Any] | None = None
    last_acked: datetime | None = None
    last_acked_by: str | None = None
    last_unacked: datetime | None = None
    last_unacked_by: str | None = None
    # Condition alerts: missing data, and the pending delay deadlines.
    no_data_since: datetime | None = None
    missing_inputs: list[str] = field(default_factory=list)
    delay_on_until: datetime | None = None
    delay_off_until: datetime | None = None
    # Not persisted: set while a restored alert waits for its first data, so that
    # the inputs still loading don't cancel the delays it was restored with.
    awaiting_data: bool = False

    @property
    def state(self) -> AlertState:
        """Return the alert's current state.

        A firing alert that has lost its data keeps its firing state during the
        grace period (spec §4.4); only a non-firing alert shows no_data.
        """
        if self.firing:
            return AlertState.ACK if self.acked else AlertState.ACTIVE
        if self.no_data_since is not None:
            return AlertState.NO_DATA
        return AlertState.IDLE

    def fire(self, now: datetime, data: dict[str, Any] | None = None) -> Transition:
        """Start firing, or record another fire of a firing alert (spec §4.3).

        Firing again keeps the acknowledgement: it's the same firing.
        """
        old = self.state
        if not self.firing:
            self.firing = True
            self.acked = False
            self.firing_since = now
            self.fire_count = 0
        self.fire_count += 1
        self.last_fired = now
        self.fire_data = data
        return Transition(old, self.state, self.fire_count)

    def end(self, now: datetime, reason: EndReason) -> Transition | None:
        """Stop firing; the acknowledgement clears with it (spec §6.1)."""
        if not self.firing:
            return None
        old = self.state
        fire_count = self.fire_count
        duration = (
            (now - self.firing_since).total_seconds() if self.firing_since else None
        )
        self.firing = False
        self.acked = False
        self.firing_since = None
        self.fire_count = 0
        self.fire_data = None
        self.last_ended = now
        return Transition(old, self.state, fire_count, duration, reason)

    def ack(self, now: datetime, user_id: str | None) -> Transition | None:
        """Acknowledge an active alert."""
        if self.state is not AlertState.ACTIVE:
            return None
        self.acked = True
        self.last_acked = now
        self.last_acked_by = user_id
        return Transition(AlertState.ACTIVE, self.state, self.fire_count)

    def unack(self, now: datetime, user_id: str | None) -> Transition | None:
        """Remove the acknowledgement from an acknowledged alert."""
        if self.state is not AlertState.ACK:
            return None
        self.acked = False
        self.last_unacked = now
        self.last_unacked_by = user_id
        return Transition(AlertState.ACK, self.state, self.fire_count)

    def await_data(self, now: datetime) -> None:
        """Wait for the first data after a restart or re-subscription (spec §15.3).

        The alert counts as having no data until its inputs report, but pending
        delays are kept: they're honoured if the condition still holds then.
        """
        self.awaiting_data = True
        if self.no_data_since is None:
            self.no_data_since = now

    def evaluate(
        self,
        condition: bool | None,
        missing_inputs: list[str],
        now: datetime,
        timing: Timing,
    ) -> list[tuple[Change, Transition]]:
        """Apply a condition result (None meaning no data), or a timer running out.

        Deadlines are kept in the runtime; the caller schedules a call at
        next_deadline() and evaluates the latest result again then.
        """
        if condition is None:
            return self._evaluate_no_data(missing_inputs, now, timing)

        self.awaiting_data = False
        self.no_data_since = None
        self.missing_inputs = []
        changes: list[tuple[Change, Transition]] = []
        if condition:
            self.delay_off_until = None
            if not self.firing:
                if self.delay_on_until is None:
                    self.delay_on_until = now + timing.delay_on
                if now >= self.delay_on_until:
                    self.delay_on_until = None
                    changes.append((Change.FIRED, self.fire(now)))
        else:
            self.delay_on_until = None
            if self.firing:
                if self.delay_off_until is None:
                    self.delay_off_until = now + timing.delay_off
                if now >= self.delay_off_until:
                    self.delay_off_until = None
                    transition = self.end(now, EndReason.RESOLVED)
                    assert transition is not None
                    changes.append((Change.ENDED, transition))
        return changes

    def _evaluate_no_data(
        self, missing_inputs: list[str], now: datetime, timing: Timing
    ) -> list[tuple[Change, Transition]]:
        changes: list[tuple[Change, Transition]] = []
        if not self.awaiting_data:
            # The condition didn't hold continuously, or can't be known to have
            # stopped holding: delays start afresh when data returns.
            self.delay_on_until = None
            self.delay_off_until = None
        self.missing_inputs = missing_inputs
        if self.no_data_since is None:
            old = self.state
            self.no_data_since = now
            changes.append(
                (Change.NO_DATA, Transition(old, self.state, self.fire_count))
            )
        if (grace_until := self.no_data_grace_until(timing)) and now >= grace_until:
            transition = self.end(now, EndReason.NO_DATA)
            assert transition is not None
            changes.append((Change.ENDED, transition))
        return changes

    def no_data_grace_until(self, timing: Timing) -> datetime | None:
        """Return when a firing alert without data stops firing, if it will."""
        if not self.firing or self.no_data_since is None:
            return None
        return self.no_data_since + timing.no_data_grace

    def next_deadline(self, timing: Timing) -> datetime | None:
        """Return when the alert next needs evaluating, if a timer is pending."""
        deadlines = [
            deadline
            for deadline in (
                self.delay_on_until,
                self.delay_off_until,
                self.no_data_grace_until(timing),
            )
            if deadline is not None
        ]
        return min(deadlines, default=None)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            name: value.isoformat() if isinstance(value, datetime) else value
            for name, value in (
                (f, getattr(self, f))
                for f in self.__dataclass_fields__
                if f not in _TRANSIENT_FIELDS
            )
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertRuntime:
        """Deserialize from storage, ignoring unknown keys."""
        runtime = cls()
        for name in cls.__dataclass_fields__:
            if name not in data or name in _TRANSIENT_FIELDS:
                continue
            value = data[name]
            if name in _DATETIME_FIELDS and value is not None:
                value = datetime.fromisoformat(value)
            setattr(runtime, name, value)
        return runtime


_DATETIME_FIELDS = frozenset(
    {
        "firing_since",
        "last_fired",
        "last_ended",
        "last_acked",
        "last_unacked",
        "no_data_since",
        "delay_on_until",
        "delay_off_until",
    }
)
_TRANSIENT_FIELDS = frozenset({"awaiting_data"})
