---
name: alert-redux
description: Configures, operates, and builds on Alert Redux, the Home Assistant alerting integration (domain alert_redux) that replaces the built-in alert integration. Use when creating, editing, or deleting Alert Redux alerts, generators, or notifier groups; firing, acknowledging, snoozing, or suspending alerts; writing automations or dashboards on alert_redux entities, events, or summary sensors; or troubleshooting alerts that don't fire, notify, or show as expected.
---

# Alert Redux

Alert Redux is a Home Assistant custom integration. Each alert is an
`alert_redux.*` entity with a state machine, notifications, and history. All
configuration is UI-only: there is no YAML. Everything is done through Home
Assistant's config subentry flows, actions, and events, so any way of driving Home
Assistant works (an MCP server, the websocket API, or the UI).

## The model

- **One config entry** (domain `alert_redux`, title "Alert Redux"). Everything else
  hangs off it as **config subentries** of three types:
  - `alert`: one alert of one **kind**, chosen from a menu when it's created
    (`manual`, `state`, `on_off`, `threshold`, `template`, `alert_state`, `trigger`,
    `event`). The kind can't be changed afterwards: delete and recreate instead.
  - `generator`: makes one alert per matching **target** entity (condition kinds
    only). Its alerts are edited only through the generator.
  - `notifier_group`: where notifications go. Alerts and options refer to groups
    by their **subentry ID**, not by name.
- The entry's **options** hold the global defaults (default groups, reminder
  schedule, durations, quiet hours, and so on).
- **States:** `idle`, `active` (firing, unacknowledged), `ack` (firing,
  acknowledged), `no_data` (inputs missing), `disabled` (disabled or suspended).
- **Priorities**, highest first: `emergency`, `critical`, `warning`, `notice`,
  `informational`.
- An alert's entity ID comes from its name when it's created
  (`alert_redux.back_door_open`).

## Rules

1. **Never edit `.storage` files.** Use the subentry flows and actions.
2. **Find IDs, don't guess them.** List the entry's subentries to get subentry IDs
   (for editing, deleting, and notifier groups).
3. **Check before deleting an alert.** Its edit form says which alerts refer to
   it ("Alerts that refer to this one: …"). Deleting it leaves their references
   broken, with a Repairs issue. When deleting a set of alerts that refer to each
   other, delete the referrers first.
4. **Test quietly.** For test alerts, turn off the default notifier groups and
   choose a quiet group, or none (an empty list notifies nobody). Loud groups (TTS
   announcements, say) queue up when a test flickers. Name test alerts so they're
   recognisable, and delete them afterwards.
5. **Leave alone what you didn't create.** Existing alerts, generators, and groups
   may be someone's working setup: change them only when asked.
6. **Read the live form when in doubt.** Fields can change between versions. An
   edit form shows its fields and the alert's current settings; a create form
   can't be read before submitting, but a refused submission returns its fields
   with the error.

## Where to look

- **Creating or editing** alerts, generators, notifier groups, or the global
  options: [configuring.md](configuring.md). Every form's fields, their types, the
  validation errors, and worked examples.
- **Using** alerts (actions, states, attributes, events, supersession, snoozing,
  notifications): [operating.md](operating.md).
- **Building on top** (automations, scripts, dashboards and the cards, summary
  sensors, the logbook): [building-on.md](building-on.md).
- **Something's wrong** (an alert won't fire, won't notify, shows `no_data`, a
  Repairs issue, a refused action): [troubleshooting.md](troubleshooting.md).
- **Using the HA-MCP server** (`ha-mcp`): its tool names and quirks for all of the
  above: [ha-mcp.md](ha-mcp.md).

## Choosing a kind

| Need | Kind |
|---|---|
| An automation decides when it starts and stops | `manual` (optionally ending by itself after a duration) |
| An entity is in a given state (door `on`, device `unavailable`) | `state` |
| A value is above or below a limit | `threshold` |
| Anything a template can express | `template` |
| Separate criteria for turning on and turning off | `on_off` |
| Another alert has been in a state for a while (e.g. unacknowledged for 30 minutes) | `alert_state` |
| A momentary occurrence (button press, trigger) that stays up for a while | `trigger`, or `event` for a bus event |
| The same alert for many similar entities (every lock, every battery) | a generator |

Prefer `state` and `threshold` to templates where they fit: they report missing
data precisely (`missing_inputs`). For "X has been open for 10 minutes", use a
`state` alert with `delay_on`, not a template.
