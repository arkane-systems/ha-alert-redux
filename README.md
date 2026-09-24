# ![icon](assets/alert-redux-32px.png) Alert Redux

A replacement alert system for Home Assistant, intended to take over from the
now-deprecated built-in `alert` integration.

> **Status:** early development (0.2.0). Manual, state, and template alerts work.
> Other condition kinds, event alerts, notifications, and the real card arrive in
> later releases; see the
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

#### Global defaults

The integration's **Configure** button sets the default no-data grace period, and an
optional **startup delay**: how long to wait after Home Assistant starts before
evaluating condition alerts.

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

## Lovelace card

The Alert Redux card is bundled with the integration: there is no separate frontend
install and no need to add a dashboard resource by hand. When the integration is set
up, it serves the card and registers it as a dashboard resource automatically. (On
YAML-mode dashboards, it is loaded app-wide instead.)

Add it to a dashboard as a **Custom: Alert Redux** card, or in YAML:

```yaml
type: custom:alert-redux-card
title: Alerts
```

## License

MIT; see [LICENSE](LICENSE).
