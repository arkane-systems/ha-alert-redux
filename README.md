# ![icon](assets/alert-redux-32px.png) Alert Redux

A replacement alert system for Home Assistant, intended to take over from the
now-deprecated built-in `alert` integration.

> **Status:** early development (0.8.0). Every alert kind works: manual, state,
> on/off, threshold, template, alert state, trigger, and bus event alerts. The card
> shows, acknowledges, and snoozes them, they send on, reminder, and done
> notifications, the admin card disables and suspends them, alerts can supersede
> each other, and summary sensors and the Activity card make them easy to build on.
> The rest arrives in later releases; see the [phase plan](docs/SPEC.md#20-phase-plan).
> The design is in [docs/SPEC.md](docs/SPEC.md).

## Installation

### HACS

1. In HACS, add `https://github.com/arkane-systems/ha-alert-redux` as a custom
   repository of type **Integration**.
2. Install **Alert Redux** and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and add **Alert Redux**.

### Manual

Copy `custom_components/alert_redux/` into your Home Assistant `config/custom_components/`
directory, restart Home Assistant, and add the integration as above.

Requires Home Assistant 2025.3 or later.

## Alerts

Each alert is an `alert_redux.*` entity, with one of these states:

| State | Meaning |
|---|---|
| `idle` | Not firing. |
| `active` | Firing, and not acknowledged. |
| `ack` | Firing, and acknowledged. |
| `no_data` | Not firing, and its inputs are unavailable, unknown, or won't parse. |
| `disabled` | Disabled, or suspended until `disabled_until`: it can't fire. |

Its attributes show its configuration and current condition: `priority`,
`firing_since`, `fire_count`, who last acknowledged it, `subject_entity` (the entity
it's about), and so on.

To add an alert, go to **Settings → Devices & Services → Alert Redux → Add alert** and
choose its kind. Every alert has a name (which also sets its entity ID), a priority,
and optionally an icon, and can be made unacknowledgeable.

Every alert can also have an **on message** and a **card message**, both templates.
The on message is sent when the alert starts firing (see
[Notifications](#notifications)); the card shows the card message if there is one,
and otherwise the on message. Leave both empty for the default, "{{ name }} is
firing." That's deliberately generic, so give real alerts a specific message.
Templates can use `name`, `subject_entity_name` (the subject entity's name, or else
the alert's), `subject_entity_id`, `entity_id`, `priority`, `fire_count`,
`fire_data` (manual alerts), `trigger` (trigger and bus event alerts), `duration`,
and entity states, e.g.
`Server room is {{ states('sensor.server_room') }} °C.` While an alert is firing,
the rendered messages are in its `message` and `display_message` attributes, and
they update as the entities they read change.

### Manual alerts

A manual alert is fired and dismissed by actions, e.g. from your automations. You can
choose whether the card should offer to dismiss it.

### Condition alerts: state, on/off, threshold, and template

These alerts fire by themselves while their condition holds, and stop when it ends:

- A **state** alert watches one entity, and fires while it's in a given state, e.g.
  `binary_sensor.back_door` is `on`. Targeting `unavailable` gives an "is offline"
  alert.
- An **on/off** alert turns on and off on separate criteria. Each side is a
  template, triggers, or both, and counts when it *becomes* true: "Garage
  intruder" can turn on when motion is detected and off only when the door is
  locked. An on side that's still true after the alert stops has to go false
  before it can fire again.
- A **threshold** alert fires while a value is above a maximum or below a minimum.
  The value is an entity's state, one of its attributes, or a template; each limit
  is a number or a template (e.g. `{{ states('input_number.max') }}`). The
  **hysteresis** is how far back inside the limits the value must come before the
  alert stops: "Server room hot" with a maximum of 30 and hysteresis 2 fires above
  30 °C and ends at 28 °C. The current value is in the `value` attribute.
- A **template** alert fires while a template renders true. The result has to be
  clearly true or false: anything else (an error, `unknown`, `none`, …) counts as no
  data, not as false.

All of them can have:

- an **extra condition**, a template that must also be true;
- **delay before firing** (`delay_on`): the condition must hold this long first.
  "Garage door left open" is a state alert with a 10-minute delay;
- **delay before ending** (`delay_off`): the condition must stay false this long
  before the alert stops firing, absorbing brief flickers;
- a **no-data grace period**; see below.

On/off delays need a template on their side, since triggers alone can't stay true
for the delay.

#### Missing data

When an alert's inputs are unavailable or unknown, it has no data. An alert that
isn't firing shows `no_data` until they return. An alert that *is* firing stays
`active` or `ack` for the grace period (10 minutes by default), with
`no_data_since` and `missing_inputs` showing what's wrong. A sensor that drops out
briefly doesn't end the firing or clear its acknowledgement. If the grace period
runs out, the firing ends.

After a restart, alerts wait in `no_data` for their inputs. Alerts that were firing
stay firing while they wait, and resume quietly if their condition still holds.

### Event alerts: trigger and bus event

These fire on a momentary occurrence, and stay firing for a **duration**:

- A **trigger** alert fires on any Home Assistant trigger, as in an automation.
- A **bus event** alert fires on an event type, optionally only when the event's
  data matches, e.g. `doorbell_pressed` with `button: front`.

Either can have a **condition**, a template checked when the trigger fires. If it
can't be judged (an error, `unknown`), the alert fires anyway and a warning is
logged, so a broken condition never silences it. Messages can use the trigger's
variables as `trigger`, as automations do: `trigger.to_state.state`, or
`trigger.event.data` for a bus event alert.

The duration is the alert's own, or else its priority's default (Emergency 60,
Critical 30, Warning 15, Notice 10, Informational 5 minutes; see
[Global defaults](#global-defaults)). Firing again while it's still firing restarts
the duration and adds to the fire count, but keeps the acknowledgement. An event
alert only sends reminders if its duration is longer than the first reminder
interval. Triggers start once Home Assistant has started (and after the startup
delay), so entities loading at startup don't fire them.

### Snoozing, disabling, and suspending

**Snoozing** acknowledges a firing alert for a while. If it's still firing when the
snooze runs out, it's `active` again (`snoozed_until` shows when), and a reminder is
sent straight away, unless its next scheduled reminder is less than 5 minutes off
(the **snooze-end window**; see [Global defaults](#global-defaults)). Reminders then
carry on from the original schedule. Snoozing an acknowledged alert gives it a new
end, sooner or later; acknowledging a snoozed alert keeps it acknowledged until it
stops firing. Unacknowledgeable alerts can't be snoozed.

**Disabling** turns an alert off, e.g. for maintenance: its state is `disabled`, and
it ignores its inputs until it's enabled again. A firing alert stops firing, and its
done message says it was disabled rather than resolved. Enabling it starts from
scratch: a condition alert waits for data, then evaluates as usual, `delay_on` and
all, so a condition that still holds fires anew. **Suspending** disables an alert
for a while, or until a time (`disabled_until`), and then enables it by itself.
Disabling, enabling, and suspending are for admins only.

Snoozes and suspensions survive a restart; one that ran out while Home Assistant was
down ends as soon as it's back.

### Actions

| Action | Effect |
|---|---|
| `alert_redux.fire` | Fires a manual alert. Optional `data` is kept as `fire_data`. Firing an alert that's already firing adds to its fire count, and keeps its acknowledgement. |
| `alert_redux.dismiss` | Ends a manual alert's firing. (Other kinds end by themselves.) |
| `alert_redux.ack` | Acknowledges a firing alert. |
| `alert_redux.unack` | Removes the acknowledgement (and any snooze). |
| `alert_redux.snooze` | Acknowledges a firing alert for a `duration`. |
| `alert_redux.disable` | Disables an alert until it's enabled. Admin only. |
| `alert_redux.enable` | Enables a disabled or suspended alert. Admin only. |
| `alert_redux.suspend` | Disables an alert for a `duration`, or `until` a time (local time if it has no time zone). Admin only. |

An action that doesn't apply to an alert's current state (such as acknowledging an
idle alert) does nothing.

```yaml
action: alert_redux.fire
target:
  entity_id: alert_redux.back_door_open
data:
  data:
    opened_by: keypad
```

### Events

Every change fires an event. Each carries `entity_id`, `name`, `priority`, `kind`,
`old_state`, `new_state`, and `user_id` (for changes made by a user), and some carry
more:

| Event | Also carries |
|---|---|
| `alert_redux_fired` | `fire_count`; `fire_data` (manual) or `trigger_data` (trigger and bus event) |
| `alert_redux_ended` | `fire_count`, `duration_seconds`, `reason` (`resolved`, `dismissed`, `no_data`, or `disabled`) |
| `alert_redux_acked` | `pre_acked_by`, when acknowledged by supersession |
| `alert_redux_unacked` | |
| `alert_redux_snoozed` | `snoozed_until` |
| `alert_redux_snooze_expired` | |
| `alert_redux_disabled` | `disabled_until` (null when disabled indefinitely) |
| `alert_redux_enabled` | |
| `alert_redux_no_data` | `missing_inputs` |
| `alert_redux_data_restored` | `missing_inputs` (the inputs that were missing) |
| `alert_redux_superseded` | `superseded_by` |
| `alert_redux_created` | |
| `alert_redux_deleted` | |

Home Assistant's event triggers don't take wildcards, but they do take a list. To
listen for all of them:

```yaml
triggers:
  - trigger: event
    event_type:
      - alert_redux_fired
      - alert_redux_ended
      - alert_redux_acked
      - alert_redux_unacked
      - alert_redux_snoozed
      - alert_redux_snooze_expired
      - alert_redux_disabled
      - alert_redux_enabled
      - alert_redux_no_data
      - alert_redux_data_restored
      - alert_redux_superseded
      - alert_redux_created
      - alert_redux_deleted
```

When one change implies another, both fire: snoozing an active alert fires
`_snoozed` then `_acked`; a snooze running out fires `_snooze_expired` then
`_unacked`; disabling a firing alert fires `_ended` then `_disabled`.

Alert state is saved as it changes and restored after a restart.

### Summary sensors

Seven sensors summarise every alert, so glue needs to follow only one entity:

| Sensor | State |
|---|---|
| `sensor.alert_redux_highest_priority` | the highest priority among firing alerts, or `none` |
| `sensor.alert_redux_highest_unacked_priority` | the same, counting only unacknowledged (`active`) alerts |
| `sensor.alert_redux_firing` | how many alerts are firing (`active` or `ack`) |
| `sensor.alert_redux_active` | how many are firing and unacknowledged |
| `sensor.alert_redux_acknowledged` | how many are acknowledged |
| `sensor.alert_redux_no_data` | how many are missing data, including firing alerts in their grace period |
| `sensor.alert_redux_disabled` | how many are disabled or suspended (a diagnostic sensor) |

Each count sensor lists the alerts it counts in its `entity_ids` attribute, and the
firing and active sensors also count each priority (`emergency: 0`,
`critical: 1`, …).

For example, a signal light that shows the most serious unacknowledged alert:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.alert_redux_highest_unacked_priority
actions:
  - choose:
      - conditions: "{{ trigger.to_state.state == 'none' }}"
        sequence:
          - action: light.turn_off
            target:
              entity_id: light.signal
    default:
      - action: light.turn_on
        target:
          entity_id: light.signal
        data:
          color_name: >-
            {{ {'emergency': 'red', 'critical': 'orange', 'warning': 'yellow',
                'notice': 'green', 'informational': 'blue'}[trigger.to_state.state] }}
```

### The Alert Redux label

Every alert gets the label **Alert Redux** when it's created (alerts that existed
before 0.3.1 get it on upgrade). To show all your alerts' history in an Activity
(logbook) card, including alerts you add later, choose that label as the card's
target. If you remove the label from an alert, it isn't put back; if you delete the
label, it isn't recreated.

The Activity card shows each change of an alert's state, with who made it. Alert
Redux adds entries for what a state change can't show: snoozing (and until when), a
snooze running out, suspending (until when), being superseded (and by what), losing
data (and which inputs) and getting it back, and alerts being created and deleted.

The dots beside alert entries in an Activity card are always grey: Home Assistant's
frontend only colours those for its own built-in domains.

## Notifications

Alerts don't name notifiers directly. They send to **notifier groups**, which you
define in Alert Redux: **Settings → Devices & Services → Alert Redux → Add notifier
group**. A group can hold any mix of:

- **notify entities** (`notify.*` entities), which receive the message, and the
  title if they can show one;
- **legacy notify actions**, such as `notify.mobile_app_phone`. These can also take
  extra `data` (e.g. a mobile notification channel) and a `target`. Values in `data`
  can be templates, using the same variables as messages, e.g.
  `group: "{{ priority }}"`;
- a **persistent notification**.

(Groups also have a **loud** flag, for notifiers that make a noise. It's stored now,
for quiet hours in a later release.)

The notification's title is the alert's name. An alert sends:

| Notification | When | Default message |
|---|---|---|
| **On** | It starts firing. | "{{ name }} is firing." |
| **Reminder** | On its reminder schedule, while firing and unacknowledged. | "{{ name }} is still firing ({{ duration }})." |
| **Done** | It stops firing, even if acknowledged. | "{{ name }} stopped firing after {{ duration }}." |

Each message can be replaced with your own template, in the alert's **Notifications
and messages** section. There, `duration` is how long the alert has been firing (or
fired, for the done message), `reason` is `on`, `reminder`, or `done`, and in the
done message `end_reason` is `resolved`, `dismissed`, `no_data`, or `disabled`. The
default done message says when an alert stopped because its data was lost, or
because it was disabled.

- **Which groups:** an alert uses the **default groups** unless you turn that off
  and choose its own; choosing none means it notifies nobody. If no default groups
  are set, alerts that rely on them send to the fallback, and a Repairs issue says
  so.
- **Reminders** follow a list of intervals in minutes, where the last one repeats.
  The default, `10, 20, 30, 60`, reminds at 10, 30, and 60 minutes, then hourly. An
  alert can have its own schedule, or none. Acknowledging stops reminders;
  removing the acknowledgement resumes them on the original schedule, counted from
  when the alert started firing. When a snooze runs out, a reminder is sent at once
  unless a scheduled one is due within the snooze-end window.
- **Firing again:** a manual or event alert fired while it's already firing sends
  its on message again, with the new `fire_count`, unless it has been acknowledged.
- **Restarts:** an alert that was firing resumes without a new on notification. A
  reminder that fell due while Home Assistant was down is sent when it's back.

### Replacing and clearing

On the mobile app and in persistent notifications, each alert's notifications
replace one another, so its reminder takes the place of its on message, and its
done message the place of its last reminder. When the alert is acknowledged
(or snoozed), its notification is cleared. Deleting an alert clears it too.

Mobile app actions (`notify.mobile_app_*`) do this automatically. For other legacy
actions that send to phones, such as a legacy notify group of them, set the
member's **Mobile app features**. Each legacy action member can also **keep the
notification when acknowledged**, or **clear it instead of showing the done
message**; the persistent notification has the same two settings. Notify entities
can't replace or clear: each notification arrives separately.

### Buttons

Mobile app notifications carry buttons: **Acknowledge** and **Snooze** (for an
alert that can be acknowledged), after any of the alert's own. An alert's own
buttons, in its **Notifications and messages** section, each have a label and an
action, e.g. *Close door* running `cover.close_cover` on the garage door. Tapping one
runs only that action, as the person who tapped it; it still works after the alert
has stopped firing. Turn on **Only from an unlocked phone** for anything
security-sensitive (iOS). Android shows at most three buttons, so the alert's own
come first. The done notification has no buttons.

The Snooze button snoozes for the alert's **Snooze button duration**, or else the
default from the integration's options (1 hour).

### When a notifier fails

A notifier that's missing (e.g. its integration hasn't loaded yet) or fails is
retried, with increasing gaps, until the **retry timeout** (5 minutes by default).
Each notifier is retried on its own, a legacy action is retried as soon as it
appears, and pending retries survive a restart.

If a notification reaches none of the notifiers it was sent to, it goes to the
**fallback group**: a persistent notification, unless you choose a group of your
own. It isn't used for alerts set to notify nobody.

A legacy notify action that doesn't exist is raised as a Repairs issue naming its
group. Integrations are gradually replacing legacy actions with notify entities; if
one has, switch the group to the entity. The issue clears itself once the action
exists again or the group no longer uses it.

## Global defaults

The integration's **Configure** button sets:

- the default no-data grace period;
- an optional **startup delay**: how long to wait after Home Assistant starts before
  evaluating condition alerts and starting triggers;
- the default notifier groups and reminder schedule;
- the fallback group, and the retry timeout;
- the **snooze-end window** (5 minutes by default): when a snooze runs out, a
  reminder is sent at once unless the next scheduled one is closer than this;
- the **Snooze button duration** (1 hour by default) for notifications' Snooze
  buttons;
- the default event alert duration for each priority.

## Lovelace card

The Alert Redux card is bundled with the integration: there is no separate frontend
install and no need to add a dashboard resource by hand. When the integration is set
up, it serves the card and registers it as a dashboard resource automatically. (On
YAML-mode dashboards, it is loaded app-wide instead.)

Add it to a dashboard as **Alert Redux** from the card picker, or in YAML:

```yaml
type: custom:alert-redux-card
title: Alerts # optional
snooze_durations: [15, 30, 60, 120, 240] # optional: the snooze menu, in minutes
```

It shows one box per firing alert, most important first: by priority, then
unacknowledged before acknowledged, then newest first. Each is coloured by
priority. Emergency and Critical alerts glow (an unacknowledged Emergency pulses),
and Warning alerts have caution stripes; acknowledging an alert tones this down.
Each box shows the alert's icon, name, how long it's been firing, and its message,
with buttons to acknowledge it (or remove the acknowledgement), to snooze it and,
for manual alerts set as dismissable from the card, to dismiss it. **Snooze** opens
a row of durations below the buttons; a snoozed alert shows how long is left, and
its menu can also keep it acknowledged or unsnooze it. Event alerts have a bar
along the bottom that drains as their duration runs out. Click the icon or name for
the alert's details.

Alerts that have no data are listed in their own section at the bottom, with the
inputs they're missing. Disabled alerts aren't shown, only counted ("2 alerts
disabled"). When nothing is firing, the card says so.

The priority colours can be changed from a theme, with `alert-redux-emergency-color`,
`alert-redux-critical-color`, `alert-redux-warning-color`, `alert-redux-notice-color`,
and `alert-redux-informational-color`.

### Admin card

The admin card lists **every** alert, grouped by priority, with its kind and state
(and when it started firing, when a snooze or suspension ends, and so on). Admins
get buttons to disable or enable each alert, and to suspend it for 1 hour to a week
or until a date and time; everyone else sees the list without them. It comes in the
same install as the main card: add **Alert Redux admin** from the card picker, or

```yaml
type: custom:alert-redux-admin-card
title: All alerts # optional
```

### After installing or upgrading

Browsers load dashboard resources only when the page loads, so a newly installed or
upgraded card isn't used until you refresh the page. Until then, a dashboard may show
"Custom element not found", or the old card. Alert Redux raises a notification when
a new card version needs a refresh, and a card that's older than the integration
offers a **Reload** button. In the companion app, pull down to reload, or reset
the frontend cache from the app's own settings.

## License

MIT; see [LICENSE](LICENSE).
