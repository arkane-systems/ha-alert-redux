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
50 seconds after the request in 9a and phase 8, 60 in 7b, 56 in 7a, 45 in
the 1.0.0 checks, and 25 in 6b. So the real downtime is roughly 25 to 50
seconds after the request, and a deadline meant to fall *during* it should be about 35 to 40 seconds after: e.g.
snooze or suspend for 1 minute, then request the restart 20 to 25 seconds later.
In 9a that worked: the restart went 21 seconds after, the deadlines fell 39
seconds after the request, and set-up came 11 seconds after them.

None.

## Done

- **2026-10-07, a restart during the soak test of PR #34. A deleted alert that
  was holding a throttled done notification isn't announced as deleted again
  at startup** (the repository review's fixes). RX Throttled (a manual alert,
  Notice, to a persistent-notification-only group, throttled to 1 notification
  in 60 minutes) was fired, then RX Throttled Over, which supersedes it, with
  the done window raised to 60 seconds; RX Throttled was dismissed, so its done
  notification was held, and deleted within the window. No "RX Throttled
  stopped firing" notification appeared. After the restart, the unfiltered
  Activity view had one "Deleted" row for RX Throttled, from the deletion, and
  none from the startup. A view filtered by entity, label, or area shows no
  rows for a deleted alert (spec §11.4), so this check needs the unfiltered
  one. Passed.

- **2026-10-03, install restart for 1.3.0. A latched alert stays latched across
  a restart** (phase 15). Test Latching Alert (a state alert on
  `input_boolean.test_latching`, Quiet only, latching, reminders every 60
  minutes) was left `latched` at 20:12:47 UTC with `fire_count` 2 and
  `next_reminder` 21:12:47. The restart was requested at 20:25:13; at 20:27:23
  `alert_redux/info` reported 1.3.0, and the alert was still `latched`, with
  `fire_count` 2, the same `last_ended` and `next_reminder`, and no
  `no_data_since`; its proxy switch was on, and `sensor.alert_redux_latched`
  and `…_active` both listed it. Acknowledging it released it to `idle`
  (`fire_count` 0, `next_reminder` null). The reminder wasn't due during the
  downtime, so that path stays covered by pytest
  (`test_latch_survives_restart`). The alert and its helper were deleted
  afterwards. Passed.

- **2026-10-02, install restart for 1.2.0. Area and labels aren't forced back
  after a restart** (phase 13). Set up on the live instance before the install:
  a throwaway generator (the target's area, plus a label) with one generated
  alert, and a throwaway fixed alert (an area and a label), whose area and labels
  were then changed by hand (a generated alert moved to another area and stripped
  of the generator's label; the fixed alert given another area and no labels). After
  the restart, a minute after the install, nothing had been put back on either, and
  `alert_redux/info` reported 1.2.0. This covers the `placed` flag and the placement
  stored with a generated alert's record (spec §11.6). The throwaways, their helper,
  and their label were deleted afterwards.

- **2026-10-02, install restart for phase 12. Exposure isn't forced back, and
  voice and proxies come back** (1.1.0). Test Voice Proxies (a state alert on
  `input_boolean.test_alert`, Quiet only, with both proxies) had been unexposed
  from Assist, and its snooze button from Google, by hand at 00:20 UTC. After
  the restart, at 01:15 UTC: the alert was still unexposed from Assist, so "what
  alerts are firing" through the built-in agent answered without it, though it
  was acknowledged and firing (the sentence triggers had reattached); Test
  Alert was still exposed. `switch.test_voice_proxies` and
  `button.snooze_test_voice_proxies` kept their entity IDs; the switch was off,
  matching its alert's `ack`; the button was still unexposed from Google, and
  both were still exposed to Alexa and hidden from Assist. Deleting Test Voice
  Proxies then removed both proxies from the entity registry. Passed.

- **2026-09-30, install restart for the logbook fix. The logbook shows an
  ending while HA was down** (1.0.0). Test Manual Ending (1 minute) was fired
  at 15:37:59 UTC and the restart requested at 15:38:21; Alert Redux set up at
  15:39:09. It came back `idle` with `last_ended` 15:38:59.405, its old
  `event_expires`, and its logbook now has an "Idle" row at 15:39:09 after the
  "Active" one. The done notification arrived on Quiet. All other alerts came
  back as before. Passed.

- **2026-09-30, restart for other updates. The expiry-on-restore code after the
  1.0.0 refactor** (1.0.0). All three fired at 15:10:42 UTC; the restart was
  requested at 15:11:03, and Alert Redux set up at 15:11:48.
  - *Duration ran out while HA was down:* Test Manual Ending (1 minute) came
    back `idle` with `last_ended` 15:11:42.148, its old `event_expires`, and the
    done notification arrived on Quiet. Passed. Its logbook showed no row for the
    end: HA's logbook drops an entity's first state after a restart, and it had
    ended before that. Fixed for 1.0.0 (spec §15.1), with a check below.
  - *Manual alert firing across the restart:* Test Manual Long (15 minutes) came
    back `active` with the same `firing_since`, `event_expires`, `fire_data`, and
    `next_reminder`. Its reminder arrived on Quiet at 15:20:42 as planned before
    the restart, and it ended at 15:25:42. Passed.
  - *Event alert firing across the restart:* Test Event Alert came back `active`
    with the same `event_expires` and `trigger_data`, and ended at 15:15:42.
    Passed.

- **2026-09-28, 1.0.0 refactor install restart.** No checks were pending. All
  26 alerts, of every kind and including generated ones, came back `idle` with
  their attributes as before, and nothing from Alert Redux in the log. Passed.

- **2026-09-26, v0.11.0 install restart. Generated supersession across the
  restart** (phase 11b). Test Switch Still On's alert came back `ack`, firing
  since 22:36:59 UTC as before, still pre-acknowledged by Test Switch On's
  alert; Switch On came back `ack` with `superseded_by` Still On's alert. No
  new logbook entries or notifications. Passed.

- **2026-09-26, 11b install restart. A generated alert keeps its state across
  the restart** (phase 11a). Test Switch On's alert came back `ack`, firing
  since 22:01:29 UTC as before; the generator sensors kept their counts (1 and
  5). Passed.
- **2026-09-26, 11b install restart. Held quiet-hours notifications survive
  the restart** (phase 10b). The phase 11 "failure" was the set-up: Office
  Only's quiet-hours threshold had been Warning, so Test Bus Event Alert
  (Warning) was never held. With it set back to Critical (by agreement, before
  this run), throttling's end (22:32:54 UTC, restart requested 22:32:27) sent
  its summary to the phones and was held for Office Only; turning the helper
  off at 22:35:38 released one key, and the Echo announced one Quiet hours
  summary. Passed.
- **2026-09-26, 11b install restart. Throttling whose end falls due while HA
  is down** (phase 10a). The new process set Alert Redux up at 22:32:49, five
  seconds before the end: it ended the restored throttling at startup, the
  phones got the summary, and `throttled_since` was null. Passed (as closely
  as this instance's timing allows).
- **2026-09-26, 11b install restart. Quiet hours hold through startup**
  (0.10.1). The Echo stayed silent through the restart while the helper was
  on. Passed again.

- **2026-09-26, phase 11 install restart. Quiet hours hold through startup**
  (0.10.1). The helper was on through the restart; the Echo stayed silent
  during and after it. Passed.
- **2026-09-26, phase 11 install restart. Held quiet-hours notifications
  survive the restart** (phase 10b). **Failed** (the set-up, not the code; see
  above): turning the helper off at
  22:01 UTC, after the restart, had the Echo announce nothing. The throttling
  summary it should have listed was produced by the old process (below), 4
  seconds into its shutdown; whether it was held and saved, or lost, isn't
  known (logging was at WARNING). Re-armed above, with debug logging.
- **2026-09-26, phase 11 install restart. Throttling whose end falls due while
  HA is down** (phase 10a). *Not exercised:* the restart was requested at
  21:54:05 UTC, only 4 seconds before throttling's end (21:54:09), so the old
  process ended it live; the phones got the summary and `throttled_since` was
  null afterwards. Still pending.

- **2026-09-26, 10b install restart. Throttling across a restart** (phase
  10a). Test Bus Event Alert was throttled from 17:42:14 UTC, one notification
  held; the restart was requested at 17:46:33 for an end due at 17:47:14. This
  restart was fast (the new process loaded Alert Redux by 17:46:57), so the end
  fell due after set-up: the restored throttle state ended at 17:47:16, and
  `throttled_since` was null. Passed for restoring the throttle state; the
  end falling due while HA is down is re-armed above.

- **2026-09-26, 10a install restart. A button on a notification sent before
  the restart still works after it** (phase 9b). Test Door Open fired at
  12:17:42 local and notified the phones; the restart followed. At 12:20:12,
  after HA was back, Close Door turned `input_boolean.alert_redux_test_value`
  off in a context parented by the tap, with the tapping user. Passed.

- **2026-09-26, 9b install restart. A live notification can still be cleared
  after the restart** (phase 9a). Test Condition Alert fired at 11:08:04 local
  and notified both phones (Quiet) before the restart; acknowledged after it,
  its notification disappeared from both. Passed.

- **2026-09-26, 9a install restart. Snooze runs out, and suspension ends,
  during the restart** (phases 6a, 6b). Test Threshold Alert snoozed and Test
  On Off Alert suspended, both until 15:41:00 UTC; restart requested at
  15:40:21, Alert Redux set up again at 15:41:11. Threshold came back `active`,
  `last_unacked_by` null, with the snooze-end rule applied at startup (its next
  slot was 8 minutes away, so an immediate reminder, which reached the phones).
  On Off was enabled with `last_enabled_by` null, and went `no_data`: its input
  was unavailable. Passed.
- **2026-09-26, 9a install restart. The summary sensors are right straight
  after a restart** (phase 8). Every count and `entity_ids` list agreed with
  the alerts' states; Test Door Open, firing in its grace period, counted as
  both firing and no data, as specified. The IDs were unchanged. Passed.
- **2026-09-26, 9a install restart. A no-data spell spanning the restart
  announces its end** (phase 8). Test Sensor Is On lost its data at 10:39:51
  local, its grace ran out while HA was down, and it came back `no_data`.
  Turning the input back on at 10:42:43 gave a "data restored" logbook row, and
  it went `idle` and then fired again after its `delay_on`. Passed. (The
  recorder took a few minutes after the restart to show any of it.)

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
