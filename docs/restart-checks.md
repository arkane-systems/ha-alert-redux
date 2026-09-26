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
and 20 seconds after the request. Set-up of Alert Redux in the new process came
50 seconds after the request in phase 8, 60 in 7b, 56 in 7a, and 25 in 6b. So
the real downtime is roughly 25 to 50 seconds after the request, and a deadline
meant to fall *during* it should be about 35 to 40 seconds after: e.g. snooze or
suspend for 1 minute, then request the restart 20 to 25 seconds later. (In phase
8 the restart went only 3 seconds after, and the deadlines fell 7 seconds after
set-up.)

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

- **The summary sensors are right straight after a restart** (phase 8). *Just
  after the next install restart:* before touching any alert, compare
  `sensor.alert_redux_firing`, `…_active`, `…_acknowledged`, `…_no_data`, and
  `…_disabled` (and their `entity_ids`) with the alerts' own states.
  *Expect:* they agree; the sensors' IDs are unchanged.

- **A no-data spell spanning the restart announces its end** (phase 8). *Set up
  just before an install restart:* with the test door open (so Test Sensor Is
  On is firing), turn `input_boolean.alert_redux_test_available` off, and
  check the `alert_redux_no_data` event (a "lost data" row in the logbook).
  Leave it off across the restart. Test Sensor Is On's 60 s grace runs out,
  so it ends and shows `no_data`.
  *Expect:* once HA is back, turning the input back on fires
  `alert_redux_data_restored` with `missing_inputs:
  [binary_sensor.alert_redux_test_sensor]` (a "data restored" logbook row).

## Done

- **2026-09-26, phase 8 install restart. A pre-acknowledgement survives the
  restart** (phase 7b). Door opened and Test Door Open acknowledged at
  12:42:11, restart requested at 12:42:14. Alert Redux was set up again at about
  12:43:04, and Left Open's `delay_on` ran out at 12:43:11, live: it fired as
  `ack` with `pre_acked_by: [alert_redux.test_door_open]`, restored from before
  the restart. Passed. (The done notification on closing wasn't observed.)
- **2026-09-26, phase 8 install restart. Snooze runs out, and suspension ends,
  during the restart** (phases 6a, 6b). *Not exercised again:* both fell due at
  12:43:11, 7 seconds after set-up. Live, both were correct: Test Condition
  Alert went `active` with `last_unacked_by` null; Test Threshold Alert was
  enabled with `last_enabled_by` null. Still pending, with the timing note
  revised.

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
