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

**Timing on this instance:** the old process keeps running for at least 20
seconds after a restart is requested: in 7a and 7b it still handled deadlines 10
and 20 seconds after the request. In 7b the new process loaded Alert Redux 37
seconds after the request and set it up at 60 seconds; in 7a, set-up was at 56
seconds (in 6b, 25). So the real downtime is roughly 25 to 55 seconds after the
request, and a deadline meant to fall *during* it should be about 45 seconds
after: e.g. snooze or suspend for 1 minute, then request the restart 15 seconds
later.

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

- **A pre-acknowledgement survives the restart** (phase 7b). Test Door Left Open
  supersedes Test Door Open with propagation *Acknowledge*. *Set up just before
  an install restart:* open the test door, acknowledge Test Door Open at once,
  and restart within the minute, so that Left Open's `delay_on` runs out during
  the restart.
  *Expect:* Left Open's `pre_acked_by` is `[alert_redux.test_door_open]` once
  HA is back, and Left Open fires at startup (its restored `delay_on`) as `ack`,
  with no on notification. Close the door afterwards: only Left Open's done
  notification.

## Done

- **2026-09-26, 7b install restart. A superseded alert stays suppressed across
  the restart** (phase 7a). Test Door Open and Left Open came back firing with
  the same `firing_since`, Open's `superseded_by` restored, and no on
  notifications; Open's 11:59:54 reminder was skipped ("reminder superseded").
  Passed.
- **2026-09-26, 7b install restart. Snooze runs out, and suspension ends, during
  the restart** (phases 6a, 6b). *Not exercised again:* both fell due 20
  seconds after the request, and the old process still handled them live
  (correctly). Still pending, with the timing note revised again.

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
