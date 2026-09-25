# ![icon](assets/alert-redux-32px.png) Alert Redux

A replacement alert system for Home Assistant, intended to take over from the
now-deprecated built-in `alert` integration.

> **Status:** early development (0.4.0). Manual, state, and template alerts work,
> the card shows and acknowledges them, and they send on, reminder, and done
> notifications. Other condition kinds, event alerts, snoozing, and the rest arrive
> in later releases; see the
> [phase plan](docs/SPEC.md#20-phase-plan). The design is in [docs/SPEC.md](docs/SPEC.md).

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
`fire_data` (manual alerts), `duration`, and entity states, e.g.
`Server room is {{ states('sensor.server_room') }} °C.` While an alert is firing,
the rendered messages are in its `message` and `display_message` attributes, and
they update as the entities they read change.

### Manual alerts

A manual alert is fired and dismissed by actions, e.g. from your automations. You can
choose whether the card should offer to dismiss it.

### State and template alerts

These alerts fire by themselves while their condition holds, and stop when it ends:

- A **state** alert watches one entity, and fires while it's in a given state, e.g.
  `binary_sensor.back_door` is `on`. Targeting `unavailable` gives an "is offline"
  alert.
- A **template** alert fires while a template renders true. The result has to be
  clearly true or false: anything else (an error, `unknown`, `none`, …) counts as no
  data, not as false.

Both can have:

- an **extra condition**, a template that must also be true;
- **delay before firing** (`delay_on`): the condition must hold this long first.
  "Garage door left open" is a state alert with a 10-minute delay;
- **delay before ending** (`delay_off`): the condition must stay false this long
  before the alert stops firing, absorbing brief flickers;
- a **no-data grace period**; see below.

#### Missing data

When an alert's inputs are unavailable or unknown, it has no data. An alert that
isn't firing shows `no_data` until they return. An alert that *is* firing stays
`active` or `ack` for the grace period (10 minutes by default), with
`no_data_since` and `missing_inputs` showing what's wrong. A sensor that drops out
briefly doesn't end the firing or clear its acknowledgement. If the grace period
runs out, the firing ends.

After a restart, alerts wait in `no_data` for their inputs. Alerts that were firing
stay firing while they wait, and resume quietly if their condition still holds.

### Actions

| Action | Effect |
|---|---|
| `alert_redux.fire` | Fires a manual alert. Optional `data` is kept as `fire_data`. Firing an alert that's already firing adds to its fire count, and keeps its acknowledgement. |
| `alert_redux.dismiss` | Ends a manual alert's firing. (Other kinds end by themselves.) |
| `alert_redux.ack` | Acknowledges a firing alert. |
| `alert_redux.unack` | Removes the acknowledgement. |

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

Every change fires an event: `alert_redux_fired`, `alert_redux_ended`,
`alert_redux_acked`, `alert_redux_unacked`, `alert_redux_no_data`,
`alert_redux_created`, and `alert_redux_deleted`. Each carries `entity_id`, `name`,
`priority`, `kind`, `old_state`, `new_state`, and `user_id` (for changes made by a
user). `alert_redux_ended` also carries a `reason` (`resolved`, `dismissed`, or
`no_data`), and `alert_redux_no_data` the `missing_inputs`.

Alert state is saved as it changes and restored after a restart.

### The Alert Redux label

Every alert gets the label **Alert Redux** when it's created (alerts that existed
before 0.3.1 get it on upgrade). To show all your alerts' history in an Activity
(logbook) card, including alerts you add later, choose that label as the card's
target. If you remove the label from an alert, it isn't put back; if you delete the
label, it isn't recreated.

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
done message `end_reason` is `resolved`, `dismissed`, or `no_data`. The default done
message says when an alert stopped because its data was lost.

- **Which groups:** an alert uses the **default groups** unless you turn that off
  and choose its own; choosing none means it notifies nobody. If no default groups
  are set, alerts that rely on them send to the fallback, and a Repairs issue says
  so.
- **Reminders** follow a list of intervals in minutes, where the last one repeats.
  The default, `10, 20, 30, 60`, reminds at 10, 30, and 60 minutes, then hourly. An
  alert can have its own schedule, or none. Acknowledging stops reminders;
  removing the acknowledgement resumes them on the original schedule, counted from
  when the alert started firing.
- **Firing again:** a manual alert fired while it's already firing sends its on
  message again, with the new `fire_count`, unless it has been acknowledged.
- **Restarts:** an alert that was firing resumes without a new on notification. A
  reminder that fell due while Home Assistant was down is sent when it's back.

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
  evaluating condition alerts;
- the default notifier groups and reminder schedule;
- the fallback group, and the retry timeout.

## Lovelace card

The Alert Redux card is bundled with the integration: there is no separate frontend
install and no need to add a dashboard resource by hand. When the integration is set
up, it serves the card and registers it as a dashboard resource automatically. (On
YAML-mode dashboards, it is loaded app-wide instead.)

Add it to a dashboard as **Alert Redux** from the card picker, or in YAML:

```yaml
type: custom:alert-redux-card
title: Alerts # optional
```

It shows one box per firing alert, most important first: by priority, then
unacknowledged before acknowledged, then newest first. Each is coloured by
priority. Emergency and Critical alerts glow (an unacknowledged Emergency pulses),
and Warning alerts have caution stripes; acknowledging an alert tones this down.
Each box shows the alert's icon, name, how long it's been firing, and its message,
with buttons to acknowledge it (or remove the acknowledgement) and, for manual
alerts set as dismissable from the card, to dismiss it. Click the icon or name for
the alert's details.

Alerts that have no data are listed in their own section at the bottom, with the
inputs they're missing. When nothing is firing, the card says so.

The priority colours can be changed from a theme, with `alert-redux-emergency-color`,
`alert-redux-critical-color`, `alert-redux-warning-color`, `alert-redux-notice-color`,
and `alert-redux-informational-color`.

### After installing or upgrading

Browsers load dashboard resources only when the page loads, so a newly installed or
upgraded card isn't used until you refresh the page. Until then, a dashboard may show
"Custom element not found", or the old card. Alert Redux raises a notification when
a new card version needs a refresh, and a card that's older than the integration
offers a **Reload** button. In the companion app, pull down to reload, or reset
the frontend cache from the app's own settings.

## License

MIT; see [LICENSE](LICENSE).
