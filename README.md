# ![icon](assets/alert-redux-32px.png) Alert Redux

A replacement alert system for Home Assistant, intended to take over from the
now-deprecated built-in `alert` integration.

> **Status:** early development (0.1.0). Manual alerts work. Condition and event
> alerts, notifications, and the real card arrive in later releases; see the
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

Its attributes show its configuration and current condition: `priority`,
`firing_since`, `fire_count`, who last acknowledged it, and so on.

### Creating a manual alert

A manual alert is fired and dismissed by actions, e.g. from your automations. To add
one, go to **Settings → Devices & Services → Alert Redux → Add alert**. Give it a
name (which also sets its entity ID), a priority, and optionally an icon, then choose
whether it can be acknowledged and whether the card should offer to dismiss it.

### Actions

| Action | Effect |
|---|---|
| `alert_redux.fire` | Fires a manual alert. Optional `data` is kept as `fire_data`. Firing an alert that's already firing adds to its fire count, and keeps its acknowledgement. |
| `alert_redux.dismiss` | Ends a manual alert's firing. |
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
`alert_redux_acked`, `alert_redux_unacked`, `alert_redux_created`, and
`alert_redux_deleted`. Each carries `entity_id`, `name`, `priority`, `kind`,
`old_state`, `new_state`, and `user_id` (for changes made by a user).

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
