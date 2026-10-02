# Troubleshooting Alert Redux

## Contents
- Start with the attributes
- It doesn't fire
- It shows `no_data`
- It fires but nobody is told
- Repairs issues
- Refused actions
- Voice
- Generators
- The cards
- Logs

## Start with the attributes

An alert's attributes explain most behaviour: read them before changing anything.
`missing_inputs`, `delay_on_until`, `superseded_by`, `next_reminder`,
`throttled_since`, `disabled_until`, `broken_references`, and `value` (threshold)
usually answer the question directly.

## It doesn't fire

- `disabled`: it's disabled or suspended (`disabled_until`). Enable it (admin).
- `delay_on_until` is set: the condition holds, and the delay is counting down.
- A `state` alert's `target_state` must be the **raw** state (`on`, `open`,
  `unavailable`), not the displayed one ("Open", "Detected").
- A template that renders something other than a clear true or false counts as
  no data, not false: check `missing_inputs`.
- The extra `condition` is ANDed in.
- An `on_off` side counts only when it *becomes* true; one that was already true
  must go false first.
- Trigger and event alerts start listening only after Home Assistant has started
  (plus the startup delay). An event alert's `event_data` must match exactly.
- A trigger, event, or on/off alert whose triggers can't be attached shows as
  **unavailable**: fix the triggers.

## It shows `no_data`

`missing_inputs` lists the entities (or templates) that are unavailable, unknown,
or won't parse. A firing alert rides out missing data for its grace period
(`no_data_grace_until`), then ends with reason `no_data`. After a restart,
condition alerts show `no_data` until their inputs report.

## It fires but nobody is told

Check in this order:

1. `notifier_groups` is empty: the alert notifies nobody (deliberately, or the
   default groups aren't set; then there's a Repairs issue).
2. It's `ack`: acknowledged or snoozed alerts send no reminders.
3. `superseded_by` isn't empty: a superseding alert is firing.
4. `throttled_since` is set: notifications are held until the rate drops.
5. Quiet hours: a loud group holds lower priorities while its quiet-hours entity
   is on.
6. `reminder_schedule` is empty: the alert has no reminders, or (event kinds and
   self-ending manual alerts) its duration doesn't outlast the first reminder
   interval, which the attribute shows as an empty schedule.
7. The notifier itself failed: check the log, and the fallback group (a
   persistent notification unless set otherwise).

## Repairs issues

| Issue | Meaning | Fix |
|---|---|---|
| `default_groups_unset` | Alerts rely on default groups, but none are set. | Set default groups in the options. |
| `notify_action_missing` | A group names a legacy `notify.*` action that doesn't exist. | Fix the group, or switch it to the notify entity. |
| `broken_reference` | An alert refers to an alert that doesn't exist (`broken_references`). | Recreate it, or edit the referring alert. |
| `broken_generator_reference` | A generator refers to a generator or alert that doesn't exist. | Edit the generator. |
| `quiet_entity_missing` | A quiet-hours entity doesn't exist. | Fix the options or the group. |

They clear themselves once fixed. Renaming an alert's entity ID in the registry
rewrites references to it; deleting an alert doesn't.

## Refused actions

| Error | Cause |
|---|---|
| `not_manual` | `fire` or `dismiss` on an alert that isn't manual. |
| `not_acknowledgeable` | `ack` or `snooze` on an unacknowledgeable alert. |
| `not_firing` | A proxy switch turned on, or a proxy snooze button pressed, while its alert isn't firing. |
| `suspend_in_past` | `suspend` with `until` in the past. |
| `not_generator` | `refresh_generator` on something that isn't a generator sensor. |
| `not_exportable` | `export` with an entity that isn't an Alert Redux alert or generator. |
| `import_refused` | `import` found problems, and imported nothing; the message lists them (codes in [operating.md](operating.md#exporting-and-importing)). |
| `not_set_up` | `export` or `import` while Alert Redux isn't set up. |
| Unauthorized | `disable`, `enable`, `suspend`, or `import` by a non-admin user. |

## Voice

- **"I don't know an alert called …"**: the alert isn't exposed to Assist
  (Settings → Voice assistants → Expose), or the name doesn't match; add an
  alias to the alert's entity.
- **Assist doesn't recognise the sentence at all** with Speech-to-Phrase: it
  only knows sentences it was trained on, and can't learn these. Use another
  speech-to-text engine, or type the command.
- **An LLM agent turns the alert off instead**: check that the agent has the
  Assist API (control) enabled; the alert_redux__ tools come with it.
- **Alexa or Google doesn't see a proxy**: check that the proxy is exposed to
  it, then ask the assistant to discover devices. Manual (non-cloud) setups
  pick entities with their own filters.

## Generators

The generator's sensor (`sensor.alert_redux_generator_<name>`) shows its
`targets`, its `alerts`, and its `problems` (e.g. a name template that failed).

- An entity that should match doesn't: criteria are AND across, OR within; labels
  and areas count through the device; disabled entities, configuration entities,
  and generated alerts are never targets.
- Alerts don't disappear at once at startup: removals wait for the generator
  startup grace (5 minutes by default).
- `alert_redux.refresh_generator` re-evaluates at once.

## The cards

"Custom element not found", or an old card after an upgrade: refresh the
browser (in the companion app, pull down to reload). A card older than the
integration offers a Reload button.

## Logs

The logger is `custom_components.alert_redux`. Set it to `debug` (with
`logger.set_level`) to see evaluations, held reminders, and notifier retries;
set it back afterwards.
