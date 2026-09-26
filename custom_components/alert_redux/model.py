"""The runtime state of an alert and its transitions.

This module is deliberately free of Home Assistant dependencies: it holds what an
alert remembers (and persists across restarts) and applies the state machine of spec
§7, including the delay and no-data rules of condition alerts (§4.1, §4.4). The
entity wraps it, adding configuration checks, timers, events, and persistence.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from .const import (
    CONF_BUTTON_SNOOZE_DURATION,
    CONF_DEFAULT_GROUPS,
    CONF_DEFAULT_REMINDER_SCHEDULE,
    CONF_DEFAULT_THROTTLE,
    CONF_DONE_WINDOW,
    CONF_EVENT_DURATIONS,
    CONF_FALLBACK_GROUP,
    CONF_NO_DATA_GRACE,
    CONF_RETRY_TIMEOUT,
    CONF_SNOOZE_REMINDER_WINDOW,
    CONF_STARTUP_DELAY,
    CONF_SUPERSESSION_DEBOUNCE,
    DEFAULT_BUTTON_SNOOZE_DURATION,
    DEFAULT_DONE_WINDOW,
    DEFAULT_EVENT_DURATIONS,
    DEFAULT_NO_DATA_GRACE,
    DEFAULT_REMINDER_SCHEDULE,
    DEFAULT_RETRY_TIMEOUT,
    DEFAULT_SNOOZE_REMINDER_WINDOW,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_SUPERSESSION_DEBOUNCE,
    AlertState,
    EndReason,
    Priority,
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


@dataclass(frozen=True, slots=True)
class Throttle:
    """At most count on notifications in any window of minutes (spec §9.8)."""

    count: int
    minutes: float

    @property
    def window(self) -> timedelta:
        """Return the window as a timedelta."""
        return timedelta(minutes=self.minutes)

    @classmethod
    def from_stored(cls, value: Any) -> Throttle | None:
        """Return a throttle from its stored form, [count, minutes]; empty is none."""
        if not value:
            return None
        count, minutes = value
        return cls(int(count), minutes)

    def to_stored(self) -> list[float]:
        """Return the throttle in its stored form."""
        return [self.count, self.minutes]


def parse_throttle(count: Any, minutes: Any) -> Throttle | None:
    """Return a throttle from a form's two numbers; neither set means none.

    Raises ValueError unless both are set, the count is a whole number of at least
    one, and the minutes are positive.
    """
    if count in (None, "") and minutes in (None, ""):
        return None
    if count in (None, "") or minutes in (None, ""):
        raise ValueError("a throttle needs both a count and minutes")
    count, minutes = float(count), float(minutes)
    if count < 1 or not count.is_integer() or minutes <= 0:
        raise ValueError("invalid throttle")
    return Throttle(int(count), int(minutes) if minutes.is_integer() else minutes)


@dataclass(slots=True)
class Settings:
    """The global defaults, from the config entry's options (spec §12.1)."""

    no_data_grace: timedelta = DEFAULT_NO_DATA_GRACE
    startup_delay: timedelta = DEFAULT_STARTUP_DELAY
    # Notifier group IDs; empty means none configured, so the fallback is used.
    default_groups: tuple[str, ...] = ()
    # Minutes between reminders (spec §9.6).
    reminder_schedule: tuple[float, ...] = DEFAULT_REMINDER_SCHEDULE
    # A notifier group ID; None means the built-in persistent fallback (§9.4).
    fallback_group: str | None = None
    # How long a failing notifier member is retried (spec §15.2).
    retry_timeout: timedelta = DEFAULT_RETRY_TIMEOUT
    # Event alerts' durations when they have none of their own (spec §4.2).
    event_durations: dict[Priority, timedelta] = field(
        default_factory=lambda: dict(DEFAULT_EVENT_DURATIONS)
    )
    # When a snooze ends, a reminder slot closer than this makes the immediate
    # reminder unnecessary (spec §6.2).
    snooze_reminder_window: timedelta = DEFAULT_SNOOZE_REMINDER_WINDOW
    # A superseded alert's on notification waits this long for a superseding
    # alert to fire (spec §8.1), and its done notification this long for one to
    # end (§9.7).
    supersession_debounce: timedelta = DEFAULT_SUPERSESSION_DEBOUNCE
    done_window: timedelta = DEFAULT_DONE_WINDOW
    # How long a notification's Snooze button snoozes for (spec §9.11).
    button_snooze_duration: timedelta = DEFAULT_BUTTON_SNOOZE_DURATION
    # The default throttle; None means none (spec §9.8).
    throttle: Throttle | None = None

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> Settings:
        """Read the settings from the entry's options, defaulting what's unset."""
        grace = to_timedelta(options.get(CONF_NO_DATA_GRACE))
        startup = to_timedelta(options.get(CONF_STARTUP_DELAY))
        schedule = options.get(CONF_DEFAULT_REMINDER_SCHEDULE)
        retry = to_timedelta(options.get(CONF_RETRY_TIMEOUT))
        durations = options.get(CONF_EVENT_DURATIONS) or {}
        window = to_timedelta(options.get(CONF_SNOOZE_REMINDER_WINDOW))
        debounce = to_timedelta(options.get(CONF_SUPERSESSION_DEBOUNCE))
        done_window = to_timedelta(options.get(CONF_DONE_WINDOW))
        button_snooze = to_timedelta(options.get(CONF_BUTTON_SNOOZE_DURATION))
        return cls(
            no_data_grace=DEFAULT_NO_DATA_GRACE if grace is None else grace,
            startup_delay=DEFAULT_STARTUP_DELAY if startup is None else startup,
            default_groups=tuple(options.get(CONF_DEFAULT_GROUPS, ())),
            reminder_schedule=(
                DEFAULT_REMINDER_SCHEDULE if schedule is None else tuple(schedule)
            ),
            fallback_group=options.get(CONF_FALLBACK_GROUP) or None,
            retry_timeout=DEFAULT_RETRY_TIMEOUT if not retry else retry,
            event_durations={
                priority: to_timedelta(durations.get(priority)) or default
                for priority, default in DEFAULT_EVENT_DURATIONS.items()
            },
            snooze_reminder_window=(
                DEFAULT_SNOOZE_REMINDER_WINDOW if window is None else window
            ),
            supersession_debounce=(
                DEFAULT_SUPERSESSION_DEBOUNCE if debounce is None else debounce
            ),
            done_window=DEFAULT_DONE_WINDOW if done_window is None else done_window,
            # A zero snooze would do nothing, so it means the default too.
            button_snooze_duration=button_snooze or DEFAULT_BUTTON_SNOOZE_DURATION,
            throttle=Throttle.from_stored(options.get(CONF_DEFAULT_THROTTLE)),
        )

    def update(self, other: Settings) -> None:
        """Take another set of settings, in place: entities hold this object."""
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(other, name))


def parse_schedule(text: str) -> tuple[float, ...]:
    """Parse a reminder schedule typed as minutes, e.g. "10, 20, 30, 60".

    Blank means no reminders. Raises ValueError unless every interval is a positive
    number.
    """
    schedule = tuple(
        float(item) for item in text.replace(";", ",").split(",") if item.strip()
    )
    if any(minutes <= 0 for minutes in schedule):
        raise ValueError("reminder intervals must be positive")
    return tuple(
        int(minutes) if minutes.is_integer() else minutes for minutes in schedule
    )


def format_schedule(schedule: Sequence[float]) -> str:
    """Return a reminder schedule as the text parse_schedule reads."""
    return ", ".join(f"{minutes:g}" for minutes in schedule)


def reminder_slots(
    firing_since: datetime, schedule: Sequence[float]
) -> Iterator[datetime]:
    """Yield the reminder times of a firing (spec §9.6).

    The gaps follow the schedule, and the last one repeats.
    """
    if not schedule:
        return
    slot = firing_since
    for minutes in schedule:
        slot += timedelta(minutes=minutes)
        yield slot
    while True:
        slot += timedelta(minutes=schedule[-1])
        yield slot


def next_reminder_slot(
    firing_since: datetime, schedule: Sequence[float], after: datetime
) -> datetime | None:
    """Return the first reminder slot of a firing that is later than after."""
    if not schedule:
        return None
    total = timedelta(minutes=sum(schedule))
    last = timedelta(minutes=schedule[-1])
    start = firing_since
    if after >= firing_since + total:
        # Skip whole repeats of the last interval rather than stepping through them.
        repeats = (after - firing_since - total) // last
        start = firing_since + repeats * last
    return next(slot for slot in reminder_slots(start, schedule) if slot > after)


def snooze_end_reminder(
    firing_since: datetime,
    schedule: Sequence[float],
    now: datetime,
    window: timedelta,
) -> tuple[bool, datetime | None]:
    """Apply the snooze-end reminder rule (spec §6.2).

    Return whether to send a reminder now, and when the next one is due: the next
    slot of the original schedule. The immediate reminder is skipped when that
    slot is less than window away. An alert without reminders gets neither.
    """
    slot = next_reminder_slot(firing_since, schedule, now)
    if slot is None:
        return False, None
    return slot - now >= window, slot


class ThrottleDecision(StrEnum):
    """What to do with an on notification, by the throttle (spec §9.8)."""

    SEND = "send"
    # Send it, marked: it starts throttling.
    START = "start"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class ThrottleSummary:
    """What was held while an alert was throttled, for the summary (spec §9.8).

    held_fires counts the on notifications held, the latest at last_held; ended,
    duration_seconds, and end_reason describe the latest held done notification.
    """

    held_fires: int = 0
    last_held: datetime | None = None
    ended: datetime | None = None
    duration_seconds: float | None = None
    end_reason: str | None = None

    @property
    def anything_held(self) -> bool:
        """Return whether anything was held, so that a summary is due."""
        return self.held_fires > 0 or self.ended is not None


@dataclass(frozen=True, slots=True)
class Reading:
    """A threshold alert's value and limits (spec §4.1); a limit may be unset."""

    value: float
    minimum: float | None = None
    maximum: float | None = None


def threshold_holds(reading: Reading, hysteresis: float, firing: bool) -> bool:
    """Return whether a threshold alert's condition holds.

    It starts to hold when the value goes above the maximum or below the minimum,
    and a firing carries on until the value is back inside by the hysteresis.
    """
    value, low, high = reading.value, reading.minimum, reading.maximum
    if not firing:
        return (high is not None and value > high) or (low is not None and value < low)
    back_inside = (high is None or value <= high - hysteresis) and (
        low is None or value >= low + hysteresis
    )
    return not back_inside


@dataclass(frozen=True, slots=True)
class OnOffSides:
    """Which criteria an on/off alert's sides have: a template, a trigger, or both."""

    on_template: bool
    on_trigger: bool
    off_template: bool
    off_trigger: bool


@dataclass(frozen=True, slots=True)
class Transition:
    """What an applied change did."""

    old_state: AlertState
    new_state: AlertState
    fire_count: int
    # How long the firing lasted, and why it ended, for a transition that ends one.
    duration_seconds: float | None = None
    reason: EndReason | None = None
    # The fire data of the firing that ended, for the done message.
    fire_data: dict[str, Any] | None = None


class Change(StrEnum):
    """A change to an alert, each announced by an event (spec §11.3)."""

    FIRED = "fired"
    ENDED = "ended"
    NO_DATA = "no_data"
    ACKED = "acked"
    UNACKED = "unacked"
    SNOOZED = "snoozed"
    SNOOZE_EXPIRED = "snooze_expired"
    DISABLED = "disabled"
    ENABLED = "enabled"
    DATA_RESTORED = "data_restored"


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
    # While snoozed (acknowledged until then; spec §6.2), and the last snooze.
    snoozed_until: datetime | None = None
    last_snoozed: datetime | None = None
    last_snoozed_by: str | None = None
    # Disabled, or suspended until disabled_until (spec §6.3, §6.4).
    disabled: bool = False
    disabled_until: datetime | None = None
    last_disabled: datetime | None = None
    last_disabled_by: str | None = None
    last_enabled: datetime | None = None
    last_enabled_by: str | None = None
    # Condition alerts: missing data, and the pending delay deadlines.
    no_data_since: datetime | None = None
    missing_inputs: list[str] = field(default_factory=list)
    # Whether losing the data was announced, so that its return is too.
    no_data_announced: bool = False
    delay_on_until: datetime | None = None
    delay_off_until: datetime | None = None
    # When the next reminder is due, while firing and unacknowledged (spec §9.6).
    next_reminder: datetime | None = None
    # Event alerts: when the current firing's duration runs out (spec §4.2).
    event_expires: datetime | None = None
    # On/off alerts' edges (spec §4.1). A template-only side counts only a
    # false-to-true change: it's armed once it has been seen false. Unknown counts
    # as false, so a new alert is armed. A side with a trigger is latched by the
    # trigger firing, until it's used or its template turns false.
    on_armed: bool = True
    off_armed: bool = True
    on_latched: bool = False
    off_latched: bool = False
    # Pre-acknowledgements (spec §8.3), by the unique ID of the superseded alert
    # that propagated them: the pre-snooze deadline, or None for a plain one.
    pre_acks: dict[str, datetime | None] = field(default_factory=dict)
    # Throttling (spec §9.8): the latest on notifications (sent or held), as many
    # as the throttle's count; while throttled, since when, and what was held.
    throttle_fires: list[datetime] = field(default_factory=list)
    throttled_since: datetime | None = None
    throttle_held: int = 0
    throttle_last_held: datetime | None = None
    throttle_ended: datetime | None = None
    throttle_ended_seconds: float | None = None
    throttle_end_reason: str | None = None
    # Not persisted: set while a restored alert waits for its first data, so that
    # the inputs still loading don't cancel the delays it was restored with.
    awaiting_data: bool = False

    @property
    def state(self) -> AlertState:
        """Return the alert's current state.

        A firing alert that has lost its data keeps its firing state during the
        grace period (spec §4.4); only a non-firing alert shows no_data.
        """
        if self.disabled:
            return AlertState.DISABLED
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

    def fire_event(
        self, now: datetime, data: dict[str, Any] | None, duration: timedelta
    ) -> Transition:
        """Fire an event alert, or fire it again, running its duration from now.

        Firing again restarts the duration and keeps the acknowledgement (§4.2).
        """
        transition = self.fire(now, data)
        self.event_expires = now + duration
        return transition

    def end(self, now: datetime, reason: EndReason) -> Transition | None:
        """Stop firing; the acknowledgement clears with it (spec §6.1)."""
        if not self.firing:
            return None
        old = self.state
        fire_count = self.fire_count
        fire_data = self.fire_data
        duration = (
            (now - self.firing_since).total_seconds() if self.firing_since else None
        )
        self.firing = False
        self.acked = False
        self.snoozed_until = None
        self.firing_since = None
        self.fire_count = 0
        self.fire_data = None
        self.next_reminder = None
        self.event_expires = None
        self.last_ended = now
        return Transition(old, self.state, fire_count, duration, reason, fire_data)

    def ack(self, now: datetime, user_id: str | None) -> Transition | None:
        """Acknowledge an active alert, or make a snoozed alert's ack permanent.

        A snoozed alert then stays acknowledged until the firing ends.
        """
        old = self.state
        if old is not AlertState.ACTIVE and not (
            old is AlertState.ACK and self.snoozed_until is not None
        ):
            return None
        self.acked = True
        self.snoozed_until = None
        self.next_reminder = None
        self.last_acked = now
        self.last_acked_by = user_id
        return Transition(old, self.state, self.fire_count)

    def unack(self, now: datetime, user_id: str | None) -> Transition | None:
        """Remove the acknowledgement (and any snooze) from an acknowledged alert."""
        if self.state is not AlertState.ACK:
            return None
        self.acked = False
        self.snoozed_until = None
        self.last_unacked = now
        self.last_unacked_by = user_id
        return Transition(AlertState.ACK, self.state, self.fire_count)

    def snooze(
        self, now: datetime, until: datetime, user_id: str | None
    ) -> list[tuple[Change, Transition]]:
        """Acknowledge a firing alert until a deadline (spec §6.2).

        An active alert is acknowledged as well; an acknowledged one, snoozed or
        not, just gets the new deadline, even if it's sooner.
        """
        old = self.state
        if old not in (AlertState.ACTIVE, AlertState.ACK):
            return []
        self.snoozed_until = until
        self.last_snoozed = now
        self.last_snoozed_by = user_id
        if old is AlertState.ACK:
            return [(Change.SNOOZED, Transition(old, old, self.fire_count))]
        self.acked = True
        self.next_reminder = None
        self.last_acked = now
        self.last_acked_by = user_id
        transition = Transition(old, self.state, self.fire_count)
        return [(Change.SNOOZED, transition), (Change.ACKED, transition)]

    def snooze_expire(self, now: datetime) -> list[tuple[Change, Transition]]:
        """End a snooze whose deadline has passed: the alert is active again.

        The caller plans the reminders by the snooze-end rule.
        """
        if (
            self.state is not AlertState.ACK
            or self.snoozed_until is None
            or now < self.snoozed_until
        ):
            return []
        self.acked = False
        self.snoozed_until = None
        self.last_unacked = now
        self.last_unacked_by = None
        transition = Transition(AlertState.ACK, self.state, self.fire_count)
        return [(Change.SNOOZE_EXPIRED, transition), (Change.UNACKED, transition)]

    def disable(
        self, now: datetime, user_id: str | None, until: datetime | None = None
    ) -> list[tuple[Change, Transition]]:
        """Disable the alert, until a time to suspend it (spec §6.3, §6.4).

        A firing ends, with reason disabled, and everything about it and about
        evaluating the condition is cleared. The latest call wins: suspending a
        disabled alert sets the new time, and disabling a suspended one makes it
        indefinite. Disabling an indefinitely disabled alert does nothing.
        """
        if self.disabled and self.disabled_until is None and until is None:
            return []
        old = self.state
        changes: list[tuple[Change, Transition]] = []
        if (ended := self.end(now, EndReason.DISABLED)) is not None:
            changes.append((Change.ENDED, ended))
        self.disabled = True
        self.disabled_until = until
        self.last_disabled = now
        self.last_disabled_by = user_id
        self.no_data_since = None
        self.missing_inputs = []
        self.no_data_announced = False
        self.delay_on_until = None
        self.delay_off_until = None
        self.on_latched = False
        self.off_latched = False
        self.awaiting_data = False
        changes.append((Change.DISABLED, Transition(old, self.state, 0)))
        return changes

    def enable(
        self, now: datetime, user_id: str | None, *, awaits_data: bool
    ) -> list[tuple[Change, Transition]]:
        """Enable a disabled or suspended alert, starting from scratch (§6.3).

        An alert with inputs awaits data; on/off edges are armed again, as for
        a new alert.
        """
        if not self.disabled:
            return []
        self.disabled = False
        self.disabled_until = None
        self.last_enabled = now
        self.last_enabled_by = user_id
        self.on_armed = True
        self.off_armed = True
        if awaits_data:
            self.await_data(now)
        return [(Change.ENABLED, Transition(AlertState.DISABLED, self.state, 0))]

    def suspension_ended(
        self, now: datetime, *, awaits_data: bool
    ) -> list[tuple[Change, Transition]]:
        """Enable a suspended alert once its time has come."""
        if (
            not self.disabled
            or self.disabled_until is None
            or now < self.disabled_until
        ):
            return []
        return self.enable(now, None, awaits_data=awaits_data)

    def live_pre_acks(self, now: datetime) -> dict[str, datetime | None]:
        """Return the pre-acknowledgements in force: pre-snoozes not yet run out."""
        return {
            source: until
            for source, until in self.pre_acks.items()
            if until is None or until > now
        }

    def pre_ack_deadline(self, now: datetime) -> datetime | None:
        """Return the pre-snooze deadline in force, or None.

        A plain pre-acknowledgement beats a pre-snooze, and among pre-snoozes
        the latest deadline wins.
        """
        live = self.live_pre_acks(now)
        if not live or None in live.values():
            return None
        return max(until for until in live.values() if until is not None)

    def prune_pre_acks(self, now: datetime) -> bool:
        """Forget pre-snoozes that have run out; return whether any were."""
        live = self.live_pre_acks(now)
        if len(live) == len(self.pre_acks):
            return False
        self.pre_acks = live
        return True

    def next_pre_ack_expiry(self) -> datetime | None:
        """Return when the next pre-snooze runs out, if any will."""
        return min(
            (until for until in self.pre_acks.values() if until is not None),
            default=None,
        )

    def apply_pre_ack(
        self, now: datetime, sources: Collection[str]
    ) -> list[str] | None:
        """Start a new firing acknowledged, if it has been pre-acknowledged (§8.3).

        Only pre-acknowledgements from sources (the superseded alerts that are
        still acknowledged) count. A pre-snooze makes the acknowledgement a
        snooze until its deadline. Return the pre-acknowledging alerts, or None.
        """
        live = {
            source: until
            for source, until in self.live_pre_acks(now).items()
            if source in sources
        }
        if not live or self.state is not AlertState.ACTIVE:
            return None
        self.acked = True
        self.snoozed_until = (
            None
            if None in live.values()
            else max(until for until in live.values() if until is not None)
        )
        self.next_reminder = None
        self.last_acked = now
        self.last_acked_by = None
        return sorted(live)

    def throttle_note(
        self, now: datetime, throttle: Throttle | None
    ) -> ThrottleDecision:
        """Count an on notification, and decide whether to send it (spec §9.8).

        Held ones count too. The one that brings the count in the window up to the
        throttle's count is sent, marked, and starts throttling; while throttled,
        they're held.
        """
        if throttle is None:
            self.throttle_fires = []
            return ThrottleDecision.SEND
        self.throttle_fires = [*self.throttle_fires, now][-throttle.count :]
        if self.throttled_since is not None:
            self.throttle_held += 1
            self.throttle_last_held = now
            return ThrottleDecision.HOLD
        if (
            len(self.throttle_fires) >= throttle.count
            and self.throttle_fires[0] > now - throttle.window
        ):
            self.throttled_since = now
            return ThrottleDecision.START
        return ThrottleDecision.SEND

    def throttle_hold_done(self, now: datetime, transition: Transition) -> bool:
        """Hold a done notification while throttled; return whether it was."""
        if self.throttled_since is None:
            return False
        self.throttle_ended = now
        self.throttle_ended_seconds = transition.duration_seconds
        self.throttle_end_reason = transition.reason
        return True

    def throttle_end_due(self, throttle: Throttle | None) -> datetime | None:
        """Return when throttling ends: when fewer than count on notifications
        are left in the window. Without a throttle, or with a smaller count
        than it has seen, it's due at once."""
        if self.throttled_since is None:
            return None
        if throttle is None or len(self.throttle_fires) < throttle.count:
            return self.throttled_since
        return self.throttle_fires[-throttle.count] + throttle.window

    def throttle_expire(
        self, now: datetime, throttle: Throttle | None
    ) -> ThrottleSummary | None:
        """End throttling if it's due, returning what was held; else None."""
        due = self.throttle_end_due(throttle)
        if due is None or now < due:
            return None
        summary = ThrottleSummary(
            self.throttle_held,
            self.throttle_last_held,
            self.throttle_ended,
            self.throttle_ended_seconds,
            self.throttle_end_reason,
        )
        self.throttled_since = None
        self.throttle_held = 0
        self.throttle_last_held = None
        self.throttle_ended = None
        self.throttle_ended_seconds = None
        self.throttle_end_reason = None
        return summary

    def plan_reminder(self, schedule: Sequence[float], now: datetime) -> None:
        """Set the next reminder: the next slot after now (spec §6.2).

        Slots are counted from when the firing started. There's none unless the
        alert is firing and unacknowledged.
        """
        if self.state is not AlertState.ACTIVE or self.firing_since is None:
            self.next_reminder = None
        else:
            self.next_reminder = next_reminder_slot(self.firing_since, schedule, now)

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
        if self.disabled:
            return []
        if condition is None:
            return self._evaluate_no_data(missing_inputs, now, timing)

        changes: list[tuple[Change, Transition]] = []
        old = self.state
        self.awaiting_data = False
        self.no_data_since = None
        self.missing_inputs = []
        if self.no_data_announced:
            # Only a loss that was announced; waiting at startup fires nothing.
            self.no_data_announced = False
            changes.append(
                (Change.DATA_RESTORED, Transition(old, self.state, self.fire_count))
            )
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
            self.no_data_announced = True
            changes.append(
                (Change.NO_DATA, Transition(old, self.state, self.fire_count))
            )
        if (grace_until := self.no_data_grace_until(timing)) and now >= grace_until:
            transition = self.end(now, EndReason.NO_DATA)
            assert transition is not None
            changes.append((Change.ENDED, transition))
        return changes

    def on_off_pulse(self, side: str) -> None:
        """Record an on/off alert's trigger firing on one side.

        It counts only on the side that can change the state (on while not firing,
        off while firing). The caller checks that side's template, if any, is true.
        """
        if side == "on" and not self.firing:
            self.on_latched = True
        elif side == "off" and self.firing:
            self.off_latched = True

    def on_off_condition(
        self, sides: OnOffSides, on: bool | None, off: bool | None
    ) -> bool | None:
        """Return an on/off alert's condition as a level, for evaluate().

        on and off are the sides' template results (None: no data, or no template).
        Not firing, the condition holds once the on side has become true; firing,
        it holds until the off side becomes true. Only the side that can change
        the state counts for missing data. The caller disarms the on side when the
        alert fires (on_off_fired).
        """
        if on is False:
            self.on_armed = True
            self.on_latched = False
        elif on is True and self.firing:
            self.on_armed = False
        if off is False:
            self.off_armed = True
            self.off_latched = False
        elif off is True and not self.firing:
            self.off_armed = False

        if not self.firing:
            if sides.on_template and on is None:
                return None
            if sides.on_trigger:
                return self.on_latched
            return on is True and self.on_armed
        if sides.off_template and off is None:
            return None
        if sides.off_trigger:
            return not self.off_latched
        return not (off is True and self.off_armed)

    def on_off_fired(self) -> None:
        """Use up the on side's edge: it must change again to fire again."""
        self.on_armed = False
        self.on_latched = False
        self.off_latched = False

    def on_off_ended(self) -> None:
        """Use up the off side's edge."""
        self.off_latched = False
        self.on_latched = False

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
        data = {
            name: value.isoformat() if isinstance(value, datetime) else value
            for name, value in (
                (f, getattr(self, f))
                for f in self.__dataclass_fields__
                if f not in _TRANSIENT_FIELDS
            )
        }
        data["pre_acks"] = {
            source: until.isoformat() if until else None
            for source, until in self.pre_acks.items()
        }
        data["throttle_fires"] = [fired.isoformat() for fired in self.throttle_fires]
        return data

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
            elif name == "pre_acks":
                value = {
                    source: datetime.fromisoformat(until) if until else None
                    for source, until in (value or {}).items()
                }
            elif name == "throttle_fires":
                value = [datetime.fromisoformat(fired) for fired in value or []]
            setattr(runtime, name, value)
        return runtime


_DATETIME_FIELDS = frozenset(
    {
        "firing_since",
        "last_fired",
        "last_ended",
        "last_acked",
        "last_unacked",
        "snoozed_until",
        "last_snoozed",
        "disabled_until",
        "last_disabled",
        "last_enabled",
        "no_data_since",
        "delay_on_until",
        "delay_off_until",
        "next_reminder",
        "event_expires",
        "throttled_since",
        "throttle_last_held",
        "throttle_ended",
    }
)
_TRANSIENT_FIELDS = frozenset({"awaiting_data"})
