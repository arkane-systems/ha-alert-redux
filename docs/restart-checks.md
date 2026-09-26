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

- **Snooze outlasts the restart** (phase 6a, set up 2026-09-25). Test Condition
  Alert is firing (`input_boolean.alert_redux_test_value` on, since 23:56:11 UTC)
  and snoozed until 2026-10-02 23:56:11 UTC.
  *Expect:* still `ack` after the restart, with the same `snoozed_until` and
  `firing_since`, and no on notification. Afterwards, turn the input boolean
  off.
- **Snooze runs out during the restart** (phase 6a). *Set up just before the
  next install restart:* fire Test Bus Event Alert or Test Condition Alert,
  snooze it for 1 minute, then restart at once.
  *Expect:* `active` once HA is back, `last_unacked_by` null, and the snooze-end
  rule applied (an immediate reminder unless a slot is under 5 min away; none
  for Test Bus Event Alert, which has no reminders).

## Done

(none yet)
