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

**Timing on this instance:** Alert Redux is set up again about 25 seconds after a
restart is requested (well before the "started" event, about two minutes after).
The real downtime is only those 25 seconds, so a deadline meant to fall *during*
it should be about 10 seconds after the request: e.g. snooze or suspend for 1
minute, then request the restart 50 seconds later.

- **Snooze runs out during the restart** (phase 6a). *Set up just before an
  install restart:* snooze a firing, Quiet-only test alert so that the deadline
  falls about 10 s after requesting the restart.
  *Expect:* `active` once HA is back, `last_unacked_by` null, and the snooze-end
  rule applied at startup (an immediate reminder unless a slot is under 5 min
  away).

- **Disabled survives the restart** (phase 6b, set up 2026-09-26). Test
  Threshold Alert disabled indefinitely at 01:12:25 UTC.
  *Expect:* still `disabled`, `disabled_until` null, and ignoring its value
  entity (it doesn't fire or go to `no_data`). Afterwards, enable it.
- **Suspension outlasts the restart** (phase 6b, set up 2026-09-26). Test On Off
  Alert suspended until 2026-10-03 01:12:25 UTC.
  *Expect:* still `disabled` with that `disabled_until`. Afterwards, enable it.
- **Suspension ends during the restart** (phase 6b). *Set up just before an
  install restart:* suspend a Quiet-only test alert so that its time falls about
  10 s after requesting the restart (see the timing note).
  *Expect:* enabled once HA is back, with `last_enabled_by` null; a condition
  alert evaluates from scratch (`no_data` until its inputs report).

## Done

- **2026-09-26, 6b install restart. Snooze outlasts the restart** (phase 6a).
  Test Condition Alert came back `ack`, still snoozed until 2026-10-02 23:56:11,
  with the same `firing_since`. Passed.
- **2026-09-26, 6b install restart. Snooze runs out during the restart** (phase
  6a). *Not exercised:* Test Sensor Is On's 1-minute snooze ran out at 01:06:19,
  after the new process had already set Alert Redux up (at about 01:05:44;
  the restart was requested at about 01:05:20).
  The live expiry was correct: `active`, and an immediate reminder, the next
  slot being 01:56:31. Still pending, with the timing note above.
