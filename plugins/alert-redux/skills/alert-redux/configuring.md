# Configuring Alert Redux

## Contents
- How the flows work
- Value formats
- Fields every alert has
- The `notifications` section
- The `supersession` section
- The `voice` section
- Fields by kind
- Generators
- Notifier groups
- Global options
- Validation errors
- Examples

## How the flows work

Alerts, generators, and notifier groups are config subentries of the one
`alert_redux` config entry, with the subentry types `alert`, `generator`, and
`notifier_group`.

- **Create:** start the subentry flow for the type. For `alert` and `generator`
  the first step is a **menu** of kinds: answer it with
  `{"next_step_id": "<kind>"}`. The next step is that kind's form (step ID = the
  kind). A `notifier_group` goes straight to its form (step `user`).
- **Edit:** start the subentry's reconfigure flow. The form (step
  `reconfigure_<kind>`, or `reconfigure` for a group) is pre-filled. **Submit the
  whole form**, not just the changed fields. The alert is updated in place and
  keeps its state; a condition alert's pending `delay_on` and `delay_off` restart
  only if its condition changed.
- **Delete:** delete the subentry. Its entity goes with it, and an
  `alert_redux_deleted` event fires.
- **Sections** are nested objects in the submission: `notifications` and
  `supersession` on every alert and generator form, `targets` on generator forms.
  **They're required keys**: send `"supersession": {}` even with nothing in it.
- A changed **name** changes the alert's name, not its entity ID.
- Names must be unique within each subentry type (case-insensitive).

## Value formats

| Type | Format | Example |
|---|---|---|
| duration | object | `{"hours": 0, "minutes": 10, "seconds": 0}` |
| template | string | `"{{ states('sensor.x') | float(0) > 30 }}"` |
| triggers | list, as in an automation's `triggers` | `[{"trigger": "state", "entity_id": "binary_sensor.door", "to": "on"}]` |
| action | list, as in a script's `sequence` | `[{"action": "cover.close_cover", "target": {"entity_id": "cover.garage"}}]` |
| reminder schedule | string of minutes, comma-separated | `"10, 20, 30, 60"` |
| notifier groups | list of group **subentry IDs** | `["01M3D2A71TKEQW9ECF1G30J4TZ"]` |
| priority | one of `emergency`, `critical`, `warning`, `notice`, `informational` | `"warning"` |

Templates that return a value must be **clearly** true or false: anything else
(an error, `unknown`, `none`) counts as no data, not false.

## Fields every alert has

| Field | Type | Notes |
|---|---|---|
| `name` | text, required | Also sets the entity ID when created. |
| `priority` | select, required | Default `warning`. |
| `icon` | icon | Empty: the priority's icon. |
| `acknowledgeable` | boolean, required | Default true. Off: can't be acknowledged or snoozed. |
| `subject_entity` | entity | What the alert is about, for messages. Defaults to the watched entity. |

## The `notifications` section

| Field | Type | Notes |
|---|---|---|
| `use_default_groups` | boolean, required | Default true: the options' default groups. |
| `notifier_groups` | group IDs | Used when `use_default_groups` is false. Empty: notifies nobody. |
| `use_default_reminders` | boolean, required | Default true. |
| `reminder_schedule` | text | Used when `use_default_reminders` is false. Minutes between reminders; the last gap repeats. Empty: no reminders. |
| `use_default_throttle` | boolean, required | Default true. |
| `throttle_count`, `throttle_minutes` | numbers | Used when `use_default_throttle` is false: at most this many on notifications in any window of this many minutes. Both empty: no throttling. |
| `message` | template | The on message, also shown on the card. Default "{{ name }} is firing." |
| `display_message` | template | A different message for the card. |
| `reminder_message` | template | Default gives the name and how long it's been firing. |
| `done_message` | template | Sent when it stops firing. |
| `buttons` | list of `{label, action, require_unlock}` | Mobile notification buttons; `action` is an action sequence. Labels must be filled in. |
| `button_snooze_duration` | duration | How long the Snooze Alert button snoozes. |

Message templates can use `name`, `entity_id`, `priority`, `subject_entity_id`,
`subject_entity_name`, `fire_count`, `fire_data` (manual), `trigger` (trigger and
event kinds), `duration` (how long it has been firing, as text, e.g. "1 hour 5
minutes") and `duration_seconds`, `reason` (`on`, `reminder`, `done`), and in the
done message `end_reason` (`resolved`, `dismissed`, `no_data`, `disabled`),
`started`, and `ended` (ISO times); for generated alerts, also `target` and
`target_name`.

## The `supersession` section

`supersedes`: a list of relationships, each `{alert, propagation,
snooze_duration}`:

- `alert`: the entity ID of an alert this one supersedes. While this alert is
  firing, that one sends no on or reminder notifications.
- `propagation`: what acknowledging **that** alert does to **this** one: `none`
  (default), `acknowledge`, or `snooze` (needs `snooze_duration`).

The form refuses self-references, repeats, and cycles, and propagation to an
unacknowledgeable alert. See [operating.md](operating.md) for how supersession
behaves.

## The `voice` section

Proxies for Alexa and Google Home, which can't see alert entities. Both are
booleans, off by default; generators take them too, for every alert they make.

- `proxy_switch`: a `switch` with the alert's name, on while the alert is
  `active`. Turning it off acknowledges the alert; turning it on removes the
  acknowledgement.
- `proxy_snooze_button`: a `button` named "Snooze" and the alert's name, which
  snoozes the alert for its `button_snooze_duration` (or the global default).

Turning an option off deletes that proxy. Assist needs no proxies: it has its
own voice commands (see [operating.md](operating.md)).

## Fields by kind

### `manual`

| Field | Type | Notes |
|---|---|---|
| `user_dismissable` | boolean, required | Show a dismiss button on the card. The dismiss action works either way. |
| `ends_by_itself` | boolean, required | End by itself after `duration`, like an event alert. |
| `duration` | duration | Empty: the priority's default event duration. |

### `state`

| Field | Type | Notes |
|---|---|---|
| `entity_id` | entity, required | |
| `target_state` | text, required | The raw state, e.g. `on`, not "Open". `unavailable` makes an offline alert. |
| `condition` | template | Extra condition, ANDed in. |
| `delay_on` | duration | The condition must hold this long before firing. |
| `delay_off` | duration | It must stay false this long before ending. |
| `no_data_grace` | duration | How long a firing alert rides out missing data. Empty: the default. |

### `threshold`

| Field | Type | Notes |
|---|---|---|
| `entity_id` | entity | The value's entity, or use `value_template`; not both. |
| `attribute` | text | Read this attribute instead of the state. |
| `value_template` | template | The value, instead of an entity. |
| `minimum`, `maximum` | template | A number (`"30"`) or a template. At least one; minimum < maximum. |
| `hysteresis` | number, required | Default 0. How far back inside the limit before it ends. |
| `condition`, `delay_on`, `delay_off`, `no_data_grace` | | As for `state`. |

### `template`

| Field | Type | Notes |
|---|---|---|
| `template` | template, required | Fires while it renders true. |
| `condition`, `delay_on`, `delay_off`, `no_data_grace` | | As for `state`. |

### `on_off`

| Field | Type | Notes |
|---|---|---|
| `on_template`, `on_triggers` | template, triggers | The on side counts when it *becomes* true. Needs one or both. |
| `off_template`, `off_triggers` | template, triggers | The off side, likewise. |
| `condition`, `delay_on`, `delay_off`, `no_data_grace` | | A delay needs a template on its side. |

### `alert_state`

| Field | Type | Notes |
|---|---|---|
| `alert` | alert entity, required | The alert it watches. Not itself. |
| `alert_states` | list, required | Any of `idle`, `active`, `ack`, `no_data`, `disabled`. Default `["active"]`. |
| `condition`, `delay_on`, `delay_off`, `no_data_grace` | | E.g. `delay_on` 30 minutes on `active`: "unacknowledged for half an hour". |

### `trigger`

| Field | Type | Notes |
|---|---|---|
| `triggers` | triggers, required | No `variables`, and no templated `enabled`. |
| `condition` | template | Checked when it triggers, with `trigger` available. If it can't be judged, the alert fires anyway. |
| `duration` | duration | How long each firing lasts. Empty: the priority's default. |

### `event`

| Field | Type | Notes |
|---|---|---|
| `event_type` | text, required | |
| `event_data` | object | Only events whose data matches. |
| `condition`, `duration` | | As for `trigger`. |

Firing an event alert again while it's firing restarts its duration and keeps
its acknowledgement.

## Generators

A generator's form is its kind's alert form (`state`, `on_off`, `threshold`,
`template`, or `alert_state`), with these differences:

- No `entity_id`, `alert`, or `subject_entity`: the **target** is the entity.
- `name_template` (template): each alert's name. Default: the target's name, then
  the generator's name ("Front Door" + "Unlocked").
- A required `targets` section: `labels` (label IDs), `areas` (area IDs),
  `domains` (list), `device_classes` (list), `pattern` (an entity ID glob, e.g.
  `lock.*_door`), and `exclude` (entity IDs). An entity must match **every**
  criterion that's set, and **any** value within each; labels and areas count
  through the entity's device. At least one criterion.
- Templates get `target` (the entity ID) and `target_name`.
- `supersedes` relationships can name a `generator` (that generator's subentry ID:
  each alert supersedes that generator's alert for the same target) or a fixed
  `alert`, not both.

Generated alerts have entity IDs built from the target and the generator, show
the generator in `generated_by`, and can't be edited on their own. Each generator
has a sensor, `sensor.alert_redux_generator_<name>`, with its `targets`, `alerts`,
and `problems`.

## Notifier groups

| Field | Type | Notes |
|---|---|---|
| `name` | text, required | |
| `entities` | `notify.*` entities | Notify entities: message and title. |
| `actions` | list of members | Legacy actions, see below. |
| `persistent` | boolean, required | Also a persistent notification. |
| `persistent_clear_on_ack` | boolean, required | Default true. |
| `persistent_clear_when_ended` | boolean, required | Clear instead of showing the done message. |
| `loud` | boolean, required | Makes a noise (e.g. TTS); quiet hours apply only to loud groups. |
| `quiet_entity` | entity | This group's own quiet-hours switch (input_boolean, schedule, binary_sensor, or switch). |
| `quiet_threshold` | select, required | `default` or a priority: quiet hours apply below it. |
| `quiet_behaviour` | select, required | `hold` (send when quiet hours end) or `soften` (send with each member's `quiet_data`). |

Each `actions` member: `action` (required, e.g. `notify.mobile_app_phone`; it may
be one that isn't loaded yet), `data` (object; values can be templates using the
message variables), `target` (text), `mobile` (`automatic`, `all`, `no_buttons`,
`none`: replacing, clearing, and buttons; `automatic` means on for
`notify.mobile_app_*` only), `keep_on_ack`, `clear_when_ended`, and `quiet_data`.

A group needs at least one member.

## Global options

The entry's options flow (one step, `init`): `no_data_grace`, `startup_delay`,
`generator_grace`, `default_groups` (group IDs), `default_reminder_schedule`,
`throttle_count`, `throttle_minutes`, `fallback_group`, `retry_timeout`,
`snooze_reminder_window`, `button_snooze_duration`; sections `event_durations`
(one duration per priority), `quiet_hours` (`quiet_entity`, `quiet_threshold`),
and `supersession` (`supersession_debounce`, `done_window`, in seconds).

## Validation errors

A form that's refused comes back with an error key:

| Key | Fix |
|---|---|
| `name_exists` | Pick another name. |
| `invalid_schedule` | Positive minutes, comma-separated. |
| `invalid_throttle` | Both throttle fields, or neither. |
| `invalid_trigger` | Valid triggers, without `variables` or a templated `enabled`. |
| `event_type_missing`, `invalid_event_data` | Set the event type; `event_data` must be a mapping. |
| `value_source` | Threshold: an entity or a value template, not both. |
| `limit_required`, `invalid_limits` | Threshold: at least one limit; minimum < maximum. |
| `criterion_required`, `delay_needs_template` | On/off: each side needs a template or triggers; a delay needs a template. |
| `alert_state_self`, `alert_states_missing` | Watch another alert; choose a state. |
| `supersedes_self`, `supersedes_duplicate`, `supersedes_cycle`, `relationship_target` | Fix the relationships. |
| `propagation_unacknowledgeable` | Set propagation to `none`, or make the alert acknowledgeable. |
| `snooze_duration_missing` | A `snooze` relationship needs `snooze_duration`. |
| `button_incomplete`, `invalid_button_action` | Each button needs a label and a valid action. |
| `targets_required` | Generators: set at least one target criterion. |
| `no_members`, `action_missing`, `invalid_data` | Notifier groups: add a member; set each action; `data` must be a mapping. |

## Examples

A door left open for 10 minutes, to one group, with a Close button:

```json
{"next_step_id": "state"}
```

```json
{
  "name": "Garage Door Left Open",
  "priority": "warning",
  "acknowledgeable": true,
  "entity_id": "cover.garage_door",
  "target_state": "open",
  "delay_on": {"hours": 0, "minutes": 10, "seconds": 0},
  "notifications": {
    "use_default_groups": false,
    "notifier_groups": ["<group subentry ID>"],
    "use_default_reminders": true,
    "use_default_throttle": true,
    "message": "The garage door has been open for 10 minutes.",
    "buttons": [{"label": "Close door", "action": [
      {"action": "cover.close_cover", "target": {"entity_id": "cover.garage_door"}}
    ]}]
  },
  "supersession": {}
}
```

A low-battery alert for every battery sensor (a `threshold` generator):

```json
{
  "name": "Battery Low",
  "priority": "notice",
  "acknowledgeable": true,
  "targets": {"device_classes": ["battery"], "domains": ["sensor"]},
  "minimum": "15",
  "hysteresis": 5,
  "notifications": {"use_default_groups": true, "use_default_reminders": true,
                    "use_default_throttle": true},
  "supersession": {}
}
```

A quiet group for one phone:

```json
{
  "name": "Phone",
  "loud": false,
  "quiet_threshold": "default",
  "quiet_behaviour": "hold",
  "actions": [{"action": "notify.mobile_app_phone", "mobile": "automatic"}],
  "persistent": false,
  "persistent_clear_on_ack": true,
  "persistent_clear_when_ended": false
}
```
