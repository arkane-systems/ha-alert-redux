"""The runtime state of an alert and its transitions.

This module is deliberately free of Home Assistant dependencies: it holds what an
alert remembers (and persists across restarts) and applies the state machine of spec
§7. The entity wraps it, adding configuration checks, events, and persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .const import AlertState


@dataclass(frozen=True, slots=True)
class Transition:
    """What an applied action changed."""

    old_state: AlertState
    new_state: AlertState
    fire_count: int
    # How long the firing lasted, for a transition that ends one.
    duration_seconds: float | None = None


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

    @property
    def state(self) -> AlertState:
        """Return the alert's current state."""
        if not self.firing:
            return AlertState.IDLE
        return AlertState.ACK if self.acked else AlertState.ACTIVE

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

    def end(self, now: datetime) -> Transition | None:
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
        return Transition(old, self.state, fire_count, duration)

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

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            name: value.isoformat() if isinstance(value, datetime) else value
            for name, value in (
                (f, getattr(self, f)) for f in self.__dataclass_fields__
            )
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertRuntime:
        """Deserialize from storage, ignoring unknown keys."""
        runtime = cls()
        for name in cls.__dataclass_fields__:
            if name not in data:
                continue
            value = data[name]
            if name in _DATETIME_FIELDS and value is not None:
                value = datetime.fromisoformat(value)
            setattr(runtime, name, value)
        return runtime


_DATETIME_FIELDS = frozenset(
    {"firing_since", "last_fired", "last_ended", "last_acked", "last_unacked"}
)
