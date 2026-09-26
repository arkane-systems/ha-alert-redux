# Restart checks

Real-HA checks of behaviour across a restart. They don't get restarts of their own.
Each is set up at the end of a real-HA run, then checked at the start of the next
run, after the restart that installing that run's code needs anyway. pytest
(`tests/test_restore.py`) covers every restore path in the phase that adds it;
this ledger confirms them against a real instance.

A check that's still pending when the phase plan ends (or before 1.0.0) is
cleared with one deliberate restart. A change to the store's format or migration
still gets a dedicated restart when it's made.

## Pending

Test alerts are the ones named "Test …", and send only to the Quiet group.

**Timing on this instance:** Alert Redux has been set up again anywhere from 25
seconds (6b) to 56 seconds (7a) after a restart is requested, well before the
"started" event, about two minutes after. The old process keeps running for at
least 10 seconds after the request: in 7a it still handled deadlines 10 seconds
after it. So a deadline meant to fall *during* the downtime should be about 20
seconds after the request: e.g. snooze or suspend for 1 minute, then request the
restart 40 seconds later.

- **Snooze runs out during the restart** (phase 6a). *Set up just before an
  install restart:* snooze a firing, Quiet-only test alert so that the deadline
  falls about 10 s after requesting the restart.
  *Expect:* `active` once HA is back, `last_unacked_by` null, and the snooze-end
  rule applied at startup (an immediate reminder unless a slot is under 5 min
  away).

- **Suspension ends during the restart** (phase 6b). *Set up just before an
  install restart:* suspend a Quiet-only test alert so that its time falls about
  10 s after requesting the restart (see the timing note).
  *Expect:* enabled once HA is back, with `last_enabled_by` null; a condition
  alert evaluates from scratch (`no_data` until its inputs report).

- **A superseded alert stays suppressed across the restart** (phase 7a). *Set
  up just before an install restart:* open the test door
  (`input_boolean.alert_redux_test_value` on) and wait for Test Door Left Open to
  fire (1 minute), so that Test Door Open is superseded; then restart.
  *Expect:* both still firing, with the same `firing_since`; no on
  notifications; Test Door Open's `superseded_by` is `[test_door_left_open]`
  once HA is back, with no `alert_redux_superseded` event; its reminders are
  skipped while Left Open fires. Close the door afterwards: only Left Open's
  (and Test Door Unacknowledged's) done notification.

## Done

- **2026-09-26, 7a install restart. Disabled survives the restart** (phase 6b).
  Test Threshold Alert came back `disabled`, `disabled_until` null, ignoring its
  value. Passed; enabled afterwards.
- **2026-09-26, 7a install restart. Suspension outlasts the restart** (phase 6b).
  Test On Off Alert came back `disabled` until 2026-10-03 01:12:25. Passed;
  enabled afterwards.
- **2026-09-26, 7a install restart. Snooze runs out, and suspension ends, during
  the restart** (phases 6a, 6b). *Not exercised:* Test Condition Alert's snooze
  and Test Sensor Is On's suspension both fell due at 11:08:43, 10 seconds after
  the restart request, and the old process handled both live (1 ms late); Alert
  Redux was set up again at 11:09:29. Both behaved correctly live, and Test
  Sensor Is On then fired at startup from its restored `delay_on`. Still
  pending, with the revised timing note.

- **2026-09-26, 6b install restart. Snooze outlasts the restart** (phase 6a).
  Test Condition Alert came back `ack`, still snoozed until 2026-10-02 23:56:11,
  with the same `firing_since`. Passed.
- **2026-09-26, 6b install restart. Snooze runs out during the restart** (phase
  6a). *Not exercised:* Test Sensor Is On's 1-minute snooze ran out at 01:06:19,
  after the new process had already set Alert Redux up (at about 01:05:44;
  the restart was requested at about 01:05:20).
  The live expiry was correct: `active`, and an immediate reminder, the next
  slot being 01:56:31. Still pending, with the timing note above.
