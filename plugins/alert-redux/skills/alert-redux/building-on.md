# Building on Alert Redux

## Contents
- Choosing what to listen to
- Automations
- Summary sensors
- Dashboards
- Custom voice sentences
- History

## Choosing what to listen to

| To react to | Use |
|---|---|
| One alert starting, ending, being acknowledged | a `state` trigger on the alert entity |
| Why it ended, who acknowledged it, what fired it | an `event` trigger on its `alert_redux_*` event, filtered by `entity_id` |
| "Anything urgent unacknowledged?" across all alerts | the summary sensors |
| Something only an automation can detect | a **manual** alert, fired and dismissed by the automation |

Don't build a parallel alerting system out of template sensors and automations:
make the condition an alert, and hang the side effects on its state or events.

## Automations

Raise and clear a manual alert from an automation:

```yaml
actions:
  - action: alert_redux.fire
    target:
      entity_id: alert_redux.backup_failed
    data:
      data:
        job: "{{ trigger.event.data.job }}"
```

```yaml
actions:
  - action: alert_redux.dismiss
    target:
      entity_id: alert_redux.backup_failed
```

For a manual alert that should clear itself, turn on its `ends_by_itself` option
rather than adding a delayed `dismiss`.

React to any alert ending, with the reason:

```yaml
triggers:
  - trigger: event
    event_type: alert_redux_ended
conditions:
  - "{{ trigger.event.data.reason == 'resolved' }}"
actions:
  - action: logbook.log
    data:
      name: "{{ trigger.event.data.name }}"
      message: "cleared after {{ trigger.event.data.duration_seconds | int }} s"
```

Event triggers don't take wildcards; list the event types to listen to several.

Act when an alert has been unacknowledged too long: make an **`alert_state`**
alert watching it (`alert_states: [active]`, `delay_on` 30 minutes) rather than an
automation with a `for:`. It then has its own notifications, card entry, and
history. For an alert kept until acknowledged, watch `[active, latched]`, so the
escalation doesn't stop just because the condition did.

## Summary sensors

| Sensor | State |
|---|---|
| `sensor.alert_redux_highest_priority` | highest priority among firing alerts, or `none` |
| `sensor.alert_redux_highest_unacked_priority` | the same, among `active` and `latched` alerts that aren't superseded |
| `sensor.alert_redux_firing` | count of firing alerts (`active` or `ack`) |
| `sensor.alert_redux_active` | count of unacknowledged alerts that aren't superseded: `active`, and `latched` (which still want acknowledging) |
| `sensor.alert_redux_acknowledged` | count of acknowledged alerts |
| `sensor.alert_redux_superseded` | count of alerts that a firing alert supersedes (`active`, `ack`, or `latched`) |
| `sensor.alert_redux_latched` | count of `latched` alerts: stopped firing, not yet acknowledged |
| `sensor.alert_redux_no_data` | count missing data, including firing alerts in their grace period |
| `sensor.alert_redux_disabled` | count disabled or suspended |

Count sensors list their alerts in `entity_ids`; the firing and active sensors
also count each priority (`emergency: 0`, …). For a status light or a badge,
follow `sensor.alert_redux_highest_unacked_priority`.

A superseded alert is hidden on the card and silent, so the unacknowledged
figures (`highest_unacked_priority` and `active`) leave it out, while `firing`
and `highest_priority` still count it. `active` plus `acknowledged` can therefore
be less than `firing`; `sensor.alert_redux_superseded` lists the difference.

## Dashboards

The cards ship with the integration and are registered automatically; no
resource needs adding.

```yaml
type: custom:alert-redux-card
title: Alerts                          # optional
snooze_durations: [15, 30, 60, 120]   # optional: the snooze menu, in minutes
areas: [workshop, garage]              # optional scope: area IDs
labels: [network]                      # optional scope: label IDs
hide_acknowledged: true                # optional: start with acknowledged hidden
priorities: [emergency, critical]      # optional: start showing only these
```

It shows every firing alert (by priority, unacknowledged first, newest first),
with acknowledge, snooze, and (for dismissable manual alerts) dismiss controls,
and the alert's custom buttons (one marked Require unlock asks to confirm);
superseded alerts fold under the alert superseding them, alerts without data are
listed at the bottom, and disabled alerts are only counted.

`areas` and `labels` set the card's **scope**: it shows only alerts in one of the
areas and with one of the labels (each, when set), and leaves the rest out of the
whole card, including the no-data list and the disabled count. Scope applies before
superseded alerts are folded, so an alert whose superseder is out of scope shows on
its own. Area and label IDs are the registry's (an alert's area and labels are set in
its form, or on its entity page). `hide_acknowledged` and `priorities` only set the
starting state of the card's **filter buttons** (hide acknowledged; one per priority
present), which change what's shown without changing the configuration; the card
says how many alerts they hide.

```yaml
type: custom:alert-redux-admin-card
title: All alerts                      # optional
page_size: 20                          # optional: alerts per page; unset shows all
```

Lists every alert by priority with its kind and state; admins get disable,
enable, and suspend controls. Generators that match no entities right now are
listed under the alerts ("Generators with no alerts"), since no alert leads to
them. With `page_size`, the list is paged (still in
priority order, headings counting the whole priority) with previous and next
buttons.

Every row has a **Summary** button (a text summary of the alert's settings, to
copy, or its definition as YAML), and the card has **Export** (all definitions
as YAML, to copy or download) and, for admins, **Import** (paste YAML or JSON, or choose a
file; **Check** is a dry run). They use the `alert_redux.export` and
`alert_redux.import` actions (see [operating.md](operating.md#exporting-and-importing)).

Admins also get **Add alert** and **Add generator** buttons, and Edit and Delete
buttons on each row. They run the same subentry flows as the integration page
(so the forms and their checks are identical); a generated alert's Edit and
Delete act on its generator. Deleting asks first.

Theme variables recolour priorities: `alert-redux-emergency-color`,
`alert-redux-critical-color`, `alert-redux-warning-color`,
`alert-redux-notice-color`, `alert-redux-informational-color`.

Other cards work too. Every alert carries the label **Alert Redux**, so a card
that takes targets (an Activity card, an entities card with a label filter) can
cover every alert, including ones added later, by that one label.

## Custom voice sentences

The voice commands are intents, so custom sentences in any language can use
them (`custom_sentences/<language>/*.yaml`):

| Intent | Slots |
|---|---|
| `AlertReduxAcknowledge` | `name` (optional) |
| `AlertReduxUnacknowledge` | `name` (optional) |
| `AlertReduxSnooze` | `name` (optional), `minutes` (optional, a number) |
| `AlertReduxListFiring` | none |

```yaml
language: de
intents:
  AlertReduxAcknowledge:
    data:
      - sentences:
          - "bestätige [den] [Alarm] {name}"
lists:
  name:
    wildcard: true
```

## History

The logbook (Activity) shows each state change of an alert with who made it, plus
rows for snoozes, snoozes running out, suspensions, supersession, lost and
restored data, and creation and deletion. Point an Activity card at the Alert
Redux label for an alert history of the alerts that exist. A deleted alert drops
out of any view filtered by label, area, or entity, because HA finds those
entities through the entity registry; that's intended for dashboards. To see a
deleted alert's history, "Deleted" row included (for example, to check a
deletion), use the unfiltered Activity panel.
