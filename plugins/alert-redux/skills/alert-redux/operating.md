# Operating Alert Redux

## Contents
- Actions
- States
- Attributes
- Events
- Acknowledging, snoozing, disabling, suspending
- Notifications
- Supersession
- Voice
- Exporting and importing
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
| `alert_redux.press_button` | `label` (required) | Run one of the alert's custom buttons by its label, as the main card does: only its action, as the caller, whatever the alert's state. |
| `alert_redux.refresh_generator` | `entity_id`: generator sensors | Re-evaluate a generator's targets now. For debugging. |
| `alert_redux.export` | `entity_id`: alerts or generator sensors (optional; default all) | Return alert and generator definitions as response data. Anyone may call it. |
| `alert_redux.import` | `definitions` (the export's form), `overwrite` (default off), `dry_run` (default off) | Create or replace alerts and generators. **Admin only.** Returns what was created, updated, and left unchanged. |

`export` and `import` aren't entity actions: `export` takes an optional
`entity_id` list, and neither takes a `target`. See Exporting and importing.

An action that doesn't fit the current state (acknowledging an idle alert) does
nothing. These raise errors instead:

- `fire` or `dismiss` on a non-manual alert: `not_manual`.
- `ack` or `snooze` on an unacknowledgeable alert: `not_acknowledgeable`.
- `suspend` until a time in the past: `suspend_in_past`.
- `refresh_generator` on something that isn't a generator sensor: `not_generator`.
- `press_button` with a label the alert doesn't have: `no_such_button`.
- `export` with an entity that isn't an Alert Redux alert or generator: `not_exportable`.
- `import` that would change nothing because it's refused: `import_refused`,
  with every problem listed.

## States

| State | Meaning |
|---|---|
| `idle` | Not firing. |
| `active` | Firing, unacknowledged. Reminders are sent. |
| `ack` | Firing, acknowledged (or snoozed: `snoozed_until` is set). |
| `latched` | Stopped firing without being acknowledged, on an alert set to **Keep until acknowledged** (`latching`). Reminders carry on until it's acknowledged. |
| `no_data` | Not firing, and its inputs are unavailable, unknown, or won't parse. |
| `disabled` | Disabled, or suspended until `disabled_until`. Ignores its inputs. |

A **firing** alert whose inputs disappear stays `active` or `ack` for its no-data
grace period, with `no_data_since` and `missing_inputs` set; if the grace runs
out, the firing ends with reason `no_data`. A `latched` alert stays `latched`
when its inputs disappear, with `no_data_since` set.

**Latching alerts.** With `latching` on, a firing that ends while `active` (for
any reason but disabling) goes to `latched`, not `idle`: the freezer that was
warm for ten minutes at 3 a.m. is still there in the morning. A firing that was
acknowledged or snoozed before it ended goes to `idle` as usual. While latched:

- `acknowledge` (by any route: action, card, voice, notification button, proxy
  switch) releases it to `idle` and clears its notifications; `_acked` fires with
  `old_state` `latched`. `unack` does nothing: it isn't acknowledged.
- `snooze` puts its reminders off: it stays `latched` with `snoozed_until`, fires
  `_snoozed` (not `_acked`), and when the snooze runs out, `_snooze_expired`
  (not `_unacked`) and the snooze-end reminder.
- If it fires again, it's `active` again and sends its on notification, but it's
  the same item: `fire_count` carries on counting. Acknowledge it then, and it
  ends as `idle`.
- `dismiss` (manual alerts) latches only when no user is behind it: a person
  dismissing it has seen it; an automation hasn't.
- Disabling it clears the latch (no `_ended`, since it wasn't firing); turning
  `latching` off releases it to `idle`, without recording an acknowledgement.
- `message` and `display_message` stay rendered, so the card can show them.

## Attributes

Every alert: `kind`, `priority`, `acknowledgeable`, `latching`, `subject_entity`,
`firing_since`, `last_fired`, `last_ended`, `fire_count`, `last_acked`,
`last_acked_by`, `last_unacked`, `last_unacked_by`, `snoozed_until`,
`last_snoozed`, `last_snoozed_by`, `disabled_until`, `last_disabled`,
`last_disabled_by`, `last_enabled`, `last_enabled_by`, `message` and
`display_message` (rendered while firing), `notifier_groups` (names),
`reminder_schedule`, `next_reminder`, `throttle`, `throttled_since`, `supersedes`,
`superseded_by`, `pre_acked_by`, `pre_snoozed_until`, `broken_references`,
`buttons` (labels), `buttons_require_unlock` (the labels marked Require unlock), `generated_by` (the generator's sensor, for generated alerts).
The `_by` attributes are user IDs. `fire_count` counts the fires of the
**current** firing (firing again adds to it), and goes back to 0 when the firing
ends; `fire_data` and `firing_since` clear then too. A latched alert keeps its
`fire_count` and `fire_data` (and adds to the count if it fires again) until
it's acknowledged; `last_ended` is when it stopped.

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
firing alert, `_ended` then `_disabled`. Latching has no event of its own:
`_ended` has `new_state` `latched`, and acknowledging it fires `_acked` with
`old_state` `latched` and `new_state` `idle`.

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
  its schedule while `active` or `latched`, and a **done** notification when it
  stops (even if acknowledged). Titles are the alert's name.
- **Latched alerts** keep the schedule counted from when the item first fired.
  Their reminders say how long ago it stopped ("…stopped firing 25 minutes ago
  and hasn't been acknowledged"); in message templates, `latched` is true and
  `duration` is the time since it stopped. A done notification of a firing that
  latched adds "It's kept until acknowledged.", keeps its Acknowledge and Snooze
  buttons, and stays clearable (it isn't final), with `latched` true.
- It sends to its own groups, or the default groups. If no default groups are set,
  alerts relying on them send to the fallback, and a Repairs issue says so.
- **Firing again** (manual and event kinds) sends the on message again unless
  acknowledged.
- An event or self-ending manual alert only reminds if its duration outlasts the
  first reminder interval, unless it's latching: then its reminders carry on
  once it has latched.
- **Throttling:** past the throttle, on and done notifications are held; the one
  that reaches the limit is marked "[Throttling starts]", and a summary is sent
  when the rate drops (`throttled_since` shows it's in force).
- **Quiet hours** (loud groups only): below the threshold priority, notifications
  are held (or softened) while the quiet-hours entity is on; when it turns off,
  still-firing and latched alerts get one reminder and the ones that ended are
  summarised.
- **Replacing and clearing** (mobile app and persistent notifications): each
  alert's notifications replace one another, and are cleared when it's
  acknowledged or deleted.
- **Buttons** (mobile app): the alert's own buttons, then Acknowledge and Snooze
  Alert; Android shows three. A custom button runs only its configured action, as
  the person who tapped it.
- **iOS interruption levels** (mobile app): on and reminder notifications of
  Emergency alerts are sent as `critical`, and Critical alerts as `time-sensitive`
  (`push: {interruption-level: …}`), so they get through Focus and silent modes.
  There's no setting; a mobile member's own `data` with `push.interruption-level`
  wins (its other `push` keys are kept), so a phone can be pinned to a level.
  Done notifications, summaries, and quiet-hours softened deliveries never get one.
  On an iPhone, `critical` comes through Do Not Disturb and silent mode, but
  `time-sensitive` came through a Sleep Focus and not through Do Not Disturb unless
  Home Assistant is allowed there.
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
  A superseding alert that's `latched` is acknowledged (or snoozed) at once, and
  so it is when the superseded alert is acknowledged while itself `latched`.
- A `latched` alert isn't firing, so it supersedes nothing. A `latched` alert
  that a firing alert supersedes is hidden and silent like a firing one.

The classic pair: *Door Open* (state, no delay) superseded by *Door Left Open*
(same state, `delay_on` 10 minutes, propagation `acknowledge`): you're told the
door opened, and acknowledging that also covers it being left open.

## Voice

**Assist** understands these English commands, through the built-in agent and
through any pipeline, LLM agents included (the sentences are checked first):

- "acknowledge [the] *name* [alert]", "ack …"
- "unacknowledge *name*", "remove the acknowledgement from *name*"
- "snooze *name*", "snooze *name* for 30 minutes" (digits or words; without a
  duration, the alert's `button_snooze_duration`)
- "what alerts are firing?", "are there any alerts?", "list the alerts" (the
  reply adds the `latched` alerts: "… stopped firing but hasn't been
  acknowledged")

Acknowledge and snooze work on `latched` alerts too; unacknowledge says it
isn't acknowledged.

Names match the alert's name or entity aliases, ignoring case, "the", and a
trailing "alert"; a part of the name works if only one alert has it. With no
name ("acknowledge the alert"), it acts only if exactly one alert fits, and
otherwise asks which. Voice only reaches alerts **exposed to Assist**: each
alert is exposed once, when it's first added, and stays unexposed if someone
unexposes it. The commands use the ordinary actions, so who gave them is
recorded (`last_acked_by` and so on), and §6's refusals apply. LLM agents get
the same commands as tools, named alert_redux__ and the intent (see
[building-on.md](building-on.md)).

**Alexa and Google Home** use the proxies (`proxy_switch`,
`proxy_snooze_button`), which are exposed to them when created, and hidden from
Assist:

| Alert state | Switch | Turning it off | Turning it on |
|---|---|---|---|
| `active` | on | acknowledges | nothing |
| `latched` | on | acknowledges | refused: `not_firing` |
| `ack` (snoozed too) | off | nothing | removes the acknowledgement and snooze |
| `idle`, `no_data`, `disabled` | off | nothing | refused: `not_firing` |

An unacknowledgeable alert's switch refuses to turn off. The snooze button
snoozes for the alert's snooze button duration, and refuses (`not_firing`) when
the alert isn't firing or `latched`. Both have an `alert` attribute (the alert's entity ID);
the button also has `snooze_duration` (seconds). On Alexa, a switch is also a
contact sensor, open while on, so an Alexa routine can announce an alert firing.
The proxies take the alert's area and labels, but not the "Alert Redux" label.

## Exporting and importing

`alert_redux.export` returns (use `return_response`) the definitions as they are
stored, which is also what `import` takes. It is the way to copy alerts to
another instance, keep them under version control, or script changes: there are
no create or edit actions, and an import goes through the same checks as the
forms.

```json
{
  "format": "alert_redux",
  "version": 1,
  "alerts": [
    {
      "id": "01M3D2A71TKEQW9ECF1G30J4TZ",
      "name": "Garage Door Left Open",
      "kind": "state",
      "priority": "warning",
      "acknowledgeable": true,
      "entity_id": "cover.garage_door",
      "target_state": "open",
      "delay_on": {"hours": 0, "minutes": 10, "seconds": 0},
      "notifier_groups": ["Phone"]
    }
  ],
  "generators": []
}
```

- A definition is the form's fields, **flattened** (no `notifications`,
  `supersession`, or `voice` sections) and **as stored**: a setting that uses the
  default is simply absent, a reminder schedule is a list of minutes
  (`[10, 20]`), a throttle is `[count, minutes]` (`[]` for none). The field
  names are those in [configuring.md](configuring.md). A generator has
  `name_template` and `targets`, and no entity (state, threshold) or alert
  (alert state); its relationships name a `generator` or an `alert`.
- **Notifier groups are written by name**, and so are the generators in a
  generator's relationships. Import turns the names back into this instance's
  groups and generators, ignoring case; a name that doesn't exist is a problem.
  Groups themselves aren't exported: create them first. Areas and labels in a
  generator's `targets` and `placement` are the registry's IDs, and aren't checked.
  An alert's own area and labels (its `placement`) aren't exported: they live in the
  entity registry.
- **`id`** is the definition's subentry ID. Import keeps it, so importing a file
  again, here or on another instance, finds the same definitions. Leave it out
  in a hand-written file: the definition then matches the existing one of the
  same type and name (ignoring case), or is new.
- Durations may be written as a number of seconds or `"HH:MM:SS"`; they are
  stored as the duration object. A priority or acknowledgeability left out is
  `warning` and `true`, as in the forms. Fields that are empty are left out.
- A definition identical to the existing one is `unchanged`, so repeating an
  import is harmless. A **different** one replaces the existing one only with
  `overwrite`; its kind can't change (`kind_changed`; delete and import again).
  An alert's runtime state, its area, and its labels aren't touched.
- **All or nothing.** Everything is checked first, including supersession cycles
  across the whole file, and if anything is wrong nothing is imported and the
  error (`import_refused`) lists each problem as `<type> '<name>': <code>
  (<detail>)`. `dry_run` does the checks, returns what would happen, and changes
  nothing.

| Problem code | Meaning |
|---|---|
| `invalid_file` | Not an export: wrong `format` or `version`, or an unknown top-level key. |
| `invalid_definition` | A missing name or required field, an unknown field, a wrong type, or an unknown kind; the detail says which. |
| `duplicate_in_file` | Two definitions with the same name (or id) in the file. |
| `exists` | It would replace an existing definition and `overwrite` is off. |
| `name_exists` | Its name is another definition's. |
| `id_in_use` | Its id belongs to a subentry of another type. |
| `kind_changed` | It would change an existing definition's kind. |
| `entity_id_clash` | A new alert's entity ID would be another alert's. |
| `unknown_group`, `unknown_generator` | A name that doesn't match a group or generator. |
| `relationship_target` | A generator relationship names both, or neither, of a generator and an alert. |

Any other code is the forms' validation error for the same mistake: see
[configuring.md](configuring.md).

## Restarts

State, snoozes, suspensions, delays, reminders, durations, and throttles survive
restarts. An alert still firing resumes quietly (no new on notification);
deadlines that passed while Home Assistant was down are dealt with when it's back.
After a restart, condition alerts wait for their inputs: those that weren't
firing show `no_data` meanwhile, and those that were stay firing and resume if
their condition still holds. A `latched` alert stays `latched`, and a reminder
that fell due while Home Assistant was down is sent once.
