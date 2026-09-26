"""Tests for the alert state machine, independent of Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.alert_redux.const import AlertState, EndReason
from custom_components.alert_redux.model import (
    AlertRuntime,
    Change,
    OnOffSides,
    Reading,
    Timing,
    format_schedule,
    next_reminder_slot,
    parse_schedule,
    reminder_slots,
    snooze_end_reminder,
    threshold_holds,
)

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_fire_from_idle() -> None:
    runtime = AlertRuntime()
    transition = runtime.fire(T0, {"a": 1})
    assert (transition.old_state, transition.new_state) == (
        AlertState.IDLE,
        AlertState.ACTIVE,
    )
    assert runtime.firing_since == runtime.last_fired == T0
    assert runtime.fire_count == transition.fire_count == 1
    assert runtime.fire_data == {"a": 1}


def test_refire_keeps_ack_and_start() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.ack(T0, "user")
    later = T0 + timedelta(minutes=5)
    transition = runtime.fire(later, {"b": 2})
    assert transition.old_state == transition.new_state == AlertState.ACK
    assert runtime.firing_since == T0
    assert runtime.last_fired == later
    assert runtime.fire_count == 2
    assert runtime.fire_data == {"b": 2}


def test_end_clears_firing() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0, {"a": 1})
    runtime.fire(T0)
    runtime.ack(T0, None)
    transition = runtime.end(T0 + timedelta(seconds=90), EndReason.DISMISSED)
    assert transition is not None
    assert (transition.old_state, transition.new_state) == (
        AlertState.ACK,
        AlertState.IDLE,
    )
    assert transition.fire_count == 2
    assert transition.duration_seconds == 90
    assert transition.reason is EndReason.DISMISSED
    assert runtime.state is AlertState.IDLE
    assert not runtime.acked
    assert runtime.firing_since is None
    assert runtime.fire_count == 0
    assert runtime.fire_data is None
    assert runtime.last_ended == T0 + timedelta(seconds=90)


def test_new_firing_starts_unacknowledged() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.ack(T0, None)
    runtime.end(T0, EndReason.RESOLVED)
    assert runtime.fire(T0).new_state is AlertState.ACTIVE


def test_ack_and_unack_record_who() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    assert runtime.ack(T0, "alice").new_state is AlertState.ACK
    assert (runtime.last_acked, runtime.last_acked_by) == (T0, "alice")
    assert runtime.unack(T0, "bob").new_state is AlertState.ACTIVE
    assert (runtime.last_unacked, runtime.last_unacked_by) == (T0, "bob")


def test_noops() -> None:
    runtime = AlertRuntime()
    assert runtime.end(T0, EndReason.RESOLVED) is None
    assert runtime.ack(T0, None) is None
    assert runtime.unack(T0, None) is None
    runtime.fire(T0)
    assert runtime.unack(T0, None) is None
    runtime.ack(T0, None)
    assert runtime.ack(T0, None) is None


def test_round_trip() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0, {"a": [1, 2]})
    runtime.ack(T0 + timedelta(seconds=1), "alice")
    data = runtime.to_dict()
    assert data["firing_since"] == T0.isoformat()
    assert AlertRuntime.from_dict(data) == runtime
    assert AlertRuntime.from_dict({"unknown": 1}) == AlertRuntime()


def test_round_trip_leaves_out_transient_fields() -> None:
    runtime = AlertRuntime()
    runtime.await_data(T0)
    runtime.missing_inputs = ["binary_sensor.door"]
    runtime.delay_on_until = T0
    data = runtime.to_dict()
    assert "awaiting_data" not in data
    restored = AlertRuntime.from_dict(data)
    assert restored.no_data_since == restored.delay_on_until == T0
    assert restored.missing_inputs == ["binary_sensor.door"]
    assert not restored.awaiting_data


def test_phase_1_record_loads() -> None:
    """A record saved by 0.1.0 has none of the condition fields."""
    runtime = AlertRuntime.from_dict(
        {"firing": True, "firing_since": T0.isoformat(), "fire_count": 1}
    )
    assert runtime.state is AlertState.ACTIVE
    assert runtime.no_data_since is None
    assert runtime.missing_inputs == []


# Condition evaluation (spec §4.1, §4.4).

DELAYS = Timing(
    delay_on=timedelta(minutes=5),
    delay_off=timedelta(minutes=1),
    no_data_grace=timedelta(minutes=10),
)


def _changes(changes: list) -> list[tuple[Change, AlertState, AlertState]]:
    return [(change, t.old_state, t.new_state) for change, t in changes]


def test_fires_and_ends_without_delays() -> None:
    runtime = AlertRuntime()
    assert _changes(runtime.evaluate(True, [], T0, Timing())) == [
        (Change.FIRED, AlertState.IDLE, AlertState.ACTIVE)
    ]
    assert runtime.evaluate(True, [], T0, Timing()) == []
    changes = runtime.evaluate(False, [], T0 + timedelta(seconds=30), Timing())
    assert _changes(changes) == [(Change.ENDED, AlertState.ACTIVE, AlertState.IDLE)]
    assert changes[0][1].reason is EndReason.RESOLVED
    assert changes[0][1].duration_seconds == 30
    assert runtime.evaluate(False, [], T0, Timing()) == []


def test_delay_on() -> None:
    runtime = AlertRuntime()
    assert runtime.evaluate(True, [], T0, DELAYS) == []
    assert runtime.delay_on_until == T0 + timedelta(minutes=5)
    assert runtime.next_deadline(DELAYS) == T0 + timedelta(minutes=5)
    # Still pending before the deadline; a repeated result doesn't restart it.
    assert runtime.evaluate(True, [], T0 + timedelta(minutes=4), DELAYS) == []
    assert runtime.delay_on_until == T0 + timedelta(minutes=5)
    fired_at = T0 + timedelta(minutes=5)
    assert _changes(runtime.evaluate(True, [], fired_at, DELAYS)) == [
        (Change.FIRED, AlertState.IDLE, AlertState.ACTIVE)
    ]
    assert runtime.firing_since == fired_at
    assert runtime.delay_on_until is None
    assert runtime.next_deadline(DELAYS) is None


def test_delay_on_needs_the_condition_throughout() -> None:
    runtime = AlertRuntime()
    runtime.evaluate(True, [], T0, DELAYS)
    runtime.evaluate(False, [], T0 + timedelta(minutes=2), DELAYS)
    assert runtime.delay_on_until is None
    runtime.evaluate(True, [], T0 + timedelta(minutes=3), DELAYS)
    assert runtime.delay_on_until == T0 + timedelta(minutes=8)


def test_delay_off_absorbs_flicker_and_keeps_ack() -> None:
    runtime = AlertRuntime()
    runtime.evaluate(True, [], T0, Timing(delay_off=timedelta(minutes=1)))
    runtime.ack(T0, None)
    timing = Timing(delay_off=timedelta(minutes=1))
    assert runtime.evaluate(False, [], T0 + timedelta(minutes=2), timing) == []
    assert runtime.delay_off_until == T0 + timedelta(minutes=3)
    flicker_back = T0 + timedelta(minutes=2, seconds=30)
    assert runtime.evaluate(True, [], flicker_back, timing) == []
    assert runtime.delay_off_until is None
    assert runtime.state is AlertState.ACK
    runtime.evaluate(False, [], T0 + timedelta(minutes=4), timing)
    changes = runtime.evaluate(False, [], T0 + timedelta(minutes=5), timing)
    assert _changes(changes) == [(Change.ENDED, AlertState.ACK, AlertState.IDLE)]


def test_no_data_while_idle() -> None:
    runtime = AlertRuntime()
    runtime.evaluate(True, [], T0, DELAYS)
    changes = runtime.evaluate(None, ["binary_sensor.door"], T0, DELAYS)
    assert _changes(changes) == [(Change.NO_DATA, AlertState.IDLE, AlertState.NO_DATA)]
    assert runtime.missing_inputs == ["binary_sensor.door"]
    # No data cancels the pending delay, and has no grace deadline when not firing.
    assert runtime.delay_on_until is None
    assert runtime.next_deadline(DELAYS) is None
    # Repeated no-data results only update the missing inputs.
    assert runtime.evaluate(None, ["x"], T0, DELAYS) == []
    assert runtime.missing_inputs == ["x"]
    # Data returning leaves no_data without a change to announce.
    assert runtime.evaluate(False, [], T0, DELAYS) == []
    assert runtime.state is AlertState.IDLE
    assert runtime.no_data_since is None
    assert runtime.missing_inputs == []


def test_no_data_while_firing_within_grace() -> None:
    runtime = AlertRuntime()
    runtime.evaluate(True, [], T0, Timing())
    runtime.ack(T0, None)
    lost = T0 + timedelta(minutes=1)
    changes = runtime.evaluate(None, ["binary_sensor.door"], lost, DELAYS)
    assert _changes(changes) == [(Change.NO_DATA, AlertState.ACK, AlertState.ACK)]
    assert runtime.no_data_since == lost
    assert runtime.next_deadline(DELAYS) == lost + timedelta(minutes=10)
    assert runtime.evaluate(True, [], lost + timedelta(minutes=9), DELAYS) == []
    assert runtime.state is AlertState.ACK
    assert runtime.firing_since == T0


def test_no_data_while_firing_past_grace() -> None:
    runtime = AlertRuntime()
    runtime.evaluate(True, [], T0, Timing())
    runtime.evaluate(None, [], T0, DELAYS)
    assert runtime.evaluate(None, [], T0 + timedelta(minutes=9), DELAYS) == []
    changes = runtime.evaluate(None, [], T0 + timedelta(minutes=10), DELAYS)
    assert _changes(changes) == [
        (Change.ENDED, AlertState.ACTIVE, AlertState.NO_DATA)
    ]
    assert changes[0][1].reason is EndReason.NO_DATA
    assert runtime.next_deadline(DELAYS) is None
    # Data returning later starts a new firing, after delay_on.
    runtime.evaluate(True, [], T0 + timedelta(minutes=20), DELAYS)
    assert runtime.state is AlertState.IDLE
    assert runtime.delay_on_until == T0 + timedelta(minutes=25)


def test_no_data_cancels_delay_off() -> None:
    runtime = AlertRuntime()
    runtime.evaluate(True, [], T0, Timing())
    runtime.evaluate(False, [], T0, DELAYS)
    assert runtime.delay_off_until is not None
    runtime.evaluate(None, [], T0 + timedelta(seconds=30), DELAYS)
    assert runtime.delay_off_until is None
    # When data returns still false, delay_off runs from then.
    runtime.evaluate(False, [], T0 + timedelta(minutes=2), DELAYS)
    assert runtime.delay_off_until == T0 + timedelta(minutes=3)


def test_awaiting_data_keeps_restored_delays() -> None:
    """After a restart, inputs that are still loading don't cancel delays."""
    runtime = AlertRuntime(delay_on_until=T0 + timedelta(minutes=2))
    runtime.await_data(T0)
    assert runtime.state is AlertState.NO_DATA
    # Loading inputs: no change announced, and the deadline survives.
    assert runtime.evaluate(None, ["binary_sensor.door"], T0, DELAYS) == []
    assert runtime.delay_on_until == T0 + timedelta(minutes=2)
    # The first real data honours it.
    assert runtime.evaluate(True, [], T0 + timedelta(minutes=1), DELAYS) == []
    assert runtime.delay_on_until == T0 + timedelta(minutes=2)
    assert not runtime.awaiting_data
    changes = runtime.evaluate(True, [], T0 + timedelta(minutes=2), DELAYS)
    assert _changes(changes) == [(Change.FIRED, AlertState.IDLE, AlertState.ACTIVE)]


def test_awaiting_data_cancels_delay_if_condition_ended() -> None:
    runtime = AlertRuntime(delay_on_until=T0 + timedelta(minutes=2))
    runtime.await_data(T0)
    runtime.evaluate(False, [], T0, DELAYS)
    assert runtime.delay_on_until is None
    assert runtime.state is AlertState.IDLE


def test_awaiting_data_keeps_firing_and_grace_starts() -> None:
    """A restored firing alert keeps its state while waiting, within grace."""
    runtime = AlertRuntime(firing=True, firing_since=T0, fire_count=1)
    start = T0 + timedelta(hours=1)
    runtime.await_data(start)
    assert runtime.state is AlertState.ACTIVE
    assert runtime.next_deadline(DELAYS) == start + timedelta(minutes=10)
    changes = runtime.evaluate(None, [], start + timedelta(minutes=10), DELAYS)
    assert _changes(changes) == [
        (Change.ENDED, AlertState.ACTIVE, AlertState.NO_DATA)
    ]


def test_reminder_slots_repeat_the_last_gap() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    slots = reminder_slots(start, [10, 20, 30, 60])
    minutes = [int((next(slots) - start).total_seconds() // 60) for _ in range(6)]
    assert minutes == [10, 30, 60, 120, 180, 240]
    assert list(reminder_slots(start, [])) == []


@pytest.mark.parametrize(
    ("after", "expected"),
    [(0, 10), (9, 10), (10, 30), (59, 60), (60, 120), (121, 180), (1000, 1020)],
)
def test_next_reminder_slot(after: int, expected: int) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    slot = next_reminder_slot(
        start, [10, 20, 30, 60], start + timedelta(minutes=after)
    )
    assert slot == start + timedelta(minutes=expected)
    assert next_reminder_slot(start, [], start) is None


def test_parse_schedule() -> None:
    assert parse_schedule("10, 20, 30,60") == (10, 20, 30, 60)
    assert parse_schedule(" 1.5 ; 2") == (1.5, 2)
    assert parse_schedule("  ") == ()
    assert format_schedule((10, 1.5)) == "10, 1.5"
    for bad in ("0", "-5", "ten"):
        with pytest.raises(ValueError):
            parse_schedule(bad)


def test_plan_reminder_only_while_active() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    runtime = AlertRuntime()
    runtime.plan_reminder([10], now)
    assert runtime.next_reminder is None
    runtime.fire(now)
    runtime.plan_reminder([10], now)
    assert runtime.next_reminder == now + timedelta(minutes=10)
    runtime.ack(now, None)
    assert runtime.next_reminder is None
    runtime.unack(now + timedelta(minutes=25), None)
    runtime.plan_reminder([10], now + timedelta(minutes=25))
    assert runtime.next_reminder == now + timedelta(minutes=30)
    # It survives serialization, and ending the firing clears it.
    restored = AlertRuntime.from_dict(runtime.to_dict())
    assert restored.next_reminder == runtime.next_reminder
    transition = runtime.end(now + timedelta(minutes=26), EndReason.RESOLVED)
    assert runtime.next_reminder is None
    assert transition is not None


def test_fire_event_restarts_the_duration() -> None:
    runtime = AlertRuntime()
    runtime.fire_event(T0, {"to": "on"}, timedelta(minutes=10))
    assert runtime.event_expires == T0 + timedelta(minutes=10)
    runtime.ack(T0, None)
    later = T0 + timedelta(minutes=4)
    transition = runtime.fire_event(later, {"to": "on"}, timedelta(minutes=10))
    assert transition.new_state is AlertState.ACK
    assert runtime.event_expires == later + timedelta(minutes=10)
    assert runtime.firing_since == T0

    restored = AlertRuntime.from_dict(runtime.to_dict())
    assert restored.event_expires == runtime.event_expires

    runtime.end(later + timedelta(minutes=10), EndReason.RESOLVED)
    assert runtime.event_expires is None


@pytest.mark.parametrize(
    ("value", "firing", "expected"),
    [
        (30, False, False),  # At the maximum isn't above it.
        (30.1, False, True),
        (29, True, True),  # Inside, but not by the hysteresis.
        (28, True, False),
        (5, False, False),
        (4.9, False, True),
        (6.5, True, True),
        (7, True, False),
    ],
)
def test_threshold_holds(value: float, firing: bool, expected: bool) -> None:
    reading = Reading(value, minimum=5, maximum=30)
    assert threshold_holds(reading, 2, firing) is expected


def test_threshold_one_limit() -> None:
    assert threshold_holds(Reading(100, maximum=50), 0, False)
    assert not threshold_holds(Reading(-100, maximum=50), 0, False)
    assert threshold_holds(Reading(-1, minimum=0), 0, False)


TEMPLATES = OnOffSides(
    on_template=True, on_trigger=False, off_template=True, off_trigger=False
)
TRIGGERS = OnOffSides(
    on_template=False, on_trigger=True, off_template=False, off_trigger=True
)


def _step(runtime: AlertRuntime, sides: OnOffSides, on, off) -> list[Change]:
    """Judge and evaluate once, as the entity does."""
    condition = runtime.on_off_condition(sides, on, off)
    changes = [change for change, _ in runtime.evaluate(condition, [], T0, Timing())]
    if Change.FIRED in changes:
        runtime.on_off_fired()
    if Change.ENDED in changes:
        runtime.on_off_ended()
    return changes


def test_on_off_templates_are_edges() -> None:
    runtime = AlertRuntime()
    # A new alert is armed: an on side that's already true fires.
    assert _step(runtime, TEMPLATES, True, False) == [Change.FIRED]
    assert _step(runtime, TEMPLATES, True, True) == [Change.ENDED]
    # Still on: no new edge, so no new firing.
    assert _step(runtime, TEMPLATES, True, False) == []
    assert _step(runtime, TEMPLATES, False, False) == []
    assert _step(runtime, TEMPLATES, True, False) == [Change.FIRED]


def test_on_off_off_side_needs_its_own_edge() -> None:
    """An off criterion already true at the fire has to go false and true again."""
    runtime = AlertRuntime()
    assert _step(runtime, TEMPLATES, True, True) == [Change.FIRED]
    assert _step(runtime, TEMPLATES, True, True) == []
    assert _step(runtime, TEMPLATES, True, False) == []
    assert _step(runtime, TEMPLATES, True, True) == [Change.ENDED]


def test_on_off_rising_edge_while_firing_is_ignored() -> None:
    runtime = AlertRuntime()
    _step(runtime, TEMPLATES, True, False)
    _step(runtime, TEMPLATES, False, False)
    _step(runtime, TEMPLATES, True, False)
    assert _step(runtime, TEMPLATES, True, True) == [Change.ENDED]
    assert _step(runtime, TEMPLATES, True, False) == []


def test_on_off_no_data_counts_only_the_live_side() -> None:
    runtime = AlertRuntime()
    assert runtime.on_off_condition(TEMPLATES, None, False) is None
    assert runtime.on_off_condition(TEMPLATES, False, None) is False
    _step(runtime, TEMPLATES, True, False)
    assert runtime.on_off_condition(TEMPLATES, None, False) is True
    assert runtime.on_off_condition(TEMPLATES, True, None) is None


def test_on_off_edges_survive_storage() -> None:
    runtime = AlertRuntime()
    _step(runtime, TEMPLATES, True, False)
    _step(runtime, TEMPLATES, True, True)
    restored = AlertRuntime.from_dict(runtime.to_dict())
    assert _step(restored, TEMPLATES, True, False) == []


def test_on_off_triggers() -> None:
    runtime = AlertRuntime()
    assert _step(runtime, TRIGGERS, None, None) == []
    runtime.on_off_pulse("off")  # Not firing: the off side doesn't count.
    runtime.on_off_pulse("on")
    assert _step(runtime, TRIGGERS, None, None) == [Change.FIRED]
    runtime.on_off_pulse("on")  # Firing: the on side doesn't count.
    assert _step(runtime, TRIGGERS, None, None) == []
    runtime.on_off_pulse("off")
    assert _step(runtime, TRIGGERS, None, None) == [Change.ENDED]
    assert _step(runtime, TRIGGERS, None, None) == []


def test_on_off_trigger_with_template_needs_it_to_hold() -> None:
    sides = OnOffSides(
        on_template=True, on_trigger=True, off_template=False, off_trigger=True
    )
    runtime = AlertRuntime()
    runtime.on_off_pulse("on")
    assert runtime.on_off_condition(sides, True, None) is True
    # The template turning false before the fire (e.g. during delay_on) drops it.
    assert runtime.on_off_condition(sides, False, None) is False
    assert runtime.on_off_condition(sides, True, None) is False


def test_snooze_active_acks_it() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.next_reminder = T0 + timedelta(minutes=10)
    until = T0 + timedelta(minutes=30)
    changes = runtime.snooze(T0, until, "user")
    assert [change for change, _ in changes] == [Change.SNOOZED, Change.ACKED]
    assert all(
        (t.old_state, t.new_state) == (AlertState.ACTIVE, AlertState.ACK)
        for _, t in changes
    )
    assert runtime.state is AlertState.ACK
    assert runtime.snoozed_until == until
    assert runtime.last_snoozed == runtime.last_acked == T0
    assert runtime.last_snoozed_by == runtime.last_acked_by == "user"
    assert runtime.next_reminder is None


def test_snooze_acked_only_sets_the_deadline() -> None:
    """Re-snoozing replaces the deadline, even with a sooner one."""
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.snooze(T0, T0 + timedelta(hours=1), "a")
    later = T0 + timedelta(minutes=5)
    changes = runtime.snooze(later, later + timedelta(minutes=10), "b")
    assert [change for change, _ in changes] == [Change.SNOOZED]
    assert changes[0][1].old_state == changes[0][1].new_state == AlertState.ACK
    assert runtime.snoozed_until == later + timedelta(minutes=10)
    assert runtime.last_snoozed_by == "b"
    assert runtime.last_acked_by == "a"


def test_snooze_not_firing_does_nothing() -> None:
    runtime = AlertRuntime()
    assert runtime.snooze(T0, T0 + timedelta(minutes=5), None) == []
    assert runtime.snoozed_until is None


def test_snooze_expire() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    until = T0 + timedelta(minutes=30)
    runtime.snooze(T0, until, "user")
    assert runtime.snooze_expire(until - timedelta(seconds=1)) == []
    changes = runtime.snooze_expire(until)
    assert [change for change, _ in changes] == [
        Change.SNOOZE_EXPIRED,
        Change.UNACKED,
    ]
    assert runtime.state is AlertState.ACTIVE
    assert runtime.snoozed_until is None
    assert runtime.last_unacked == until
    assert runtime.last_unacked_by is None


def test_ack_makes_a_snooze_lasting() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.snooze(T0, T0 + timedelta(minutes=30), "a")
    transition = runtime.ack(T0 + timedelta(minutes=1), "b")
    assert transition is not None
    assert transition.old_state == transition.new_state == AlertState.ACK
    assert runtime.snoozed_until is None
    assert runtime.last_acked_by == "b"
    # A plain acknowledgement can't be acknowledged again.
    assert runtime.ack(T0 + timedelta(minutes=2), "c") is None


def test_unack_and_end_clear_the_snooze() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.snooze(T0, T0 + timedelta(minutes=30), None)
    runtime.unack(T0, None)
    assert runtime.snoozed_until is None
    runtime.snooze(T0, T0 + timedelta(minutes=30), None)
    runtime.end(T0, EndReason.RESOLVED)
    assert runtime.snoozed_until is None


def test_snooze_round_trip() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.snooze(T0, T0 + timedelta(minutes=30), "user")
    restored = AlertRuntime.from_dict(runtime.to_dict())
    assert restored.snoozed_until == T0 + timedelta(minutes=30)
    assert restored.last_snoozed == T0
    assert restored.state is AlertState.ACK


@pytest.mark.parametrize(
    ("minutes", "remind", "next_slot"),
    [
        # Schedule [10, 20, 30, 60]: slots at 10, 30, 60, 120, 180, …
        (15, True, 30),  # 15 min to the next slot
        (26, False, 30),  # 4 min: the slot will do
        (25, True, 30),  # exactly the window: remind now
        (119, False, 120),
        (130, True, 180),  # the repeating part
    ],
)
def test_snooze_end_reminder(minutes: int, remind: bool, next_slot: int) -> None:
    now = T0 + timedelta(minutes=minutes)
    assert snooze_end_reminder(T0, (10, 20, 30, 60), now, timedelta(minutes=5)) == (
        remind,
        T0 + timedelta(minutes=next_slot),
    )


def test_snooze_end_reminder_without_reminders() -> None:
    now = T0 + timedelta(minutes=30)
    assert snooze_end_reminder(T0, (), now, timedelta(minutes=5)) == (False, None)


def test_disable_ends_a_firing_and_clears_it() -> None:
    runtime = AlertRuntime()
    runtime.fire(T0)
    runtime.snooze(T0, T0 + timedelta(hours=1), None)
    runtime.no_data_since = T0
    runtime.delay_off_until = T0 + timedelta(minutes=1)
    later = T0 + timedelta(minutes=5)
    changes = runtime.disable(later, "user")
    assert [change for change, _ in changes] == [Change.ENDED, Change.DISABLED]
    ended = changes[0][1]
    assert ended.reason is EndReason.DISABLED
    assert ended.duration_seconds == 300
    assert changes[1][1].old_state is AlertState.ACK
    assert runtime.state is AlertState.DISABLED
    assert not runtime.firing and runtime.snoozed_until is None
    assert runtime.no_data_since is None and runtime.delay_off_until is None
    assert runtime.next_reminder is None
    assert (runtime.last_disabled, runtime.last_disabled_by) == (later, "user")


def test_disable_idle() -> None:
    runtime = AlertRuntime()
    changes = runtime.disable(T0, None)
    assert [change for change, _ in changes] == [Change.DISABLED]
    assert changes[0][1].old_state is AlertState.IDLE


def test_disable_and_suspend_latest_wins() -> None:
    runtime = AlertRuntime()
    runtime.disable(T0, None)
    assert runtime.disable(T0, None) == []
    until = T0 + timedelta(hours=1)
    changes = runtime.disable(T0, None, until)
    assert [change for change, _ in changes] == [Change.DISABLED]
    assert changes[0][1].old_state is AlertState.DISABLED
    assert runtime.disabled_until == until
    # Suspending again moves the time; disabling makes it indefinite.
    runtime.disable(T0, None, until + timedelta(hours=1))
    assert runtime.disabled_until == until + timedelta(hours=1)
    assert runtime.disable(T0, None) != []
    assert runtime.disabled_until is None


def test_disabled_ignores_evaluation() -> None:
    runtime = AlertRuntime()
    runtime.disable(T0, None)
    assert runtime.evaluate(True, [], T0, Timing()) == []
    assert runtime.state is AlertState.DISABLED


def test_enable() -> None:
    runtime = AlertRuntime()
    assert runtime.enable(T0, None, awaits_data=False) == []
    runtime.on_armed = False
    runtime.disable(T0, None, T0 + timedelta(hours=1))
    changes = runtime.enable(T0, "user", awaits_data=False)
    assert [change for change, _ in changes] == [Change.ENABLED]
    assert (changes[0][1].old_state, changes[0][1].new_state) == (
        AlertState.DISABLED,
        AlertState.IDLE,
    )
    assert runtime.disabled_until is None
    assert runtime.on_armed
    assert (runtime.last_enabled, runtime.last_enabled_by) == (T0, "user")


def test_enable_awaiting_data() -> None:
    runtime = AlertRuntime()
    runtime.disable(T0, None)
    runtime.enable(T0, None, awaits_data=True)
    assert runtime.state is AlertState.NO_DATA
    assert runtime.awaiting_data


def test_suspension_ended() -> None:
    runtime = AlertRuntime()
    until = T0 + timedelta(hours=1)
    runtime.disable(T0, None, until)
    assert runtime.suspension_ended(until - timedelta(seconds=1), awaits_data=False) == []
    changes = runtime.suspension_ended(until, awaits_data=False)
    assert [change for change, _ in changes] == [Change.ENABLED]
    assert runtime.last_enabled_by is None
    # An indefinitely disabled alert doesn't end its own suspension.
    runtime.disable(T0, None)
    assert runtime.suspension_ended(until, awaits_data=False) == []


def test_disabled_round_trip() -> None:
    runtime = AlertRuntime()
    runtime.disable(T0, "user", T0 + timedelta(hours=1))
    restored = AlertRuntime.from_dict(runtime.to_dict())
    assert restored.state is AlertState.DISABLED
    assert restored.disabled_until == T0 + timedelta(hours=1)
    assert restored.last_disabled == T0
