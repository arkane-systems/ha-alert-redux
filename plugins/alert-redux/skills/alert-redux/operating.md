# Operating Alert Redux

## Contents
- Actions
- States
- Attributes
- Events
- Acknowledging, snoozing, disabling, suspending
- Notifications
- Supersession
- Restarts

## Actions

All take alert entities as a normal `target` (`entity_id`, area, label, …).

| Action | Fields | Effect |
|---|---|---|
| `alert_redux.fire` | `data` (object, optional) | Fire a **manual** alert, or fire it again (adds to `fire_count`, keeps the acknowledgement). `data` is kept as `fire_data`. |
| `alert_redux.dismiss` | | End a **manual** alert's firing. Other kinds end by themselves. |
| `alert_redux.ack` | | Acknowledge a firing alert, or make a snooze a lasting acknowledgement. |
| `alert_redux.unack` | | Remove the acknowledgement (and any snooze). Reminders resume on the original schedule. |
| `alert_redux.snooze` | `duration` (required) | Acknowledge a firing alert for a while. |
| `alert_redux.disable` | | Disable until enabled. **Admin only.** |
| `alert_redux.enable` | | Enable a disabled or suspended alert. **Admin only.** |
| `alert_redux.suspend` | `duration` or `until` | Disable for a while, or until a time (local time if no zone). **Admin only.** |
| `alert_redux.refresh_generator` | `entity_id`: generator sensors | Re-evaluate a generator's targets now. For debugging. |

An action that doesn't fit the current state (acknowledging an idle alert) does
nothing. These raise errors instead:

- `fire` or `dismiss` on a non-manual alert: `not_manual`.
- `ack` or `snooze` on an unacknowledgeable alert: `not_acknowledgeable`.
- `suspend` until a time in the past: `suspend_in_past`.
- `refresh_generator` on something that isn't a generator sensor: `not_generator`.

## States

| State | Meaning |
|---|---|
| `idle` | Not firing. |
| `active` | Firing, unacknowledged. Reminders are sent. |
| `ack` | Firing, acknowledged (or snoozed: `snoozed_until` is set). |
| `no_data` | Not firing, and its inputs are unavailable, unknown, or won't parse. |
| `disabled` | Disabled, or suspended until `disabled_until`. Ignores its inputs. |

A **firing** alert whose inputs disappear stays `active` or `ack` for its no-data
grace period, with `no_data_since` and `missing_inputs` set; if the grace runs
out, the firing ends with reason `no_data`.

## Attributes

Every alert: `kind`, `priority`, `acknowledgeable`, `subject_entity`,
`firing_since`, `last_fired`, `last_ended`, `fire_count`, `last_acked`,
`last_acked_by`, `last_unacked`, `last_unacked_by`, `snoozed_until`,
`last_snoozed`, `last_snoozed_by`, `disabled_until`, `last_disabled`,
`last_disabled_by`, `last_enabled`, `last_enabled_by`, `message` and
`display_message` (rendered while firing), `notifier_groups` (names),
`reminder_schedule`, `next_reminder`, `throttle`, `throttled_since`, `supersedes`,
`superseded_by`, `pre_acked_by`, `pre_snoozed_until`, `broken_references`,
`buttons` (labels), `generated_by` (the generator's sensor, for generated alerts).
The `_by` attributes are user IDs.

By kind:

- **manual:** `user_dismissable`, `fire_data`; with a duration, `duration`
  (seconds) and `event_expires`.
- **condition kinds** (`state`, `threshold`, `template`, `on_off`,
  `alert_state`): `condition`, `delay_on`, `delay_off`, `no_data_grace` (seconds),
  `no_data_since`, `missing_inputs`, `delay_on_until`, `delay_off_until`,
  `no_data_grace_until`, and:
  - `state`: `source_entity`, `target_state`;
  - `alert_state`: `source_entity` (the watched alert), `target_states`;
  - `threshold`: `source_entity`, `attribute`, `value_template`, `minimum`,
    `maximum`, `hysteresis`, `value` (the current reading);
  - `template`: `template`;
  - `on_off`: `on_template`, `on_triggers`, `off_template`, `off_triggers`.
- **event kinds** (`trigger`, `event`): `duration`, `event_expires`, `condition`,
  `trigger_data` (the last trigger's variables), and `triggers`, or `event_type`
  and `event_data`.

Generator sensors (`sensor.alert_redux_generator_<name>`): the number of alerts,
with `targets`, `alerts`, and `problems`.

## Events

Every change fires an event carrying `entity_id`, `name`, `priority`, `kind`,
`old_state`, `new_state`, and `user_id` (when a user made the change):

| Event | Also carries |
|---|---|
| `alert_redux_fired` | `fire_count`; `fire_data` (manual) or `trigger_data` (event kinds) |
| `alert_redux_ended` | `fire_count`, `duration_seconds`, `reason`: `resolved`, `dismissed`, `no_data`, `disabled` |
| `alert_redux_acked` | `pre_acked_by` when acknowledged by supersession |
| `alert_redux_unacked` | |
| `alert_redux_snoozed` | `snoozed_until` |
| `alert_redux_snooze_expired` | |
| `alert_redux_disabled` | `disabled_until` (null when indefinite) |
| `alert_redux_enabled` | |
| `alert_redux_no_data` | `missing_inputs` |
| `alert_redux_data_restored` | `missing_inputs` (what was missing) |
| `alert_redux_superseded` | `superseded_by` |
| `alert_redux_created` | |
| `alert_redux_deleted` | |

One change can fire two events: snoozing an active alert fires `_snoozed` then
`_acked`; a snooze running out, `_snooze_expired` then `_unacked`; disabling a
firing alert, `_ended` then `_disabled`.

## Acknowledging, snoozing, disabling, suspending

- **Acknowledging** stops reminders and clears the alert's notifications. A new
  firing starts unacknowledged (unless pre-acknowledged; see Supersession).
- **Snoozing** acknowledges until `snoozed_until`. If it's still firing then, it's
  `active` again and a reminder is sent at once, unless the next scheduled one is
  within the snooze-end window (5 minutes by default).
- **Disabling** ends any firing (done reason `disabled`) and ignores the inputs
  until enabled. **Enabling** starts from scratch: a condition alert waits for
  data and evaluates as new, `delay_on` and all.
- **Suspending** is disabling with an end (`disabled_until`).

## Notifications

- An alert sends an **on** notification when it starts firing, **reminders** on
  its schedule while `active`, and a **done** notification when it stops (even if
  acknowledged). Titles are the alert's name.
- It sends to its own groups, or the default groups. If no default groups are set,
  alerts relying on them send to the fallback, and a Repairs issue says so.
- **Firing again** (manual and event kinds) sends the on message again unless
  acknowledged.
- An event or self-ending manual alert only reminds if its duration outlasts the
  first reminder interval.
- **Throttling:** past the throttle, on and done notifications are held; the one
  that reaches the limit is marked "[Throttling starts]", and a summary is sent
  when the rate drops (`throttled_since` shows it's in force).
- **Quiet hours** (loud groups only): below the threshold priority, notifications
  are held (or softened) while the quiet-hours entity is on; when it turns off,
  still-firing alerts get one reminder and the ones that ended are summarised.
- **Replacing and clearing** (mobile app and persistent notifications): each
  alert's notifications replace one another, and are cleared when it's
  acknowledged or deleted.
- **Buttons** (mobile app): the alert's own buttons, then Acknowledge and Snooze
  Alert; Android shows three. A custom button runs only its configured action, as
  the person who tapped it.
- **Failures:** a missing or failing notifier is retried until the retry timeout
  (5 minutes by default), surviving restarts; if nothing in the group got it, it
  goes to the fallback group.

## Supersession

An alert can **supersede** others (its `supersedes` relationships):

- While it's firing, the alerts it supersedes send no on or reminder
  notifications. Their state is unaffected; `superseded_by` lists the firing
  alerts superseding them. Supersession is transitive.
- When an alert starts firing, its on notification waits out a short debounce
  (0.5 s) in case a superseding alert fires too.
- A done notification is dropped only when both alerts stop together (within the
  done window).
- **Propagation** (per relationship): acknowledging the superseded alert can
  `acknowledge` or `snooze` the superseding one. If that one isn't firing yet,
  it's **pre-acknowledged** (`pre_acked_by`, `pre_snoozed_until`) and starts as
  `ack` when it fires, for as long as the superseded alert stays acknowledged.

The classic pair: *Door Open* (state, no delay) superseded by *Door Left Open*
(same state, `delay_on` 10 minutes, propagation `acknowledge`): you're told the
door opened, and acknowledging that also covers it being left open.

## Restarts

State, snoozes, suspensions, delays, reminders, durations, and throttles survive
restarts. An alert still firing resumes quietly (no new on notification);
deadlines that passed while Home Assistant was down are dealt with when it's back.
After a restart, condition alerts wait for their inputs: those that weren't
firing show `no_data` meanwhile, and those that were stay firing and resume if
their condition still holds.
