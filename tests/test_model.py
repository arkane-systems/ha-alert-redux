"""Tests for the alert state machine, independent of Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.alert_redux.const import AlertState
from custom_components.alert_redux.model import AlertRuntime

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
    transition = runtime.end(T0 + timedelta(seconds=90))
    assert transition is not None
    assert (transition.old_state, transition.new_state) == (
        AlertState.ACK,
        AlertState.IDLE,
    )
    assert transition.fire_count == 2
    assert transition.duration_seconds == 90
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
    runtime.end(T0)
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
    assert runtime.end(T0) is None
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
