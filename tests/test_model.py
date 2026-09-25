"""Tests for the alert state machine, independent of Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.alert_redux.const import AlertState, EndReason
from custom_components.alert_redux.model import (
    AlertRuntime,
    Change,
    Timing,
    format_schedule,
    next_reminder_slot,
    parse_schedule,
    reminder_slots,
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
