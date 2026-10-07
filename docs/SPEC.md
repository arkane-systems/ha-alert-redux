# Alert Redux — Specification

**Status:** version 1, approved. All sections reviewed, every open question
resolved, and the phase plan (§20) agreed. Built from the notes in [spec-notes.md](spec-notes.md);
IDs in brackets (N7, R2, F12, …) refer to that file.

Each substantive point carries a status tag:

- **[Decided]** — agreed during brainstorming.
- **[Proposed]** — my recommendation, usually answering one of the F-questions. It
  becomes Decided once you accept it, or changes if you don't.
- **[Open]** — still needs a decision; also listed in §18.
- **[Deferred]** — wanted, but designed and built in a later phase.

---

## 1. Purpose

Alert Redux is a Home Assistant custom integration that replaces the deprecated
built-in `alert` integration. It also ships the Lovelace cards for using it, from the
same repository and in the same HACS install.

## 2. Principles

1. **Transparency** [Decided, N1]. You can understand an alert entirely from its
   entity: its state and attributes show everything about its current condition, and
   as much of its configuration as reasonably fits.
2. **Easy to build on** [Decided, N2, R5, R17]. State changes go out as HA events,
   and summary sensors describe the alert system as a whole. The aim is that other
   integrations (such as ha-accent-signal-light) can be connected with simple
   automations.
3. **Configured in the UI only** [Decided, R21]. There's no YAML configuration, so
   there's only one set of configuration code to write, and it follows where HA is
   heading.
4. **Actions, not APIs** [Decided, R20]. Other components interact with Alert Redux
   through HA actions (services) and events; there's no Python API.
5. **Resilient** [Decided, N33]. Late-arriving entities, late notifiers, and
   integrations restarting mid-run are normal events, not errors.
6. **Serious by design** [Decided, R19]. No bulk dismissing; each alert is dealt with
   on its own.

## 3. Terminology

[Decided, F10] The spec uses these terms consistently:

| Term | Meaning |
|---|---|
| **Alert** | One configured alert and its `alert_redux.*` entity. |
| **Firing** | The alert's triggering condition currently holds: its state is `active` or `ack`. |
| **Notification** | A message sent to notifiers *about* an alert. Alerts fire; notifications are sent. |
| **Notifier group** | A named set of notifiers, defined in Alert Redux and flagged loud or quiet. Alerts send to groups, not to notifiers directly (§9.3). |
| **Acknowledge (ack)** | Mark a firing alert as seen. This stops reminders until the alert stops firing. |
| **Snooze** | Acknowledge for a limited time (§6.2). |
| **Disable** | Turn an alert off so that it can't fire at all (§6.3). |
| **Suspend** | Disable for a limited time (§6.4). Alert2 calls this "snooze"; we don't. |
| **Supersede** | One alert takes precedence over another and suppresses the other's notifications (§8). |
| **Dismiss** | End a manual alert's firing (§4.3). |

## 4. Alert kinds

Every alert is exactly one of the kinds below. [Decided, N3, N5, N6, R2]

### 4.1 Condition alerts

A condition alert fires while its condition holds, and ends when the condition
changes. It can't be fired or dismissed manually [Decided, R3].

| Kind | Configuration |
|---|---|
| **State** | One entity plus a target state, e.g. `binary_sensor.leak` is `on`. The simple case, equivalent to the built-in `alert`. [Decided, phase 2] A target state of `unavailable` or `unknown` counts as a match, not as missing data, so "lock unavailable for 10 minutes" is a state alert with a `delay_on`. Only a missing entity is no data for such an alert. [Decided, phase 13, N38] A target state is the entity's real state, e.g. `on` for a door binary sensor: typing its displayed name, "open", never matches. Recognising displayed names was considered and dropped: translations, device classes, and entities' own state names make it a lot of added complexity for marginal gain. It may be revisited if Home Assistant's state selector becomes usable for this. |
| **On/off** | Separate *on* and *off* criteria, each a condition and/or trigger. Turns on when the on criterion becomes true, and off when the off criterion becomes true (edge-triggered, as in Alert2). [Decided, phase 5] Each side is a template, triggers, or both. A template-only side counts on its false-to-true change; a side with triggers counts when one fires while its template (if any) is true. The off side is edge-triggered too: an off criterion already true when the alert fires has to go false and true again. An unknown previous value counts as false, so an on criterion already true when a new alert is first evaluated fires it. The edge state is persisted, so a restart or a data dropout doesn't create a false edge. Only the side that can change the state counts for missing data (the on side while idle, the off side while firing). |
| **Threshold** | A numeric value (from an entity, attribute, or template) with a minimum and/or maximum, and hysteresis. The limits can themselves come from entities or templates [P18]. [Decided, phase 5] The limits are templates, where a plain number works as-is. It fires when the value is strictly above the maximum or below the minimum, and a firing ends once the value is back inside by the hysteresis (an absolute amount, default 0). A value, or a configured limit, that isn't a number means no data. |
| **Template** | A template that evaluates to true or false. The fully general option. [Decided, phase 2] Only a clearly true or false result counts (`true`/`on`/`yes`/`1`, `false`/`off`/`no`/`0`, or a real boolean or number). An error, an undefined variable, or a result of `none`, `unknown`, `unavailable`, or anything else means no data (§4.4). A template binary sensor would read those as false, but for an alert that silently hides a broken template. |
| **Alert state** | [Decided, F24] Fires when another alert has been in a given state (e.g. `active`, meaning unacknowledged) for a given time. This gives escalation without templates (§8.4). [Decided, phase 7] The watched alert is chosen by entity ID, and the states are a set: `active` alone means unacknowledged, and `active` plus `ack` means firing. "For a given time" is the alert's `delay_on`, so it's kept across restarts, and it starts again whenever the watched alert leaves those states (acknowledging it, say). The watched alert is the subject entity. A missing or `unavailable` watched alert means no data. |

All condition alerts support:

- **`delay_on`** [Decided, N5]: the condition must hold continuously for this long
  before the alert fires.
- **`delay_off`** [Decided, F9, F12]: the condition must be false continuously for
  this long before the alert stops firing. This absorbs flicker at the *state* level.
  Otherwise a momentary drop would end the firing, which clears its acknowledgement
  (§6.1) and sends a done notification.
- An optional extra **condition** combined (AND) with the main criterion (threshold
  kind in particular) [P18].
  - [Decided, phase 2] It's a **template**, judged like the template kind, and
    tracked reactively. HA's condition selector would be friendlier, but HA
    conditions can't be tracked, so time-based ones would need polling.
  - [Decided, phase 2] It's simply part of the condition: while it's false, the alert
    doesn't fire, and if it turns false while the alert is firing, `delay_off` runs and
    then the alert ends.
  - [Decided, phase 2] If either the main criterion or the extra condition has no
    data, the alert has no data, even if the other one is false (§4.4).
- [Decided, phase 5] On/off alerts' `delay_on` and `delay_off` need the side to
  hold, so they need a template on that side; the form refuses a delay on a
  trigger-only side. The extra condition gates the on edge, and ends a firing
  (after `delay_off`) when it turns false, as for the other kinds.

### 4.2 Event alerts

An event alert fires on a momentary occurrence and then stays firing for a set
**duration** [Decided, N4]. It can't be fired or dismissed manually; it ends when the
duration runs out [Decided, R2, R3].

| Kind | Configuration |
|---|---|
| **Trigger** | Any HA trigger, plus an optional condition that must be true when the trigger fires [Decided, R2, P16]. [Decided, phase 2] The condition is a template, for consistency with the condition alerts' extra condition (§4.1), even though it's only checked at the moment the trigger fires. |
| **Bus event** | An event type on the HA event bus, plus an optional filter on the event data [Decided, R2]. |

- **Duration** comes from the alert's own setting, or else from its priority's default
  (§5) [Decided, N4].
- **Firing again while still firing** [Decided, F2]: restarts the duration from the
  new event, adds one to the fire count, and updates the message context. It
  **doesn't** clear an acknowledgement. The alert is still the same firing, so an
  event that repeats frequently doesn't cause repeated nagging. The fire-again
  notification is subject to throttling (§9.8).
  [Decided, phase 4] The fire-again notification is the on message again, with the
  new fire count, and it's sent only while the alert is `active`. An acknowledged
  alert that fires again sends nothing: keeping the acknowledgement is what stops
  the nagging. (Manual alerts do the same, §4.3.)
- The card shows a draining progress bar for the remaining duration (§13.1).
- [Decided, phase 5] The per-priority default durations are Emergency 60, Critical
  30, Warning 15, Notice 10, and Informational 5 minutes. Changing a duration, or
  the defaults, applies from the next fire; a running firing keeps its expiry.
- [Decided, phase 5] A condition that has no data when the trigger fires (an
  error, or a result that isn't clearly true or false) doesn't stop the alert: it
  fires, and a warning is logged. A broken condition must never silence it (as
  §12.4). The bus event kind also takes the optional condition, which comes free
  with the shared engine.
- [Decided, phase 5] Triggers attach once HA has started, as automations' do, and
  after the startup delay (§15.3), so entities loading at startup don't fire them.
  A trigger that can't be attached makes the alert `unavailable` (§7.1), and the
  error is logged. There's no `no_data` state for event alerts.
- [Decided, F23] Internally, both kinds share one engine: a bus event alert is a
  trigger alert with an `event` trigger. Keeping it as a separate kind is purely to
  make configuration simpler.

### 4.3 Manual alerts

A manual alert is fired and dismissed by a pair of actions
(`alert_redux.fire` / `alert_redux.dismiss`) [Decided, R2]. It's the only kind that
can be dismissed [Decided, R3]. Manual alerts must be declared in advance; there are
no ad-hoc alerts [Decided, R4].

- [Decided] `fire` can pass message variables, which are available to message
  templates as `fire_data`.
- [Decided] Firing an already-firing manual alert behaves like an event alert firing
  again (§4.2): it adds to the fire count and doesn't clear an acknowledgement.
- [Decided] **Dismissable from the card** is a per-alert setting, which supports
  both ways of using manual alerts:
  - *On*: the alert is raised and left for a person to dismiss, so the card shows a
    dismiss button.
  - *Off*: the alert behaves like the other kinds. An automation dismisses it once
    the underlying problem is fixed, so the card shows no dismiss button.

  Either way, the `alert_redux.dismiss` action always works, so automations can
  dismiss any manual alert. The setting is exposed as the `user_dismissable`
  attribute. [Decided] It defaults to *off*: a dismiss button is then something you
  opt into deliberately, and it's less likely to be turned on by accident.
- [Decided; 1.0.0] **End by itself after.** A manual alert can optionally end by
  itself, like an event alert (§4.2): fired by `alert_redux.fire`, it then stays
  firing for a duration. This fills the gap between manual alerts, which stay until
  dismissed, and event alerts, which can't be fired by action. (Today that needs a
  bus event alert listening for a made-up event.)
  - The option is off by default. When it's on, the duration is the alert's own, or
    else its priority's default event duration (§5), as for event alerts.
  - Firing again while it's firing restarts the duration, adds to the fire count,
    and keeps the acknowledgement, as for event alerts.
  - It can still be dismissed early: the `alert_redux.dismiss` action always works,
    and the card's dismiss button follows *Dismissable from the card* as usual.
  - Everything else follows event alerts: the card's progress bar (§13.1), reminders
    only if the duration outlasts the first reminder interval (§9.6), the expiry
    kept across restarts, and the `duration` and `event_expires` attributes.
  - It stays a manual alert, not a new kind. Event alerts still can't be fired by
    action (R2), and manual alerts are still the only kind that can be dismissed
    (R3).

### 4.4 Missing data

When an entity or template that an alert depends on is `unavailable` or `unknown`, or
won't parse (e.g. a non-numeric threshold value), the alert goes into its
**no-data** state instead of raising an error [Decided, N7].

- [Decided] If the alert was firing, it keeps its firing state and acknowledgement
  while it waits for data, until a grace period runs out. That way a sensor briefly
  dropping out doesn't end the firing and trigger done and "on" notifications. The
  grace period is set per alert, with a global default. [Decided, phase 2] The
  default is 10 minutes.
- [Decided, phase 2] During the grace period the entity **stays `active` or
  `ack`**. Its `no_data_since` and `missing_inputs` attributes show that data is
  missing, and a `_no_data` event is fired (§11.3). It still counts as firing
  (§3), so summary sensors and signal lights don't drop out with the sensor, and
  automations watching its state don't see the flicker the grace period exists to
  prevent. If the grace period runs out, the firing ends (`_ended` with reason
  `no_data`) and the state becomes `no_data`. An alert that isn't firing goes to
  `no_data` at once.
- [Decided, phase 2] Missing data interrupts pending delays. `delay_on` needs the
  condition to hold *continuously*, and while there's no data, nobody knows whether
  it stopped holding. So both delays start afresh when data returns.
- [Decided] An alert that has just started up, or been re-enabled, is in the no-data
  state until its inputs first report data (§15).
- Alerts with no data are listed in their own section on the card (§13.1) and counted
  by a summary sensor (§11.2).

## 5. Priority

[Decided, N10] Five levels, a modified syslog hierarchy, from highest to lowest:
**Emergency, Critical, Warning, Notice, Informational**.

Priority affects:

- display order and colour on the cards [Decided, N10];
- sort order whenever alerts compete for attention [Decided, N10];
- the default event-alert duration (§4.2) [Decided, N4];
- the default icon; each priority has an icon list to pick from [Decided, N14, F4];
- which alerts quiet hours apply to (§9.9) [Decided, R9].

[Decided, F4] Priority does **not** set default notifier groups or reminder schedules.
Those have a single global default and can be overridden per alert. Otherwise the
precedence rules would get complicated for little gain; revisit if that proves wrong.

## 6. Acknowledging, snoozing, disabling, suspending

### 6.1 Acknowledging

[Decided, N19]

- Acknowledging a firing alert changes its state from `active` to `ack`. On the card
  it's shown as acknowledged, and it sorts below unacknowledged alerts of the same
  priority. Reminders stop.
- You can remove the acknowledgement manually, which returns the alert to `active`
  and restarts reminders.
- The acknowledgement clears automatically when the alert stops firing, so a new
  firing always starts unacknowledged. **Exception:** the pre-acknowledgement
  described in §8.3 [Decided, F13].
- The done notification is still sent when an acknowledged alert stops firing
  [Decided, R10].
- [Decided, phase 15] A **latched** alert (§10) is acknowledged too: that
  releases it to `idle`. It can't be unacknowledged, since it isn't.
- [Decided, phase 6] Acknowledging a **snoozed** alert makes it a plain
  acknowledgement: the snooze is cleared, and the alert stays acknowledged until it
  stops firing. `_acked` fires, with `ack` as both the old and new state.
- **Unacknowledgeable** alerts can't be acknowledged or snoozed [Decided, N9,
  F14]. The action is refused with an error, and the card shows no
  acknowledge controls for them.

### 6.2 Snoozing

[Decided, N20] Snoozing acknowledges the alert and starts a timer. If the alert is
still firing when the timer runs out, it becomes unacknowledged and reminders
resume. The timer is cleared if the alert stops firing, or if the acknowledgement is
removed manually.

[Decided] **Snooze-end reminder rule.** This applies to ordinary snoozes and to
pre-snoozes (§8.3). When a snooze runs out and the alert is still firing:

- one reminder is sent **immediately**, so the alert speaks up again;
- **unless** the next slot on the alert's original reminder schedule (counted from
  when it actually started firing) is less than 5 minutes away. In that case the
  immediate reminder is skipped and the slot's reminder does the job, so there's no
  double reminder;
- after that, reminders follow the original schedule;
- reminders always give the real firing duration.

[Decided] The 5-minute threshold is a global setting, with 5 minutes as its default.
[Decided, phase 6] It's the **snooze-end window** option
(`snooze_reminder_window`). An alert with no reminders (an empty schedule,
including short event alerts, §9.6) sends nothing when its snooze runs out: it
becomes `active`, and that's all.

[Decided, phase 15] Snoozing a **latched** alert (§10) puts its reminders off
without acknowledging it: it stays `latched`, with `snoozed_until`.

[Decided, phase 6] Snoozing takes a duration. Re-snoozing an acknowledged alert,
snoozed or not, replaces the deadline with *now + duration*, even if that's sooner.

[Decided, F3] There's no separate state for snoozing. A snoozed alert is `ack` with
a `snoozed_until` attribute. Snoozing is a kind of acknowledgement, and keeping the
state list small keeps automations simple. Anything that needs to tell them apart can
check the attribute or listen for the snooze events (§11.3).

### 6.3 Disabling

[Decided, N21] A disabled alert can't fire. Its state is `disabled` and it ignores
all its inputs.

- **This isn't HA's entity-registry "disable"**, which removes the entity entirely
  and would hide it from view [Decided, F19].
- [Decided, F15] Disabling a firing alert ends the firing: a done notification is
  sent, saying the alert was disabled, not resolved.
- [Decided, F15] Re-enabling it starts from scratch: the alert goes into its no-data
  state until its inputs report data, and then evaluates normally, including
  `delay_on`. If it fires, that's a new firing with a fresh notification.
- Unacknowledgeable alerts **can** be disabled, e.g. for maintenance [Decided, F14].
- [Decided, phase 6] A disabled alert ignores its inputs by detaching from them: a
  condition alert stops its sources, triggers, and timers, and an event alert
  detaches its triggers. Firing or dismissing a disabled manual alert, and
  acknowledging, unacknowledging, or snoozing a disabled alert, do nothing (§16).
- [Decided, phase 6] Disabling clears everything about the firing and its
  evaluation: the acknowledgement and snooze, reminders, pending delays, the no-data
  state, event expiry, and on/off latches. The done message's default is "{{ name }}
  was disabled; stopped firing after {{ duration }}." (`end_reason` `disabled`).
- [Decided, phase 6] Re-enabling starts from scratch. Condition alerts go to
  `no_data` and wait for data, with no delays to honour; on/off edges are armed
  again, so an on criterion that's already true fires, as for a new alert (fails
  loud). Manual and event alerts go straight to `idle`. `_enabled` is the only
  event; waiting for data fires none, as at startup.
- [Decided, phase 6] Disabling, enabling, and suspending are **admin-only**
  actions. They're maintenance and debugging tools, not everyday operations;
  acknowledging and snoozing stay open to everyone.

### 6.4 Suspending

[Decided, N22, F16] Suspending disables an alert until a given time, or for
a given duration, after which it re-enables automatically as in §6.3. The name
*suspend* keeps it clearly separate from *disable* and *snooze*.

[Decided, F16] As with snoozing, there's no separate state: a suspended alert is
`disabled` with a `disabled_until` attribute.

[Decided, phase 6] The latest call wins. Suspending an alert that's already
disabled or suspended sets the new time; disabling a suspended alert makes it
indefinite. Each fires `_disabled` (old state `disabled`). Disabling an alert
that's already indefinitely disabled does nothing. The action takes exactly one of
`duration` or `until` (a time without a time zone is local time); an `until` that
isn't in the future is an error.

## 7. States and lifecycle

### 7.1 States

[Decided, N8, F1]

| State | Meaning |
|---|---|
| `idle` | Enabled and has data, but not firing. |
| `active` | Firing and not acknowledged. |
| `ack` | Firing and acknowledged (or snoozed; see `snoozed_until`). |
| `latched` | [Decided, phase 15] Stopped firing without being acknowledged, on an alert kept until acknowledged (§10). |
| `no_data` | The alert can't evaluate its inputs because they're unavailable, unknown, or won't parse. |
| `disabled` | Disabled (or suspended; see `disabled_until`). |

[Decided, F1] Use **`no_data`**, not `unavailable`. `unavailable` has a special
meaning throughout HA: the frontend greys the entity out, and state attributes go
missing. That would hide exactly the information N1 wants shown. HA's own
`unavailable` remains for the rare case where the alert entity itself is broken,
such as a configuration error.

### 7.2 Transitions

```
                  fires                          ack / snooze
   idle ──────────────────────────▶ active ─────────────────────▶ ack
    ▲                                  │  ◀─────────────────────   │
    │                                  │    unack / snooze ends    │
    │           stops firing           │                           │
    └──────────────────────────────────┴───────────────────────────┘

   fires        = condition met (after delay_on) · event received · manual fire
   stops firing = condition ends (after delay_off) · duration elapsed · manual dismiss

   latching alert, active ── stops firing ──▶ latched ── fires ──▶ active
                                              └── ack ──▶ idle  (§10)
   idle ── inputs missing ──▶ no_data ── inputs return ──▶ re-evaluate
   active/ack ── inputs missing ──▶ (stays active/ack) ── grace ends ──▶ no_data
                                                  └── inputs return ──▶ re-evaluate
   any state ── disable / suspend ──▶ disabled ── enable / suspension ends ──▶ no_data
```

(A firing alert keeps its `active`/`ack` state through the grace period; see §4.4.
Only condition alerts go to `no_data` when enabled; manual and event alerts go
straight to `idle`, §6.3.)

## 8. Supersession

### 8.1 Basics

[Decided, N11, R15] An alert can list alerts it **supersedes**. While a superseding
alert is firing, the alerts it supersedes don't notify (with one exception for done
notifications; see below).

- Supersession is **transitive**: if A supersedes B and B supersedes C, then A
  supersedes C [Decided, R15].
- A **debounce** (default 0.5 s) applies: when an alert starts firing, its
  notification waits that long to see whether an alert superseding it also starts
  firing [Decided, R15].
- [Decided, F7] Supersession affects notifications only. A superseded alert keeps
  its own state, in line with N1, and its attributes include `superseded_by`. It can
  stop firing before the alert that supersedes it; that's fine. [Decided; phase 13]
  Notifications aren't all it affects: the card hides a superseded alert, so the
  summary sensors' *unacknowledged* figures leave it out too (§11.2), or a signal
  light would ask for an acknowledgement of something the user can't see. Its
  state, and so the alert itself, are unchanged.
- [Decided] While the superseding alert is firing, the superseded alert sends no on
  or reminder notifications. Its **done** notification follows §9.7: it's dropped
  only if both alerts stop firing together.
- [Decided, F7] On the main card, superseded alerts are **hidden behind a
  disclosure toggle** under the alert that supersedes them, e.g. "▸ 1 superseded
  alert", and collapsed by default. Alerts that are implied by another alert then
  don't clutter the card (§13.1).
- Supersession cycles (A ⊃ B ⊃ A) are a configuration error.
- [Decided, phase 7] An alert refers to the alerts it supersedes by **entity ID**,
  in a collapsed **Supersession** section of its form, as a list of
  relationships (so that each can carry its propagation setting, §8.2). The form
  refuses the alert itself, repeats, and cycles.
- [Decided, phase 7] `superseded_by` lists the **firing** alerts that supersede
  this one, transitively, highest priority first. It's shown whether or not this
  alert is firing. `supersedes` lists the configured alerts.
- [Decided, phase 7] The debounce applies only to alerts that something
  supersedes; others notify at once, as before. When it ends, the on notification
  is sent only if the alert is still `active` and not superseded. A dropped on
  notification is never sent late. Reminders keep their schedule, but a slot that
  falls due while the alert is superseded is skipped, as is the snooze-end
  reminder (§6.2). The debounce is the **supersession debounce** option.
- [Decided, 0.11.1] **A reminder about to be superseded is held.** A superseding
  alert whose `delay_on` matches a slot of the superseded alert's reminder
  schedule (Door Left Open, 10 minutes after Door Open, against the default first
  reminder at 10 minutes) would otherwise send the reminder and the on
  notification together, since at that instant nothing supersedes the reminder
  yet. So when a reminder of an alert that something supersedes (and that isn't
  superseded already) falls due:
  - if a superseding alert, transitively, has a `delay_on` counting down that
    ends within the **snooze-end window** (§6.2; a reminder that close to
    something else speaking up is redundant), the reminder is held until then
    plus the debounce;
  - otherwise it waits out the debounce, as an on notification does, for a
    superseding alert that fires unannounced (manual and event alerts).

  When the hold ends, the reminder is skipped if a superseding alert is firing,
  and otherwise sent late, with the real firing duration; the schedule carries
  on from its original slots. `next_reminder` shows the held time. Only
  scheduled reminders are held, not the snooze-end reminder. A hold isn't
  stored as such: after a restart, the held time is simply a reminder due.

### 8.2 Propagating acknowledgements

[Decided, N12, N13] Each supersession relationship has a **propagation** setting.
It controls what acknowledging the **superseded** alert does to the alert that
supersedes it:

| Setting | Effect | Example |
|---|---|---|
| **None** (default) | Nothing. | Acknowledging *Server Room Overheated (Warning)* leaves *(Critical)* alone. |
| **Acknowledge** | Pre-acknowledges the superseding alert (§8.3). | Acknowledging *Workshop Door Open* also covers *Workshop Door Left Open*. |
| **Snooze** (with a duration) | Pre-snoozes the superseding alert (§8.3). If you take long enough, it speaks up again. | Acknowledging *Back Door Open* keeps *Left Open* quiet for an hour, but no longer. |

The default is **None** [Decided]: acknowledgements pass along a supersession only
when you explicitly set that up.

- [Decided, phase 7] Propagation is set on the superseding alert, per
  relationship in its Supersession list: nothing, acknowledge, or snooze with a
  duration. It follows **direct** relationships only. Snoozing the superseded
  alert counts as acknowledging it.
- [Decided, phase 7] If the superseding alert is already firing and `active`,
  propagation acts at once: *Acknowledge* acknowledges it, and *Snooze* snoozes
  it until the acknowledgement time plus the duration, both with the
  acknowledging user. The pre-acknowledgement also stays in place for a later
  firing. An alert that's already acknowledged is left as it is.
- [Decided, phase 7] A superseding alert that **fires** pre-acknowledged counts
  as acknowledged, so it propagates onwards along its own relationships. A
  pre-acknowledgement on an alert that isn't firing doesn't chain.

### 8.3 Pre-acknowledgement

[Decided, F5, F13] Propagation usually happens before the superseding alert has
fired. So acknowledging the superseded alert **pre-acknowledges** the superseding one:

- The pre-acknowledgement lasts while the superseded alert is firing. It's cancelled
  when that alert stops firing, or has its acknowledgement removed.
- If the superseding alert fires during that time, it starts as `ack` instead of
  `active`. This is the one exception to "a new firing starts unacknowledged".
- The pre-acknowledgement is shown as an attribute on the superseding alert
  (`pre_acked_by`).
- Propagation to an **unacknowledgeable** alert is a configuration validation error
  [Decided, F6].
- [Decided, phase 7] `pre_acked_by` is a **list** of entity IDs, since several
  superseded alerts can pre-acknowledge the same alert. A plain
  pre-acknowledgement beats a pre-snooze, and among pre-snoozes the latest
  deadline wins; `pre_snoozed_until` is that deadline, or null while a plain one
  is in force. They're shown while a pre-acknowledgement is in force, firing or
  not, and a pre-snooze is forgotten once its deadline passes.
- [Decided, phase 7] Pre-acknowledgements are kept by the superseded alert's
  unique ID, so renaming it doesn't affect them, and they're restored across
  restarts. One whose source has gone, or is no longer acknowledged, is dropped.

**Pre-snoozing** (the *Snooze* setting) works the same way, plus a deadline:

- [Decided] The snooze timer starts when you acknowledge the superseded alert, not
  when the superseding alert fires. The deadline is *acknowledgement time +
  duration*, which matches the intent: "if you take long enough, it speaks up".
- [Decided] If the superseding alert fires before the deadline, it starts as `ack`
  with `snoozed_until` set to the deadline, and then behaves like any snoozed alert
  (§6.2). If it fires after the deadline, it starts as `active`, as normal.
- Until the superseding alert fires, the deadline is shown alongside `pre_acked_by`
  as `pre_snoozed_until`.

**Notifications for a pre-acknowledged firing:**

- [Decided] A superseding alert that fires pre-acknowledged sends **no** on
  notification. That's the point of the workshop example: you're there, you know.
- [Decided] Its done notification is still sent (§9.7). In the workshop example,
  closing the door ends both alerts together, so you get exactly one done
  notification: the superseding alert's.
- [Decided] If a pre-snooze deadline passes while the alert is still firing, it
  becomes `active` and **no** on notification is sent, not even a late one.
  Instead, reminders start from that point, as if the alert had been on its normal
  reminder schedule since it actually started firing. A late on notification would
  make it look as if the alert had only just started, and the times in the messages
  would then be confusing. Reminders always give the real firing duration.
- [Decided] Reminders resume by the **snooze-end reminder rule** (§6.2): one
  reminder is sent immediately, then the original schedule carries on. Example: the
  alert fired at 10:00 with schedule `[15, 30, 60]`, and the pre-snooze ended at
  10:50. A reminder goes out at 10:50 ("still firing, 50 min"), and the next is at
  11:45, the next slot on the original schedule (10:15, 10:45, 11:45, …).
- The done notification follows in due course, as always (§9.7).

### 8.4 Escalation and delayed notification

These are done with supersession, not as separate features [Decided, R8, R11]:

- **Escalation:** a superseding alert with a longer `delay_on`, a higher priority, or
  different notifier groups. To escalate only when nobody has acknowledged, use the
  **alert state** condition kind (§4.1) against the superseded alert.
- **Delayed first notification** (the built-in `skip_first`): a first alert with an
  empty notifier group list shows up on the card at once, and a superseding alert with a
  `delay_on` sends the notification.

## 9. Notifications

### 9.1 The notifier module

[Decided, R24] All notification delivery lives in a **self-contained module** inside
the integration (its own package, with its own tests). The rest of Alert Redux talks
to it through a narrow interface:

- *send this notification (title, message, buttons, lifecycle key) to notifier
  group X*;
- *is group X currently quiet?*;
- *clear the notification with this lifecycle key from group X* (§9.10).

[Decided, phase 9] As built, clearing doesn't name groups: the notifier is told
that the notifications with a key have been **acknowledged** (it clears them from
the members set to), or to **clear** them everywhere (a deleted alert), or that
a key has changed (a renamed alert). It remembers which members are showing each
key's notification, so clearing reaches exactly those (§9.10).
[Decided, phase 10] Quiet hours are the notifier's own: each notification
carries an **urgency**, a number that Alert Redux maps from its priority, and
thresholds are urgencies too. When a group's quiet hours end, the notifier hands
its held notifications to its owner, which says what to send instead (§9.9).

The module handles notifier kinds, groups, retries (§15.2), the fallback, quiet-hours
delivery rules, notification replacing and clearing, and turning buttons into each
notifier's format. The aim is that it can later be pulled out into a general-purpose
integration of its own, without redesign [Decided, N36, R24].

### 9.2 Notifier kinds

[Decided, S1–S4] HA currently has three incompatible ways to notify. The module
supports all three:

| Kind | How it sends | What it can do |
|---|---|---|
| **Entity** | `notify.send_message` to a `notify.*` entity | Message, and title if the entity supports it. Nothing else. |
| **Legacy action** | A `notify.<name>` action | Message, title, `data`, `target`. `data` is what makes mobile features possible: `tag`, `clear_notification`, action buttons, critical alerts. |
| **Persistent** | `persistent_notification.create` / `.dismiss` | Message, title, and `notification_id`, so notifications can be replaced and dismissed. |

- Legacy actions are deprecated one integration at a time (S3). Mobile app
  notifications with any of the features above are still only possible through the
  legacy action (S4), so supporting legacy actions is required, not optional.
- When a legacy action disappears, e.g. after an integration has moved to entities,
  its group members stop working. That's treated like any other missing notifier:
  retried, then the fallback is used (§9.4), and a Repairs issue names the member so
  it can be switched to the entity (as in §12.4).
  [Decided, phase 4] The issue names the group and the action. It's raised when a
  member gives up because its action is missing, and also for every missing action
  once integrations have had the retry timeout (§15.2) to set up after startup;
  after that, for a group edited to use a missing action. It clears itself when the
  action is registered, or the group no longer uses it. Missing notify *entities*
  are only logged.

### 9.3 Notifier groups

[Decided, N35, R25] Alerts never name notifiers directly. They name **notifier
groups**, which Alert Redux defines itself. Each group is a **config subentry**, like
alerts and generators (§12.1).

A group has:

- **Members:** any mix of the three notifier kinds. Each member can have settings
  that only make sense for its kind:

  | Member setting | Applies to | Purpose |
  |---|---|---|
  | `data` template | Legacy action | Extra `data` merged into every notification, e.g. a mobile notification channel. Templates can use the notification's context (§9.5). |
  | `target` | Legacy action | Passed through as `target`. |
  | Replace and clear | Legacy (mobile), persistent | How earlier notifications for the same alert are replaced or cleared (§9.10). |
  | Buttons | Legacy (mobile) | Whether this member shows buttons (§9.11). Detected automatically for `notify.mobile_app_*`. |

  [Decided, phase 9] A legacy action member's **mobile app features** are
  *Automatic* (replace, clear, and buttons for `notify.mobile_app_*`, none for
  other actions), *Replace, clear, and buttons*, *Replace and clear; no
  buttons* (e.g. a legacy notify group of phones), or *None*. Each legacy member
  also has **keep the notification when acknowledged** and **clear instead of
  showing the done message**; the persistent member has **clear when
  acknowledged** (on by default) and **clear when the alert ends** (off by
  default). The form can't give fields in a list defaults, so an unset field
  means the default.
  | Quiet-hours `data` | Legacy action | Alternative `data` used when the group *softens* during quiet hours (§9.9). |

  [Decided, phase 10] A group's quiet-hours settings (its own entity and
  threshold, and hold or soften) are on the group form, for loud groups only;
  they're stored only when they aren't the defaults.

- **Loud or quiet** [Decided, N35]. Only you know which notifiers make noise, and
  integrations can't tell us (N34: `notify_mqtt` can't even know who's listening).
  So every group is flagged:
  - **quiet**, e.g. a text message: delivered at any time;
  - **loud**, e.g. a speaker announcement: quiet hours apply (§9.9).

  A group holding both kinds of destination should be split into two groups, and an
  alert can use both.
- [Decided; phase 13] Mobile members send higher-priority alerts with iOS
  **interruption levels** matching their priority, so they get through Focus and
  silent modes: `critical` for Emergency and `time-sensitive` for Critical, sent as
  the mobile app's `push: {interruption-level: …}`. There's no setting for it; if
  there's demand for time-sensitive lower-priority alerts, it can be added then.
  - Only the **on** and **reminder** notifications carry a level, since the alert is
    asking for attention. Done notifications and the summaries (throttling, quiet
    hours) don't.
  - Only **mobile-app members** get it (`notify.mobile_app_*`, or a member whose
    mobile setting says to treat it as one; the same test as for replacing and
    buttons), since other notify actions may reject an unknown key.
  - **The member's own data wins**: if its `data` sets `push.interruption-level`,
    that is kept, and its other `push` keys are merged with it. That pins a phone to
    a level, whatever the priority.
  - A **softened** quiet-hours delivery (§9.9) never gets it.
  - The level travels with the notification (`Notification.interruption`), so a
    retried or held notification keeps it; the notifier module doesn't know about
    priorities, the owner chooses the level.
  - Android ignores `push`, so nothing changes there.
  - Critical notifications bypass Do Not Disturb and silent mode, and need Critical
    Alerts allowed for the app in iOS settings. Time-sensitive notifications are, by
    default, read aloud by Siri (on AirPods, say), which iOS settings can turn off.
  - [Checked on an iPhone, phase 13] An Emergency (`critical`) alert came through
    Do Not Disturb with sound, despite the silent switch. A Critical
    (`time-sensitive`) one came through a Sleep Focus but **not** through Do Not
    Disturb, which lets through only what you allow: so a Critical alert reaches a
    phone in Do Not Disturb only if Home Assistant is allowed there. A message sent
    straight to the app with the same level behaved the same, so this is how iOS
    treats the level, not something Alert Redux does.
- [Decided] Groups are **not** exposed for use outside Alert Redux. General-purpose
  notification belongs in the possible future notifier integration (§9.1), not
  halfway here.

### 9.4 Which groups an alert uses, and the fallback

- Each alert names one or more groups, or else uses the global **default group**. An
  explicitly **empty** list means "notify nobody" [Decided, N15, F26, R25].
- Separate groups for the on, reminder, and done notifications: **not** planned
  [Decided, R10].
- Groups chosen by template or entity: not planned for now, but nothing in the design
  should rule it out [Decided, R13].
- **Fallback group** [Decided, R6, F26, R25]: a global setting (default: one
  persistent member). It receives a notification when *every* member of *every* group
  it was sent to is missing or has failed, after the retry queue (§15.2) gives up. It
  isn't used for alerts with an explicitly empty list. A notification that reached at
  least one member counts as delivered; failed members are logged.
  [Decided, phase 4] The fallback group is chosen in the options; unset, or a group
  that no longer exists, means the built-in persistent member. If the fallback fails
  too, that's logged; it has no fallback of its own.
- [Decided, phase 4] **No default groups configured.** An alert that uses the
  default groups when none are set sends to the fallback, and a Repairs issue
  (`default_groups_unset`) says why, listing the alerts. It's raised while any alert
  relies on the unset default, and clears itself once default groups are set or no
  alert relies on them. Nothing fails silently, but the admin is told why.
- [Decided, phase 4] **Deleting a group** removes it from the default groups and the
  fallback-group setting (emptied defaults then count as unset, as above). Alerts'
  own group lists keep it: a group that doesn't exist is skipped, and an alert with
  none of its groups left notifies the fallback. Pruning an alert's list to empty
  would instead make it silently notify nobody.

### 9.5 Messages

[Decided, N17] The notification title is the alert's name, and the message body
doesn't repeat it automatically. It can include the name deliberately through the
`name` variable. There are three messages, each a template with a default:

| Message | When | Default |
|---|---|---|
| **On** | When the alert starts firing | "{{ name }} is firing." |
| **Reminder** | On the reminder schedule, while firing and unacknowledged | "{{ name }} is still firing ({{ duration }})." |
| **Done** | When the alert stops firing | "{{ name }} stopped firing after {{ duration }}." |

- Templates can read entity states and attributes [Decided, N25, R23], plus context
  variables [Decided, R23, P28]:
  - `name`, the alert entity's friendly name [Decided];
  - `subject_entity_name` and `subject_entity_id`, the friendly name and entity ID
    of the alert's **subject entity** (see below) [Decided];
  - `entity_id` and `priority`;
  - how long the alert has been firing, as `duration` (readable text) and
    `duration_seconds`;
  - the fire count;
  - the trigger or event data (event alerts), and `fire_data` (manual alerts);
    [Decided, phase 5] event alerts' is `trigger`, as in automations (a bus event
    alert reads `trigger.event.data`). It's stored with the firing in a JSON-safe
    form (states and events as dictionaries, so `trigger.to_state.state` still
    works), so it survives a restart and feeds the card and the done message.
  - the reason for the notification (`on`, `reminder`, or `done`);
  - [Decided, phase 10] for the done message, when the firing `started` and
    `ended`, as ISO 8601 text (they feed the quiet-hours summary, §9.9);
  - [Decided, phase 4] for the done message, why the firing ended, as `end_reason`
    (`resolved`, `dismissed`, or `no_data`; §11.3), and from phase 6 `disabled`.
- [Decided] The default wording is deliberately generic. It's a starting point,
  meant to be overridden with something more specific.
- [Decided, phase 4] The default done message depends on `end_reason`: an alert
  that lost its data says "{{ name }} lost its data; stopped firing after
  {{ duration }}.", so that it never reads as resolved. [Decided, phase 6] One
  that was disabled says "{{ name }} was disabled; stopped firing after
  {{ duration }}."
- [Decided, phase 4] The on and reminder messages give `duration` as at the time of
  sending (so 0 for the on message), and the done message the length of the whole
  firing. A message that fails to render is logged, and the default for that
  message is sent instead.
- **Subject entity.** Many alerts are about one obvious entity: the door, the lock,
  the thermometer. Its name is available to templates as `subject_entity_name`, so
  messages can say "{{ subject_entity_name }} is unlocked." without deriving the
  text from the alert's name. This matters most for generators: *Back Door Lock*,
  *Side Door Lock*, and *Front Door Lock* alerts can all share one message template
  [Decided].
  - [Decided] The subject entity is set automatically where it's obvious: the
    entity in a **state** alert, the value entity in a **threshold** alert (when the
    value comes from an entity), the other alert in an **alert state** alert, and
    the target of a **generated** alert.
  - [Decided] Any alert can also set its subject entity explicitly, overriding the
    automatic choice. This is how template, on/off, trigger, and bus event alerts
    get one.
  - [Decided] If there's no subject entity, `subject_entity_name` falls back to the
    alert's `name`, so generic templates still read sensibly.
  - [Decided] The subject entity is also exposed as a `subject_entity` attribute
    (N1).
  - [Decided, phase 11] A generated alert's subject is always its target, and
    its templates also get `target` (the target's entity ID) and `target_name`
    (§12.3).
- [Decided, F22] The card shows the **on** message by default. An optional separate
  **display** message can be set for the card.
  - [Decided, phase 3] With neither message configured, the card shows the default
    on message, generic as it is. The default is only a fallback, and seeing it on
    the card is a reminder to configure something specific; hiding it would need a
    special case for something that shouldn't come up.
  - [Decided, phase 3] The card's messages are rendered by the integration, with
    the on notification's context (`reason` is `on`, and `duration` is as at
    firing), so the card shows the on message as it would be sent. They're rendered
    only while the alert is firing, and re-rendered as the entities they read
    change. A message that fails to render is logged, and falls back to the
    default (the on message) or to none (the display message).

### 9.6 Reminders

- Each alert has a reminder schedule, or else uses the global default [Decided, N16].
- A schedule is a list of intervals, e.g. `[15, 30, 60]`: the gaps follow the list,
  and the last value repeats [Decided, R12]. An empty list means no reminders.
- Reminders are sent only while the alert is `active`.
- [Decided, phase 4] The global default schedule is `[10, 20, 30, 60]`: reminders at
  10, 30, and 60 minutes, then hourly.
- [Decided, phase 4] Slots are always counted from when the firing started (as in
  §6.2). Removing an acknowledgement resumes reminders at the next slot after that
  moment; slots that passed while the alert was acknowledged aren't made up.
  Changing a schedule, or the default, applies from the next slot after the change.
- [Decided, phase 4] The next reminder is kept in the store and shown as the
  `next_reminder` attribute. A reminder that fell due while HA was down is sent
  once, when it's back, and the schedule then carries on (§15.1).
- [Decided] Event alerts send reminders only if their duration is longer than the
  first reminder interval. Short event alerts just fire and expire. [Decided,
  phase 5] This compares the alert's configured (or default) duration with its
  schedule's first interval; the `reminder_schedule` attribute then shows the
  effective, empty, schedule.
- [Decided, phase 15] A **latched** alert (§10) keeps reminding, on the schedule
  counted from when it first fired, whatever its duration.

### 9.7 The done notification

- It's always sent, even if the alert was acknowledged [Decided, R10].
- [Decided, F25] It's sent **even if no on notification went out**, e.g. because of
  quiet hours or throttling. You may already know about the problem some other way,
  and hearing nothing when it's over is more confusing than a done notification with
  nothing before it.
- [Decided, F25] **Exception, supersession:** if a superseded alert and the alert
  superseding it stop firing together, within a short window, only the superseding
  alert's done notification is sent. *Door Open* and *Door Left Open* then produce a
  single "door closed" message. If they stop firing at different times, both done
  notifications are sent.
- [Decided] The window reuses the supersession debounce mechanism (§8.1), with its
  own setting, **done window**, defaulting to 5 s. The superseded alert's done
  notification waits that long to see whether the superseding alert also stops
  firing. The default is longer than the 0.5 s debounce because the two alerts may
  have different `delay_off` settings.
- [Decided, phase 7] "Together" means a superseding alert stops firing within the
  done window of the superseded one, **before or after** it. A done notification
  held when Alert Redux is unloaded is sent rather than lost.
- [Decided] **Done notifications are throttled too.** While an alert is throttled, its
  done notifications are held along with its on notifications. The throttling
  summary sent when throttling ends (§9.8) covers what happened. Throttling is
  expected to be exceptional, and usually means someone goes to the console for
  details anyway; revisit if it proves a problem.
- [Decided] **Done notifications during quiet hours** for affected alerts on loud
  groups are held and folded into the end-of-quiet-hours summary (§9.9).
- [Decided, phase 15] The done notification of a firing that **latched** (§10)
  isn't final: it keeps its buttons and stays clearable, since the alert still
  wants acknowledging.

### 9.8 Throttling

[Decided, N18, F9]

- Throttling applies to **notifications** only; state never flickers because of it.
  (Flicker at the state level is handled by `delay_off`, §4.1.)
- Format: `[count, minutes]`: at most *count* on notifications in any *minutes*
  window. Set per alert, or else from the global default (default: no throttling).
- It doesn't affect reminders.
- Throttling summaries ("[Throttling starts]" / "fired 10× in this period") are part
  of the feature [Decided, R14].
- Done notifications are held while throttled, and covered by the summary (§9.7)
  [Decided].
- [Decided, phase 10] As built, following Alert2 (P9):
  - **What counts:** every on notification the alert would otherwise send, a new
    firing or firing again while `active`, after the supersession debounce (§8.1)
    has had its say. Held ones count too. Firing again while acknowledged sends
    nothing, so it doesn't count.
  - **Starting:** the on notification that brings the count in the last
    *minutes* up to *count* is still sent, prefixed "[Throttling starts]", and
    throttling starts with it.
  - **While throttled**, on and done notifications are held. What's kept is a
    tally: how many were held, when the latest was, and when the latest firing
    ended, after how long, and why.
  - **Ending:** once fewer than *count* on notifications are left in the window.
    If anything was held, one summary is sent then, e.g. "[Throttling ends] Fired
    7× while throttled, most recently 12 minutes ago; stopped firing 3 minutes
    ago after 40 seconds." (or "…; still firing."). Its wording is fixed, not a
    template. A summary of a firing that has ended is final, like the done
    notification (§9.10, §9.11); one of a firing that goes on is like a reminder,
    with buttons.
  - Since held notifications count, a firing soon after throttling ends can
    start it again at once: the rate hasn't dropped far.
  - Turning an alert's throttling off, or raising its count above what it has
    seen, ends throttling at once. The throttle state is stored with the alert
    (§15.1), and an end that fell due while HA was down is dealt with when it's
    back.
  - Each alert uses the **default throttle** (an option; none by default), its
    own `[count, minutes]`, or none: a "use the default" checkbox, then the two
    numbers, both left empty for none.

### 9.9 Quiet hours

[Decided, R9, R25] Quiet hours hold back or soften notifications to **loud** groups for
lower-priority alerts, while a quiet-hours entity is on.

**When quiet hours apply**

- **The quiet-hours entity** [Decided, R25]: any on/off entity, e.g. a Schedule
  helper, an `input_boolean`, or a template binary sensor. While it's on, it's quiet
  hours. It's a global setting, so HA's own schedule editor and your automations
  (guests, naps, holidays) control quiet hours, not Alert Redux.
- **Per-group override** [Decided, R25]: a loud group can name its own quiet-hours
  entity instead of the global one, e.g. if bedroom and office speakers need
  different hours.
- **Priority threshold** [Decided, R9]: quiet hours apply only to alerts *below* a
  threshold priority, a global setting that defaults to Warning. So by default
  Notice and Informational alerts are affected, and Warning and above always get
  through. [Decided] A loud group can override the threshold.
- **Only loud groups** are affected. Quiet groups deliver as normal (§9.3).

**What happens during quiet hours**

Each loud group has a **quiet-hours behaviour** [Decided, R25]:

- **Hold** (default): the group's notifications for affected alerts are held until
  quiet hours end.
- **Soften**: notifications are sent anyway, using each member's quiet-hours `data`
  instead of its normal `data`, e.g. iOS `interruption-level: passive` or a
  low-priority Android channel. [Decided] Members that have no quiet-hours `data`,
  or can't take `data` at all (entities, persistent), hold instead. Softened
  notifications count as delivered and aren't repeated later.

**When quiet hours end** [Decided, R9]

For each loud group, when its quiet-hours entity turns off:

- [Decided] **Alerts still firing and unacknowledged** get **one reminder**, which
  shows the real firing duration. There's no late on notification, for the same
  reason as §8.3: a late on notification would make it look as if the alert had
  only just started. Held reminders aren't replayed. Alerts acknowledged during the
  night get nothing more.
- [Decided] **Alerts that stopped firing during quiet hours**, whether they started
  before quiet hours or during them, are listed in **one summary notification** per
  group. For each alert it gives the name, when it **started**, when it **stopped**,
  how long it fired, and how many times. Their held done notifications are folded
  into this summary rather than sent separately (§9.7). For an alert whose on
  notification went out before quiet hours began, the summary is where you learn
  when it ended.
- [Decided] The summary stays an ordinary notification. (The acknowledgement queue
  it might once have used was replaced by latching alerts, §10.)

**As built** [Decided, phase 10]

- The global entity and threshold are in a collapsed **Quiet hours** section of
  the options; the entity can be an `input_boolean`, `schedule`,
  `binary_sensor`, or `switch`. With no entity, quiet hours apply only to groups
  with their own.
- An entity that's **unavailable or unknown** can't say it's quiet hours, so new
  notifications go out (fail loud), but what's held stays held until the entity
  is off. An entity that **doesn't exist** once integrations have had the retry
  timeout to set up is a Repairs issue (`quiet_entity_missing`), which clears
  when it appears or is no longer used; meanwhile quiet hours don't apply.
- [Decided, 0.10.1] **While HA is starting**, a quiet-hours entity may not
  have its state yet. Until HA has started, a loud group whose quiet hours
  can't be told holds, so a restart in the night doesn't wake anyone; what's
  held is released once HA has started if they turn out not to be on.
- Holding is per member: in a softening group, members with quiet-hours `data`
  get softened notifications, and the rest hold. What's sent when quiet hours
  end goes to the members that held. A held notification never goes to the
  fallback.
- **When quiet hours end**, Alert Redux decides per alert, from what was held
  for it:
  - an alert that's `active` (and not superseded) gets one reminder, with its
    real duration;
  - its firings that ended while held are one line of the summary: "Back Door
    Open: first started 01:12, last stopped 02:24, fired 2 times for 12
    minutes in all." (or "started …, stopped …, fired for …" for one firing),
    with the day as well for a time that isn't today;
  - a throttling summary (§9.8) held for a firing that ended is a line of its
    own; throttling holds the done notification itself, so the throttling
    summary is what reports it.
  The summary is one notification per group, titled "Quiet hours summary",
  headed "While quiet hours were on:", with its own key
  (`alert_redux_quiet_hours_<group>`), so each night's replaces the last. Its
  wording is fixed. An alert whose firing ended while held, and that gets no
  reminder, has its earlier notification cleared from the members that held, as
  its done notification would have done.
- Held notifications are kept in the notifier's store. Quiet hours that ended
  while HA was down end once it has started. Deleting an alert drops what was
  held for it; renaming it moves that to its new key. Deleting a group drops
  what it held.

### 9.10 Replacing and clearing notifications

[Decided, P1–P2, R25] Where a notifier kind can do it,
each alert's notifications replace one another instead of piling up, and can be
cleared when they're no longer needed.

- [Decided] Each alert has a **lifecycle key**, `alert_redux_<alert object ID>`. It's
  used as the mobile `tag` (legacy mobile members) and as the `notification_id`
  (persistent members). Each new notification for the alert (on, reminder, done)
  replaces the previous one on that device.
- [Decided] Per member, **clear when acknowledged**: when the alert is acknowledged
  (on the card, by voice, by button), its notification is removed, using
  `clear_notification` on mobile and `dismiss` for persistent. Default: on.
- [Decided] Per member, **when the alert stops firing**: *replace* the notification
  with the done message (default), or *clear* it.
- Entity members can't replace or clear. Each notification arrives as a separate
  message.
- [Decided, phase 9] **Acknowledging** includes snoozing (§6.2) and
  pre-acknowledgement (§8.3): each clears. **Deleting** an alert clears its
  notifications, including an alert deleted while HA was down.
- [Decided, phase 9] The notifier keeps **live records**: which members are
  showing each key's notification, and with what tag. Clears go to exactly
  those, so they still reach a phone after it's been removed from the group, or
  a notification that went to the fallback. A delivered done notification ends
  its key's records: it stays on show, but there's nothing more to clear. The
  records are kept in the notifier's store, so they survive a restart.
- [Decided, phase 9] **Renaming** an alert changes its key. Its records keep the
  tag they were shown with: clearing the new key clears them, and the next
  notification to such a member clears the old one first.
- [Decided, phase 9] **Retries honour replacing.** A newer notification or a
  clear for a member drops any earlier one for the same tag that's still
  waiting for a retry, so a retried on notification can't arrive after the
  acknowledgement. A dropped attempt counts as delivered, so it never goes to
  the fallback; clears never go to the fallback either.
- [Decided, phase 9] Alert Redux's `tag` (and `actions`, §9.11) win over the same
  keys in a member's own `data`.

### 9.11 Buttons

[Decided, N37, P3] Alerts can put buttons on notifications, and members that support
buttons show them. Currently that means legacy mobile members; Telegram inline
keyboards could be added later. Other members leave the buttons out.

- **Custom buttons** [Decided, N37]: each alert can define buttons, each with a
  label and the HA action it runs. For example, *Garage Door Left Open* has "Close
  door", which runs `cover.close_cover` on `cover.garage_door`. The definition says
  nothing about mobile; the member converts it into its own format.
- **Built-in buttons** [Decided, P3]: **Acknowledge**, and **Snooze Alert** for a fixed
  duration (per alert, or else a global default). They aren't shown on
  unacknowledgeable alerts (§6.1).
- **Require unlock** [Decided]: a per-button setting. It maps to iOS
  `authenticationRequired`, so security-sensitive buttons (e.g. "Unlock door") only
  work from an unlocked phone.
- **How a tap is handled** [Decided]: the member sends each button with an action ID
  of the form `ALERT_REDUX_<alert>_<button>`. Tapping it makes `mobile_app` fire a
  `mobile_app_notification_action` event. Alert Redux matches the ID and runs **only
  the action configured for that button**; nothing in the event itself is executed.
  The user who tapped it is recorded for the activity log (R18).
- [Decided] **Too many buttons**: some platforms limit the number of buttons (Android
  shows at most three). They're ordered custom buttons first, then Acknowledge, then
  Snooze, and the extras are dropped from the end.
- [Decided] **Which notifications carry buttons**: on and reminder notifications do;
  done notifications don't.
- [Decided] **Tapping after the alert has ended**: custom buttons still run their
  action. Acknowledge and Snooze do nothing.
- [Deferred] Raw extra `data` supplied per alert, for anything buttons can't express,
  could be added later if a need appears.
- [Decided, phase 9] **Action IDs** are `ALERT_REDUX_<alert's unique ID>_<button>`:
  the unique ID survives renames. `<button>` is `ACK`, `SNOOZE`, or, for a
  custom button, `B` and a hash of its label and action. An edited or removed
  button's old taps then match nothing, and are ignored, rather than running
  another button's action.
- [Decided, phase 9] A custom button's action is an HA action sequence, chosen
  with the action selector and validated when the alert is saved. It runs as the
  user who tapped (the mobile app fires the event with its user's context).
- [Decided, phase 9] Every mobile member gets at most **three** buttons, since
  the platform isn't known for a notify group of phones.
- [Decided, phase 9] The Snooze button's duration is the alert's own setting, or
  the **Snooze button duration** option, 1 hour by default. Its title gives the
  duration ("Snooze Alert 1 hour").
- [Decided, 0.11.1] **The app's own snooze options.** By default the HA app
  offers its own *Snooze 5 min*, *Snooze 15 min*, and *Snooze 1 hour* on
  notifications. These aren't Alert Redux's snooze (§6.2): they only snooze the
  notification on the phone, which was confusing next to our button. They're
  left alone, since people may want them, and ours is called **Snooze Alert**
  instead, so the two are told apart.
- [Decided; phase 13] Custom buttons also show **on the main card** (§13.1).

## 10. Latching alerts

[Decided; phase 15] Some alerts matter even if they stop before anyone
sees them: the freezer that was warm for twelve minutes at 3 a.m., or a leak sensor
that tripped three times overnight and is dry now. Reminders end when a firing
ends, so today nothing says "you haven't seen this". A **latching** alert keeps
asking until someone acknowledges it, however its firing ended.

This replaces the separate "needs acknowledgement" queue first proposed in R7
(spec notes). Walking through real uses showed a queue would be a subsystem of its
own (items with identity, storage, a card, notifications, sensors) for what a
setting on the alert does with the model that already exists. Nothing is lost for
the other stories: done notifications, the Activity card, and the quiet-hours
summary (§9.9, which stays an ordinary notification) already cover them.

- **A per-alert setting**, off by default and meant for alerts that matter (a
  critical alert, a transient fault): *keep until acknowledged*. Alerts without it
  behave as they do now.
- **What it does**: when a latching alert's firing ends *without having been
  acknowledged*, the alert doesn't return to `idle`. It stays visible on the main
  card as needing acknowledgement, and acknowledging it (the card's button, the
  action, voice, a notification button) clears it. A firing that was acknowledged
  before it ended ends as now.
- **One item per alert, not one per firing.** The queue would have made a separate
  item of each unacknowledged firing. A latching alert that fires again before
  it's acknowledged is the same item, and the card shows how many times it has
  fired (`fire_count`) whenever that is more than one and the card isn't already
  showing it.
- [Decided; phase 15] **Design.** As built in phase 15 (with the user's choices
  marked):
  - **A state of its own, `latched`** [with the user], not `idle` with an
    attribute: automations, history, the logbook, and the alert state kind see
    it directly. It ranks below firing and above `no_data`: a latched condition
    alert that loses its data stays `latched`, with `no_data_since`, and counts
    as no data, as a firing alert does in its grace period (§4.4).
  - **What latches.** A firing that ends while `active`, for any reason but
    being disabled: resolved, a duration running out, the no-data grace running
    out, and a dismissal. **A dismissal latches only when no user is behind it**
    [with the user]: a person dismissing the alert (the card's button, or a
    script they ran) has seen it; an automation hasn't. An end while `ack`
    (snoozed and pre-acknowledged included) goes to `idle` as before.
  - **One item.** A latched alert that fires again becomes `active`, sends its
    on notification as a new firing does, and keeps counting `fire_count`;
    `fire_data` and the messages are kept while latched. Acknowledging it
    during that firing closes the item, so it ends as `idle`.
  - **Acknowledging** releases it to `idle`, by every route (the action, the
    card, voice, notification buttons, the proxy switch), clears its
    notifications (§9.10), and fires `_acked` with `old_state` `latched`.
    `unack` does nothing: it isn't acknowledged.
  - **Snoozing** a latched alert puts its reminders off [with the user]: it
    stays `latched` with `snoozed_until`, `_snoozed` fires without `_acked`, and
    when the snooze runs out, `_snooze_expired` without `_unacked`, and the
    snooze-end reminder rule (§6.2) applies.
  - **Reminders** carry on while latched (not while snoozed), on the schedule
    counted from when the item first fired; the runtime keeps that start
    (`latch_anchor`), since `firing_since` clears at the end. A latching event
    or self-ending manual alert reminds whatever its duration (§9.6). A
    reminder's `duration` is then how long ago the alert stopped, and `latched`
    is true; the default text is "{{ name }} stopped firing {{ duration }} ago
    and hasn't been acknowledged" (with the fire count when it's more than
    one). The alert's own reminder message is used if it has one.
  - **The done notification** is sent as always (§9.7). For a firing that
    latched it isn't final: it keeps the Acknowledge and Snooze buttons and
    stays clearable, `latched` is true, and the default adds "It's kept until
    acknowledged."
  - **Summary sensors** [with the user]: a latched alert counts as
    unacknowledged, in `active` and `highest_unacked_priority` (a signal light
    stays on until it's acknowledged), but not as firing. A new
    `sensor.alert_redux_latched` lists them. A superseded latched alert is left
    out of `active` and counted in `superseded`, as a firing one is (§11.2).
  - **Supersession.** A latched alert isn't firing, so it supersedes nothing;
    one that a firing alert supersedes is hidden, silent, and skips its
    reminders, as a firing one does. Propagation (§8.2) acts at once on a
    superseding alert that is `latched`, as on one that is `active`:
    *Acknowledge* releases it, *Snooze* snoozes it. Acknowledging a latched
    alert pre-acknowledges nothing (it isn't firing), but it propagates the
    same way to directly superseding alerts that are latched too, so *Door
    Open* and *Door Left Open* that both latched overnight are cleared
    together.
  - **Disabling** clears the latch (and fires no `_ended`: nothing was
    firing); enabling starts from scratch (§6.3). **Turning the setting off**
    releases a latched alert to `idle` without recording an acknowledgement.
  - **Restarts** keep the latch and its anchor; a reminder that fell due while
    Home Assistant was down is sent once (§15.1).
  - **Validation.** Latching needs the alert to be acknowledgeable, or nothing
    could clear it: the forms and import refuse it
    (`latching_unacknowledgeable`).
  - **Events.** None new: `_ended` with `new_state` `latched`, and `_acked`
    with `old_state` `latched`, tell the story. The alert state kind can watch
    for `latched`, which gives escalation of an alert left unacknowledged.
  - **Quiet hours.** When they end, a latched alert gets the one reminder, as
    an `active` one does (§9.9).
  - **Voice and proxies** (§14). Acknowledge and snooze accept latched alerts;
    "which alerts are firing" lists them after the firing ones ("… stopped
    firing but hasn't been acknowledged"). The proxy switch is on while the
    alert is `active` or `latched`; turning it off acknowledges, and turning it
    on while latched is refused (`not_firing`). The snooze button snoozes it.
  - **Configuration.** The setting is `latching` ("Keep until acknowledged"),
    beside `acknowledgeable` in every kind's form and generators', stored only
    when on (so no schema version change), and exported and imported as an
    ordinary field (§16). The attribute `latching` shows it.
  - **The card** lists latched alerts with the firing ones: within a priority,
    after `active` and before `ack`, with a dashed border, when it stopped, the
    fire count, Acknowledge, and Snooze, but no dismiss (§13.1).

## 11. Integration surface: attributes, sensors, events

### 11.1 Alert entity attributes

[Decided, N1] Every alert entity has, at minimum:

- **State details:** `kind`, `priority`, `firing_since`, `last_fired`, `last_ended`,
  `fire_count` (current firing), `event_expires` (event alerts), `snoozed_until`,
  `disabled_until`, `pre_acked_by`, `superseded_by`, `no_data_since`, the input
  entities that are missing data (`missing_inputs`), and the time and user of the
  last acknowledge, snooze, disable, or enable [Decided, R18]. [Decided, phase 2]
  Also the pending deadlines: `delay_on_until`, `delay_off_until`, and
  `no_data_grace_until`.
- **Configuration:** `acknowledgeable`, `supersedes`, `notifier_groups`, `buttons`,
  `reminder_schedule`, `throttle`, `delay_on`/`delay_off`, `duration`, the source
  entity or entities, and the on message (rendered). [Decided, phase 2] Durations
  are given in seconds. The state kind shows `source_entity` and `target_state`,
  and the template kind shows `template`. Condition alerts also show `condition`
  and the effective `no_data_grace`. Templates are kept out of the recorder.
  [Decided, phase 3] The rendered messages are `message` (the on message) and
  `display_message` (null unless one is configured). Both are null while the alert
  isn't firing, and both are kept out of the recorder.
  [Decided, phase 4] `notifier_groups` gives the names of the groups the alert
  actually sends to (the defaults, or the fallback, if it has none of its own), and
  `reminder_schedule` the effective schedule in minutes. `next_reminder` is when
  the next reminder is due, or null.
  [Decided, phase 5] Event alerts show `duration` (seconds), `event_expires`,
  `condition`, the latest trigger's variables as `trigger_data`, and their triggers
  (`triggers`, or `event_type` and `event_data`). Threshold alerts show
  `source_entity`, `attribute`, `value_template`, `minimum`, `maximum`,
  `hysteresis`, and the current `value`; on/off alerts show `on_template`,
  `on_triggers`, `off_template`, and `off_triggers`. Templates, trigger
  configuration, trigger data, and `value` are kept out of the recorder.
  [Decided, phase 6] The snooze and disable details are `snoozed_until`,
  `last_snoozed`, `last_snoozed_by`, `disabled_until`, `last_disabled`,
  `last_disabled_by`, `last_enabled`, and `last_enabled_by`. A snooze running
  out, or a suspension ending, records no user.
  [Decided, phase 7] `supersedes` and `superseded_by` are lists of entity IDs
  (§8.1). Alert state alerts show `source_entity` (the watched alert) and
  `target_states`.
  [Decided, phase 7] Also `pre_acked_by` and `pre_snoozed_until` (§8.3), and
  `broken_references` (§12.4), a list of entity IDs.
  [Decided, phase 9] `buttons` lists the labels of the alert's custom buttons.
  [Decided, phase 13] `buttons_require_unlock` lists the labels of those marked
  **Require unlock**, which the main card asks to confirm (§13.1).
  [Decided, phase 10] `throttle` is the effective throttle, `[count, minutes]`,
  or null; `throttled_since` is when throttling started, or null (§9.8).
  [Decided, phase 15] `latching` (§10). A latched alert keeps `fire_count`,
  `fire_data`, and its rendered messages until it's acknowledged.
- **Generator provenance:** `generated_by` (§12.3). [Decided, phase 11] The
  generator's sensor's entity ID, or null for a fixed alert.

Attributes that can grow large, or change constantly, should be kept out of the
recorder with `_unrecorded_attributes`.

### 11.2 Summary sensors

[Decided, R5]

- `sensor.alert_redux_highest_priority`: the highest priority among firing
  alerts, or `none`. (This is the one to use for a signal light.)
- `sensor.alert_redux_highest_unacked_priority`: the same, counting only `active`
  alerts.
- Count sensors: **firing**, **active** (unacknowledged), **acknowledged**, and
  **no data**.
- **Disabled** count: a **diagnostic** sensor (`entity_category: diagnostic`)
  [Decided]. It counts suspended alerts too.
- Per-priority counts are **attributes** on the firing and active sensors, not
  separate sensors, so the number of entities doesn't multiply [Decided,
  preliminary]. For example, `sensor.alert_redux_active` has `emergency: 0`,
  `critical: 1`, `warning: 2`, and so on.
- Each count sensor lists the entity IDs it counts, as an attribute, so automations
  don't need to scan all alerts.
- [Decided, phase 8] As built: the two priority sensors are enum sensors whose
  state is a priority or `none`. The count sensors are `sensor.alert_redux_firing`,
  `…_active`, `…_acknowledged`, `…_no_data`, and `…_disabled`, each with an
  `entity_ids` attribute (kept out of the recorder); the firing and active sensors
  also carry a count per priority. The count sensors have a state class
  (`measurement`), which gives them statistics and keeps them out of the logbook.
  The sensors have no device, and don't get the alerts label (§11.5).
- [Decided; phase 13] **Superseded alerts aren't unacknowledged.** A firing alert
  that a firing alert supersedes (§8.1) is hidden on the card and silent, so it
  is left out of the unacknowledged figures: `highest_unacked_priority`, and the
  `active` count, its `entity_ids`, and its per-priority counts. Acknowledging
  the visible alert therefore quiets the signal. The factual figures still count
  it: `firing`, `highest_priority`, and `acknowledged` (when it is). So `active`
  plus `acknowledged` is no longer `firing`; the difference is the **superseded
  alerts that are `active`**.
- [Decided; phase 13] `sensor.alert_redux_superseded` counts the firing alerts
  that are currently superseded, `active` or `ack`, and lists them in
  `entity_ids`, so what is left out of `active` can be seen. An alert that
  isn't firing isn't counted, whatever its `superseded_by` says. When the
  superseding alert stops firing, its alerts count as unacknowledged again, as
  they would on their own (§12.4).
- [Decided; phase 15] **Latched alerts are unacknowledged** (§10): they count in
  `active` and `highest_unacked_priority` (not in `firing` or
  `highest_priority`), unless superseded, when they count in `superseded`
  instead. `sensor.alert_redux_latched` counts and lists them.
- [Decided, phase 8] The **no data** count counts every alert missing data,
  whatever its state: `no_data` alerts, and firing alerts in their grace period
  (§4.4), which count as firing too. Something's input being broken shows at
  once (fail loud).
- [Decided, phase 8] The sensors update once per burst of changes (a
  supersession cascade, say), not once per alert.

### 11.3 Events

[Decided, N2, R17] Every change fires its own HA event, with the common prefix
`alert_redux_`: `alert_redux_fired`, `…_ended`, `…_acked`, `…_unacked`,
`…_snoozed`, `…_snooze_expired`, `…_disabled`, `…_enabled`, `…_no_data`,
`…_superseded`, `…_created`, `…_deleted`, and [Decided, phase 8]
`…_data_restored`. Every event carries `entity_id`, `name`,
`priority`, `kind`, the old and new states, and, for user actions, `user_id`
[Decided, R18].

**Separate events, not one combined event** [Decided]. HA's event bus has no prefix
wildcards (`alert_redux_*` won't match). To listen for several, an event trigger takes
a **list** of event types. The spec will include a ready-made list, ready to paste.

**Events fire together when one change implies another** [Decided], so each event
tells the whole story and nothing has to be inferred:

| Change | Events fired |
|---|---|
| Snooze an `active` alert | `_snoozed`, `_acked` |
| Snooze an alert that's already `ack` (re-snooze or extend) | `_snoozed` only |
| Snooze runs out while still firing | `_snooze_expired`, `_unacked` |
| Unack a snoozed alert | `_unacked` (the snooze is cleared as part of this) |
| Suspend | `_disabled` (with `disabled_until` in the data) |
| Suspension ends | `_enabled` |

- [Decided] When an alert stops firing, only `_ended` is fired. The automatic
  clearing of its acknowledgement and snooze (§6.1, §6.2) is part of ending, not a
  separate change, so no `_unacked` accompanies it. Otherwise, anything listening
  for `_unacked` as "someone un-acknowledged this" would see false positives.
- [Decided] A firing that starts pre-acknowledged (§8.3) fires `_fired` and
  `_acked`, and the `_acked` data carries `pre_acked_by`. [Decided, phase 7] So
  does propagation acknowledging an already active alert (§8.2), which carries
  the acknowledging user too; snoozing it fires `_snoozed` as well.
- [Decided, phase 2] `_ended` carries a **`reason`**: `resolved` (the condition
  ended, or an event alert's duration ran out), `dismissed` (a manual alert), or
  `no_data` (the grace period ran out; §4.4). Phase 6 adds `disabled` (F15). The
  done notification (§9.7) uses it.
- [Decided, phase 6] `_snoozed` carries `snoozed_until`, and `_disabled` carries
  `disabled_until` (null when disabled indefinitely). Disabling a firing alert
  fires `_ended` (reason `disabled`) and then `_disabled`.
- [Decided, phase 7] `_superseded` fires on a **firing** alert when an alert
  superseding it starts firing, so that its `superseded_by` goes from empty to
  non-empty. It carries `superseded_by`, and its old and new states are the same.
  An alert that starts firing while already superseded gets no `_superseded`
  (its `superseded_by` didn't change), and nor does restoring after a restart.
- [Decided, phase 2] `_no_data` fires when an alert loses its data, and carries
  `missing_inputs`. This happens both when the alert enters `no_data` and when a
  firing alert loses data but keeps its state during the grace period. If the
  grace period then runs out, only `_ended` fires. Data returning has no event of
  its own (`state_changed` shows it); the phase 8 review of the event set can
  revisit that. Waiting for data at startup fires no events.
- [Decided, phase 8] `_data_restored` fires when data returns after a loss that
  `_no_data` announced, and carries the `missing_inputs` that were missing. It's
  the only sign of data returning to a firing alert within its grace period,
  where the state doesn't change. It fires before any `_fired` or `_ended` the
  same result causes. Data arriving after waiting at startup fires nothing, as
  the wait itself fired nothing; a loss announced before a restart is announced
  as restored after it.

[Decided, phase 8] **The event set, reviewed.** Each event's data, beyond the
common data above:

| Event | Also carries |
|---|---|
| `_fired` | `fire_count`; `fire_data` (manual alerts) or `trigger_data` (event alerts) |
| `_ended` | `fire_count`, `duration_seconds`, `reason` |
| `_acked` | `pre_acked_by`, when acknowledged by supersession (§8.2, §8.3) |
| `_unacked` | — |
| `_snoozed` | `snoozed_until` |
| `_snooze_expired` | — |
| `_disabled` | `disabled_until` (null when disabled indefinitely) |
| `_enabled` | — |
| `_no_data` | `missing_inputs` |
| `_data_restored` | `missing_inputs` (the inputs that were missing) |
| `_superseded` | `superseded_by` |
| `_created` | — (`old_state` is null) |
| `_deleted` | — (`new_state` is null; the rest comes from the stored record) |

[Decided, phase 15] Latching (§10) adds no event. A firing that latches fires
`_ended` with `new_state` `latched`; acknowledging a latched alert fires `_acked`
with `old_state` `latched`; snoozing one fires `_snoozed` alone, and its snooze
running out `_snooze_expired` alone.

The review kept `_superseded` without a counterpart: an alert ceasing to be
superseded shows in `superseded_by`, and the change that caused it (the
superseding alert ending) has its own event.

**Ready to paste**, to listen for every event:

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

### 11.4 Logbook / Activity

[Decided, N24, R18, F18]

- Entity states are translated (`ack` → "Acknowledged", `no_data` → "No data", …)
  through `translation_key`.
- A logbook platform describes Alert Redux events in readable text, including who did
  what, e.g. "Back Door Open acknowledged by Alistair". This is what lets a standard
  Activity card stand in for Alert2's history view.
- [Decided, phase 8] **Only events that add to the state rows are described.**
  The logbook already has a row for every change of an alert's state, showing the
  translated state and, from the change's context, the user who made it ("Back
  Door Open · Acknowledged · Alistair"). Describing `_fired`, `_acked`,
  `_unacked`, `_enabled`, or `_ended` too would show each of those changes twice,
  and a describer can't drop a row once its event type is registered. So only
  these get rows, each with the user from its context:

  | Event | Row |
  |---|---|
  | `_snoozed` | "Snoozed until 14:30" (the date too, unless it's today) |
  | `_snooze_expired` | "Snooze ran out" |
  | `_disabled` | "Suspended until Tue 06 Oct 18:00", or "Disabled" (which repeats the state row; it's rare) |
  | `_superseded` | "Superseded by Door Left Open" |
  | `_no_data` | "Lost data from sensor.x" (it also covers a firing alert, whose state doesn't change) |
  | `_data_restored` | "Data restored" |
  | `_created`, `_deleted` | "Created", "Deleted" |

  An end's reason is still clear without `_ended`: an end for lack of data
  follows its `_no_data` row, and a dismissal's state row carries the user.
  [Decided, 1.0.0] HA's logbook leaves out an entity's first state after a
  restart, so a change made while restoring would have no row. A duration that
  ran out while HA was down therefore ends just after the first state is written
  (§15.1). The
  messages are English, like the cards (§13.1).
- [Decided, 0.11.1] The messages are **capitalised**, like the translated
  states on the state rows beside them ("Acknowledged", "Idle"), so the
  Activity list reads consistently.
- **Known limitation: grey dots.** The Activity card colours each entry's dot from
  theme variables (`--state-<domain>-<state>-color`), but the HA frontend only
  looks these up for a hard-coded list of built-in domains (`STATE_COLORED_DOMAIN`
  in its `state_color.ts`). `alert_redux` isn't on the list, so our entries always
  get a grey dot, and themes can't change that. The only proper fix is upstream: a
  frontend change to look up those variables for any domain whose theme defines
  them. With that in place, Alert Redux would ship default state colours.
  [Deferred] An upstream request is left until after the phase plan is complete.
- **Known limitation: deleted alerts in filtered views.** A deleted alert's rows,
  "Deleted" included, are recorded, but only the unfiltered Activity view shows
  them all. Filtered by the alert's entity, HA keeps an integration's described
  rows only for entities whose config entry, found through the entity registry,
  is that integration's; a deleted alert has no registry entry, so only its
  state rows remain. Filtered by label, area, or device, HA finds the entities
  through the registry too, so a deleted alert has no rows at all. Nothing on
  our side changes this.

### 11.5 The alerts label

[Decided] Every alert carries one label, **"Alert Redux"**. Cards that take targets,
such as the Activity card, can then show every alert, including alerts added later,
by selecting that one label. Entities can carry several labels, so this doesn't use
up labels you want for other things, and areas stay free.

- The label is created the first time the integration sets up (or, if a label with
  that name already exists, that one is used). Its ID is kept in the store.
- Each alert is given the label **once**: a new alert when it's first added, and an
  alert that existed before the label the first time it's added afterwards. The
  alert's stored record remembers that it's been done. That includes generated
  alerts (§12.3).
- It's never forced back. If you remove it from an alert, it stays removed. If you
  delete the label, it isn't recreated.
- Only alert entities get it. Summary sensors (§11.2), generator entities (§12.3), and
  voice proxies (§14.2) don't. The summary sensors in particular change
  constantly and would flood an Activity card.
- [Decided, phase 12 design] By the same rule, each alert is **exposed to
  Assist** once, and never forced back (§14.1). Its stored record remembers
  that as well.
- Built as release 0.3.1, between phases 3 and 4.

**Why not a device.** A single virtual "alerts" device was tried first and rejected.
Since HA 2026.4 (core PRs #166246 and #166696), an entity that belongs to a device
always has the device's name put in front of its name, and newly created entities
get it in their entity IDs too. There's no supported way to opt out. Every alert
would have become "Alert Redux alerts Back Door Open", with an entity ID to match.
One device per alert would keep the names, but brings back the problem the device
was meant to solve.

### 11.6 Area and labels

[Decided; phase 13] An alert's area and labels can be set in its configuration
form (§12.1), as well as on the entity's settings page as now. They're meant for
card filters (§13.1) and anything else that selects entities by area or label.

- **The entity registry is where they live.** The form is an editor for the
  registry's values, not a second copy: editing an alert pre-fills them from the
  registry, and saving writes them back. Changes made on the entity's settings
  page stay, and the form shows them the next time it's opened.
- **A new alert** has no entity while its form is open, so the values travel in
  the subentry and are applied once, when the entity is first added, as the alerts
  label is (§11.5). They're kept apart from the alert's configuration proper: a
  change to them isn't a configuration change, and doesn't restart a condition
  alert's pending delays.
- **The alerts label** keeps its own rule (§11.5): given once, never forced back.
  The form shows it like any other label, and removing it there removes it.
- **Generators** (§12.3) [Decided, provisionally]: a generator's form sets labels
  for all its alerts, and an area that's either a fixed area or **the same as the
  target**: the target entity's area, or else its device's. The target's area is
  the default. Each door's *Left Open* alert then lands in that door's area,
  though the doors are all in different areas.
- **Voice proxies** (§14.2) copy their alert's area and labels, and follow
  changes to them however they're made, except for the alerts label, which
  proxies don't get (§11.5).
- [Decided, as built] **The form.** A collapsed **Area and labels** section
  (`placement`) on every alert and generator form: an area and labels. Editing a
  fixed alert pre-fills it from the registry and writes it back on saving (a label
  left out is removed, the alerts label too); the subentry keeps nothing, so
  there's nothing stale. A new alert's values are stored in the subentry as
  `placement`, kept apart from the alert's configuration (`AlertDefinition.placement`,
  not `data`), and applied once, when the entity is first added; a `placed` flag in
  the stored record stops them being applied again.
- [Decided, as built] **Generators.** The section also has *Use the target's area*
  (on for a new generator; a generator made before this has none of it, so its
  alerts' areas are left alone). The stored `placement` is
  `{area_from_target | area_id, labels}`. Each generated alert is given the
  target's area (the entity's, else its device's) or the fixed area, and the labels,
  when it's added. A change then **follows**: saving the generator, or the target
  moving to another area, adds the labels the generator now names, removes those it
  no longer names, and sets the new area, leaving everything else on the alert alone
  (labels added by hand, the alerts label). The placement an alert was built with is
  kept in its stored record, so setting up again after a restart changes nothing.
- [Decided, as built] **Export and import** (§16). An alert's placement was applied
  once and now lives in the registry, so it isn't exported, and doesn't stop an
  import finding the alert unchanged. A generator's placement is part of its
  definition and is exported; its area and label IDs are the registry's and aren't
  checked, as for its targets.

## 12. Configuration

### 12.1 Structure

[Decided, R21, F27]

- One integration config entry (already in place) holds the **global defaults**:
  the default and fallback notifier groups, reminder schedule, throttle, snooze
  duration for notification buttons, the per-priority event durations (phase 5)
  and icons, the
  quiet-hours entity and priority threshold, and the no-data grace period. They're
  edited through its options flow. [Decided, phase 6] Also the snooze-end window
  (§6.2). [Decided, phase 7] Also the supersession debounce and the done window
  (§8.1, §9.7), in seconds, in a collapsed **Supersession** section.
  [Decided, phase 9] The snooze duration for notification buttons is the
  **Snooze button duration** (§9.11).
  [Decided, phase 10] The default throttle is two numbers, a count and minutes,
  both empty for none (§9.8). The quiet-hours entity and threshold are a
  collapsed **Quiet hours** section (§9.9).
  [Decided, phase 11] Also the **generator startup grace** (§12.3).
- Each **alert** is a **config subentry** of that entry, created and edited in the
  UI (and, later, from the admin card, §13.2).
- Each **generator** is also a subentry (§12.3).
- Each **notifier group** is also a subentry (§9.3).
- [Decided, phase 13] The layout and grouping of the alert and generator forms were
  reviewed, and found sound. The one change: the collapsed **Area and labels**
  section (§11.6) sits right after the name, priority, and icon, where you think
  about where an alert is. The other three collapsed sections follow the kind's
  fields, in alphabetical order: **Notifications and messages**, **Supersession**,
  **Voice assistants**.
- The forms use HA's own selectors: entity, template, trigger, duration, and so on.
  The form fields shown depend on the kind of alert.

### 12.2 Naming

[Decided, F11] Each alert has one **name** (shown on the card, and used as the
notification title). Its entity ID is derived from the name when the alert is created
(`alert_redux.<slug>`) and doesn't change after that. It can be renamed through the
entity registry as usual. In the UI, "name and friendly name" become this single
name.

### 12.3 Generators

[Decided, N32, F20] A generator is a template for alerts, plus a way of
choosing the target entities. It creates one alert per target. Generated alerts are
marked **read-only**: they're edited through their generator, and the admin card
doesn't allow editing them individually.

[Decided, F20]

- Targets are chosen by any combination of: label, area, domain, device class, and a
  pattern on the entity ID. Labels are the natural fit, because they're what the UI
  is built around.
- Generators are **dynamic**: when an entity starts matching, an alert is created for
  it, and when it stops matching, its alert is removed.
- A generated alert's entity ID is derived from the generator and the target entity,
  so it stays stable as long as the target's entity ID does.
- Templates in the generator can use the target entity (`target`) and anything else
  about it: name, area, and so on.
- **Generated supersession** [Decided]: a generator can declare that each of its
  alerts supersedes the alert that *another generator* made for the **same
  target**. E.g. the *Left Open* generator supersedes the *Open* generator, so each
  door's *Left Open* alert supersedes that door's *Open* alert. It can also
  supersede, or be superseded by, a fixed alert. The propagation setting (§8.2) is
  part of the declaration.
- **Generators are entities** [Decided], e.g.
  `sensor.alert_redux_generator_<name>`. State: the number of alerts generated.
  Attributes: the matching targets, the generated alert IDs, the generator's
  supersession links, and any problems (e.g. a target whose alert couldn't be
  created).
- **Refresh action** [Decided]: `alert_redux.refresh_generator` re-evaluates a
  generator's targets immediately. It's for debugging; generators normally refresh
  themselves when entities or labels change.
- [Decided, phase 11] As built:
  - **Kinds.** Generators make condition alerts: state, threshold, template,
    on/off, and alert state. Manual alerts make no sense per target, and HA's
    triggers can't be templated with the target. The form is the kind's alert
    form, with a name template and a **Targets** section instead of the kind's
    entity and the subject entity.
  - **The target** is filled in as the kind's entity (the state alert's entity,
    the threshold alert's value entity unless a value template gives the value,
    or the alert state alert's watched alert) and as the subject entity (§9.5).
    Every template, the messages included, gets `target` (its entity ID) and
    `target_name`. On/off triggers are the same for every target.
  - **Matching.** Criteria combine **AND across, OR within**: an entity must
    match every criterion that's set, and any one value within each. Labels and
    areas count through the entity's device too. The entity ID pattern is a glob
    (`lock.*_door`). A list of excluded entities is never targeted. At least one
    criterion is needed, so a generator can't match everything.
  - **Which entities can be targets.** Every enabled entity except configuration
    entities (diagnostic ones, such as battery levels, are obvious targets), and
    entities with no registry entry, which can only match by domain, device class
    (from their state), or pattern. Generated alerts are **never** targets, so
    alert state generators can't feed on themselves or each other; nor are Alert
    Redux's sensors. Fixed alerts are.
  - **Identity.** A generated alert's unique ID is the generator's subentry ID
    and the target's entity registry ID (its entity ID if it has no entry). A
    renamed target keeps its alert, state and all; the alert follows the new
    entity ID, and keeps its own. The alert's entity ID is the target's object ID
    followed by the generator's name (`alert_redux.front_door_unlocked`), fixed
    once created.
  - **Naming.** The name template defaults to the target's name followed by the
    generator's ("Front Door Unlocked"). It's re-rendered as the target's name
    changes. One that fails to render gives the default, and a problem on the
    generator's sensor.
  - **Following changes.** Generators follow the entity and device registries,
    and entities with no registry entry coming and going, settling each burst of
    changes for a second. Editing a generator updates its alerts in place;
    deleting it removes them, each announced by `_deleted` (§11.3).
  - **Startup grace** [Decided with the user]. While HA starts, generators only
    add alerts. None is removed until HA has started **and** the **generator
    startup grace** (an option, 5 minutes by default) has passed, so entities
    from slow integrations or external sources (Ring-MQTT, say) don't make alerts
    come and go. An alert whose target hasn't appeared yet is kept from its stored
    record, and has no data meanwhile (§4.4). Set up while HA is running (a first
    install, or a reload), generators remove alerts straight away.
  - **The generator's sensor** is `sensor.alert_redux_generator_<name>`, named
    "Alert Redux generator <name>". It has no device and no label (§11.5).
    Attributes: `targets`, `alerts` (entity IDs), and `problems`; the two lists
    are kept out of the recorder.
  - Generated alerts get the alerts label (§11.5) and restore their state (§15.1)
    like any other. Their stored records say which generator and target they
    belong to, so a restart doesn't take them for deleted alerts.
  - A generated alert renamed with its target (or whose template variables
    change) keeps its pending `delay_on` and `delay_off`: only a change to the
    generator's alert configuration restarts them, as editing an alert does.
  - **Generated supersession.** A generator's **Supersession** section lists
    relationships each to **another generator** (its alert for the same target)
    or to a **fixed alert**, each with its propagation (§8.2). They're resolved
    live: a relationship to a generator that has no alert for the target is
    simply absent, not a broken reference. A fixed alert supersedes generated
    alerts by entity ID, as it does any alert. The generator's sensor lists its
    relationships in `supersedes` (the other generators' sensors, and the fixed
    alerts).
  - **Checks.** A generator can't supersede itself, or list one twice. Cycles
    are checked with each generator standing for all its alerts, so a cycle
    through generators is refused even before they share a target. A
    relationship to a generator that's been deleted, or to a fixed alert that
    doesn't exist, raises a Repairs issue naming the generator
    (`broken_generator_reference_<subentry ID>_<generator ID or object ID>`).
    Renaming a fixed alert rewrites generators' relationships to it. Edit forms
    list the alerts and generators that refer to them, generators included.

### 12.4 References to alerts that no longer exist

Alerts refer to other alerts in three ways: **supersession**, **propagation**, and
the **alert state** condition kind (§4.1). A reference can be left dangling when a
generator's target set shrinks, or when someone deletes an alert that another alert
refers to.

[Decided] Each kind of reference fails in the direction of *more* noise, never
less. (Force-disabling alerts that lose a partner was considered and rejected: it
**fails unsafe**, silencing an alert that's otherwise working. For example, *Server
Room Overheated (Critical)* would be switched off because the *Warning* alert it
supersedes had disappeared.)

| Dangling reference | Behaviour |
|---|---|
| A superseding alert whose superseded alert is gone | Keeps working normally. It just has nothing to suppress. |
| A superseded alert whose superseding alert is gone | Keeps working normally, and is no longer suppressed, so it notifies as if it stood alone. |
| Propagation to or from an alert that's gone | Does nothing. |
| An **alert state** condition on an alert that's gone | The condition's input is missing, so the alert goes to `no_data` (§4.4), with the missing alert listed. It's visible on the card's no-data section. |

To make sure it gets fixed:

- [Decided] Each dangling reference is raised as a **Repairs** issue (HA's
  Settings → Repairs), naming both alerts. It clears itself once the reference is
  fixed, or the missing alert comes back (e.g. the target reappears).
- [Decided] Each alert also shows its dangling references in an attribute
  (`broken_references`), in keeping with N1.
- [Decided] Repairs issues are acceptable under R6: they aren't alerts, and they're
  HA's standard place for "your configuration needs attention".
- [Decided] When you delete an alert that other alerts refer to, the delete dialog
  lists them as a warning, but deleting is still allowed.
  [Decided, phase 7] **Changed:** HA's delete dialog for subentries is the
  frontend's generic one, and integrations get no hook before a subentry is
  deleted. Instead, an alert's **edit form** lists the alerts that refer to it
  ("Alerts that refer to this one: …"), and the Repairs issue raised after a
  deletion names both alerts.
- [Decided, phase 7] References are entity IDs. When an alert's entity ID is
  renamed in the entity registry, the references to it in other alerts are
  rewritten. A deleted alert recreated under the same name gets the same entity
  ID back, so references to it work again and its issues clear.
- [Decided, phase 7] Each issue is one referring alert and one missing alert
  (`broken_reference_<subentry ID>_<object ID>`). They're checked at setup, on
  every configuration change, and whenever an alert entity is added, removed,
  or renamed.

## 13. Cards

### 13.1 Main card (`alert-redux-card`)

[Decided, N25–N29, N31]

- One card containing a **sub-card per firing alert**, sorted by priority, with
  acknowledged alerts below unacknowledged ones within each priority, and coloured by
  priority.
- Sub-card layout: **top left**, the icon and the alert name in bold; **below**,
  the on (or display) message, which can include entity values; **bottom right**,
  the controls: acknowledge (showing the current state), snooze (with the countdown
  if one is running), and dismiss (manual alerts set as dismissable from the card;
  §4.3).
- Event alerts show a **progress bar** that drains as their duration runs out.
  [Decided, phase 5] It's a thin bar in the priority colour along the foot of the
  alert's box, running from when the alert last fired to `event_expires`, and
  toned down when acknowledged.
- Superseded alerts are hidden behind a collapsed disclosure toggle under the alert
  that supersedes them [Decided, F7, §8.1]. [Decided, phase 7] A chain goes under
  its **root**: the first alert in card order that supersedes it and isn't itself
  superseded. The disclosure ("› 2 superseded alerts") sits under the root's box,
  and opens to show the superseded alerts in card order, slightly indented, with
  all their controls.
- [Decided, phase 15] **Latched alerts** (§10) are listed with the firing ones,
  after the `active` and before the `ack` alerts of their priority, with a
  dashed border in the priority colour and no glow. They say when they stopped
  and show an "Unacknowledged" badge, and offer Acknowledge and Snooze, not
  dismiss. Any alert shows "fired N×" when its `fire_count` is more than one.
- A **no-data section** at the bottom lists alerts that currently lack data.
- **Empty state:** the card always shows, with a small grey "No alerts are firing"
  when there's nothing to show.
- [Decided, F22] Disabled and suspended alerts aren't shown on the main card; they
  appear on the admin card only. The main card shows a one-line count instead, e.g.
  "3 alerts disabled".
- [Decided, phase 6] **Snooze control.** Snooze durations are a preset menu (15
  and 30 minutes, 1, 2, and 4 hours), which a `snooze_durations` card option (in
  minutes) replaces. The menu opens as a row of choices below the controls rather
  than floating over the card, where the alert's box would clip it. A snoozed alert
  shows "Snoozed · 23 min" in place of its acknowledge button, and its menu adds
  **Keep acknowledged** (ack) and **Unsnooze** (unack).
  [Decided, 0.11.1] The card's visual editor sets the durations too, as a list
  of numbers of minutes (HA's multiple text selector). It stores them as
  strings, which the card reads just as well as numbers.
- **Custom buttons** [Decided; phase 13]. An alert's custom buttons (§9.11)
  show on its box too, beside the controls, so *Garage Door Left Open* has
  *Close door* on the dashboard as well as on the phone. They're the same
  buttons, defined once; there's no separate set for the card.
  - Pressing one runs **only that button's configured action**, as the user who
    pressed it, through a new `alert_redux.press_button` action (§16), keeping
    to the rule that anything the card does is also an action (§14).
  - The card doesn't have the phones' limit of three buttons.
  - [Decided, as built] The buttons sit in the alert's controls row, before Dismiss,
    Snooze, and Acknowledge, and wrap on a narrow card. Labels are unique within
    an alert, which the forms and import enforce (`button_label_duplicate`), because
    the label is how a button is pressed. A button can't be limited to the card or
    to notifications: one definition, both places.
  - [Decided, as built] A **Require unlock** button (§9.11), which only means
    something on iOS, asks for confirmation on the card ("Run 'Lock up'?
    Confirm / Cancel", in place), since a dashboard has no unlocked phone to rely
    on. The alert's `buttons_require_unlock` attribute tells the card which.
- **Filters** [Decided, R22; phase 13]. There are two sorts, set in different
  places:
  - **Scope, set once in the card's configuration** (and its visual editor):
    which alerts the card is for at all, by **area** and by **label** (§11.6).
    For example, a card on each room's page that shows only that room's alerts,
    or a card on a network dashboard that shows only the alerts labelled
    *Network*. As for generator targets (§12.3), an alert must match each of
    the two that's set, and any one value within each. Alerts outside the scope
    are left out of the whole card, including the no-data section and the
    disabled count. [Decided, as built] Scope applies **first**, then
    supersession grouping: an in-scope alert whose superseder is out of scope
    shows as a top-level alert, and an in-scope superseder just has nothing
    folded under it, so the card never hides something in scope behind
    something that isn't. The options are `areas` and `labels`, and the area
    is the entity registry's own (alerts have no device).
  - **View, changed on the card itself**: hide acknowledged alerts, and show
    only some priorities. These are for changing while looking at the card, so
    they're controls on the card; the card's configuration only sets their
    starting values. [Decided, as built] The options are `hide_acknowledged` and
    `priorities`. The controls are a **Hide acknowledged** button and a button per
    priority present, in a row under the title (not shown when they'd have
    nothing to do); the state lives in the card, so a reload returns to the
    configured start. They are judged by the alert at the root of a supersession
    group, which takes its superseded alerts with it, as they do for the summary
    sensors (§11.2). The card says "N alerts hidden by the filters" so nothing
    disappears silently; the no-data section and disabled count follow scope only.
- Styling follows [weather_alerts_card](https://github.com/seevee/weather_alerts_card)
  [Decided, N31].
- **Priority colours** [Decided]. Used for the sub-cards, the admin card, and the
  integration icon:

  | Priority | Colour | Card treatment |
  |---|---|---|
  | Emergency | Red `#E53935` | Solid, with a **glow** |
  | Critical | Orange `#FB8C00` | Solid, with a **glow** |
  | Warning | Yellow `#FDD835` | **Caution striping** |
  | Notice | Green `#43A047` | Solid |
  | Informational | Blue `#1E88E5` | Solid |

  The glow and striping are extra emphasis for the most serious levels. Exactly how
  they look (glow strength, stripe angle and width, whether the glow pulses) is
  settled when the card is built (phase 3), keeping them legible on both light and
  dark themes. Acknowledged alerts should tone the effects down.

  [Decided, phase 3] As built, and approved on the preview page:
  - Each alert is a bordered box with a priority-coloured bar down its left edge,
    a faint priority tint, and the icon in a tinted, ringed circle.
  - **Emergency**: a strong glow that **pulses** while unacknowledged (it stays
    still when reduced motion is set). **Critical**: a weaker, steady glow. Both
    also have a priority-coloured border.
  - **Warning**: the bar is wider and striped diagonally (-45°) in yellow and
    near-black, 6 px each.
  - **Acknowledged**: the glow drops to a faint halo, the bar or stripes fade to
    about half strength, and the icon dims.
  - The Acknowledge button uses the theme's primary colour rather than the
    priority colour, which is hard to read on orange and yellow. Themes can
    override the priority colours (`alert-redux-<priority>-color`).
- [Decided, phase 3] Each alert's box also shows its priority and how long it's
  been firing. A firing alert in its no-data grace period (§4.4) gets a "No data"
  badge. Clicking the icon or name opens the entity's more-info dialog. Alerts of
  the same priority and acknowledgement are ordered newest first.
- [Decided, phase 3] The card's text is English for now.
- **Icon** [Decided]: a priority-coloured warning triangle with a circling arrow, on a
  deep indigo (`#26305A`) tile. Master SVG: `assets/alert-redux-icon.svg`.

### 13.2 Admin card (`alert-redux-admin-card`)

[Decided, N30]

- Lists **all** alerts grouped by priority, showing each one's state.
- Controls to enable, disable, and suspend each alert.
- [Decided, phase 6] As built: each row shows the icon, name, **kind**, and state
  (translated), with a few words of detail (since when it's been firing, when a
  snooze or suspension ends, how long it's had no data). The controls are shown
  to admins only, since the actions are admin-only (§6.3); everyone else sees a
  read-only list. Suspend offers 1 hour, 4 hours, 8 hours, 1 day, 1 week, or
  **Until…** a date and time. It ships in the same bundle as the main card, so
  there's no second resource.
- [Decided, phase 13] **Create, edit, and delete from the card** (admins only),
  as a front end to the same subentry flows the integration page uses, so there's
  one validation path. "Add alert" and "Add generator" in the card's toolbar, and
  Edit and Delete buttons on each row (a generated alert edits and deletes its
  generator, and the confirmation says so). The card drives the flow over Home
  Assistant's REST API (`config/config_entries/subentries/flow`) and shows each
  step in a dialog: menus as buttons, forms with Home Assistant's own form
  element, labelled from the integration's translations, with the flow's errors
  and its description placeholders (the "referrers" text) as the integration
  page shows them. Home Assistant's own flow dialog can't be opened by a custom
  card, which is why the card has a renderer. If the form element can't be
  loaded in the browser, the dialog says so and links to the integration's
  settings page. Deleting asks first, naming the alerts that supersede the one
  deleted (they keep working and get a Repairs issue, §12.4), and calls
  `config_entries/subentries/delete`. Notifier groups are still edited in Home
  Assistant's own pages.
- [Decided, F27; late phase] Export/import of alert definitions, to make up for
  losing YAML's version control and text editing. Also available as actions (§16).
  [Decided, as built] **Export** (a button for everyone; the actions are open to
  all) shows every definition as **YAML**, to copy or download as
  `alert-redux-<date>.yaml`; **Import** (admins only) takes pasted text or a chosen
  file, with a checkbox for overwrite, a **Check** button (a dry run that says what
  would be created, replaced, or left alone), and **Import**. A refusal shows the
  action's error, which lists every problem. The card's text format is YAML, which
  is how Home Assistant shows the actions' data; import also accepts JSON, which
  is YAML. (The card bundles js-yaml for this.)
- [Decided, phase 11] Generated alerts are marked "generated" beside their
  kind, with the generator's name as a tooltip; they're edited through their
  generator (§12.3).
- [Decided, after 1.3.0] **Generators with no alerts.** A generator is reached
  through its alerts, so one that matches no entities now had no row at all,
  which was confusing. Under the list (and outside its pages), a "Generators
  with no alerts" section lists them by name, from their sensors, as
  "Generator · no matching entities", with the Summary button and, for admins,
  Edit and Delete, as on an alert's row. Generators that have alerts aren't
  listed there: their alerts already lead to them.
- [Decided, 0.11.1] A firing alert that's currently **superseded** (§8.1) says
  so after its state's detail: "superseded by Back Door Left Open", naming the
  highest-priority superseder and counting any others ("+1"), with all of them
  in the tooltip. An alert that isn't firing isn't marked, since supersession
  only affects its notifications.
- [Decided; phase 13] **Paging.** The admin card lists every alert, firing or
  not, so it gets long and hard to fit on a dashboard. A card option sets how
  many alerts a page shows, with controls to move between pages; unset, it
  shows them all, as now. Pages keep the grouping by priority. The main card
  isn't paged: it shows only firing alerts, and hiding one on another page
  would defeat it. [Decided, as built] The option is `page_size`; the alerts
  are cut into pages in card order (priority, then name), a priority's heading
  counts its alerts on every page, and the card shows "Page 2 of 5" with
  previous and next buttons under the list when there's more than one page.
  [Decided, as built] The list keeps the height of the tallest page it has shown
  at the current page size and number of alerts, so a shorter last page doesn't
  shrink the card and make the dashboard rearrange its other cards.
- [Decided, as built; phase 13] On request (a click, not shown all the time), show a
  **copyable text summary** of an alert's settings. That's useful when setting up a
  matching alert. A Summary button on each row (for everyone, like export) calls
  the export action for that alert (a generated alert shows its generator) and
  turns the definition it returns into text in the card (`describe.ts`): kind and
  priority, what makes it fire, delays and messages, notifications (groups,
  reminders, throttle), buttons, supersession, voice proxies, and for a generator
  its targets. The dialog can switch to the definition itself as YAML, and both
  copy with one click. The text is made in the card, from the export, so there's one
  source of truth for what a definition holds.

## 14. Voice control

[Decided, N23, F17; late phase]

- **Assist:** the integration registers its own voice commands for acknowledging,
  removing an acknowledgement, and snoozing (with a duration), matching alerts by
  name. For example: "acknowledge the back door alert", "snooze the server room
  alert for 30 minutes". No extra entities are needed. [Decided, phase 12
  design] Also a read-only query, "what alerts are firing?". Designed in §14.1.
- **Alexa (and other limited assistants):** each alert can optionally expose a
  **proxy switch** and a snooze button, designed in §14.2. They're opt-in per
  alert so that entities aren't doubled across the board. [Changed, phase 12
  design] This originally said that turning the switch on acknowledges the alert;
  it now follows the built-in `alert`, where the switch is on while the alert
  needs attention, and turning it off acknowledges.
- The design must allow for this from the start: anything the card can do must also
  be available as an action, and alerts need names that make sense when spoken.
- [Decided, to verify] The limited-assistant solution must also work with **Google
  Assistant / Google Home**, not just Alexa. Proxy switches should work there too,
  through HA's Google Assistant integration (Nabu Casa or manual), but this needs
  checking when the phase is built.
- Proxies take their alert's area and labels (§11.6).

### 14.1 Assist

[Decided, phase 12 design] Researched against HA 2026.9. It needs no new
entities and no files in the user's configuration directory.

[Decided, phase 15] Acknowledge and snooze accept **latched** alerts (§10), and
the list adds them after the firing ones.

**One implementation, several ways in.** Four intents carry the behaviour:
`AlertReduxAcknowledge`, `AlertReduxUnacknowledge`, `AlertReduxSnooze`, and
`AlertReduxListFiring`. They're registered (`intent.async_register`) when the
config entry is set up, and removed when it's unloaded. Each has a description
and a slot schema: an optional `name`, and for snoozing an optional `duration`.
Each also has `platforms` set to `alert_redux`, so it's only offered where alerts
are exposed. They're reached through:

- **Sentence triggers.** Alert Redux attaches HA's own `conversation` trigger,
  the one automations use, with its English sentences, once HA has started. The
  built-in agent checks sentence triggers before its intents, and an Assist
  pipeline checks them before **any** conversation agent, LLM agents included,
  whatever "prefer handling commands locally" is set to. The trigger hands its
  sentence to the matching intent, with the speaker's context (so acknowledgements
  record who made them, R18), and returns the intent's reply as the spoken
  response.
- **LLM agents.** From HA 2026.8, integrations offer LLM tools through an
  `llm.py` platform. Alert Redux offers the four intents as tools (named
  `alert_redux__…`), when at least one alert is exposed, with a short prompt
  saying that alerts are acknowledged and snoozed with these tools, not by turning
  them off. Before 2026.8, HA offered every registered intent to LLM agents by
  itself, so older versions get the same tools with no extra code.
  [Phase 12 as built] The platform arrived in 2026.8, not 2026.6 as first
  researched. In 2026.8 itself, a tool handled the intent its name named, so
  there the tools take the intents' own names; from 2026.9 they're prefixed.
- **Custom sentences.** Anyone can write custom sentences for the intents by
  name, in any language. That's how languages other than English are covered for
  now; the README gives an example.

**Acting.** The intents call the existing actions (`alert_redux.ack`, `unack`,
`snooze`) with the speaker's context. §6 and §16 therefore apply unchanged: an
unacknowledgeable alert's refusal becomes the spoken reply. An action that
doesn't apply to the alert's state still does nothing (§16), but the intent
checks the state first, so the reply says why ("… isn't firing").

**Which alerts.** Voice acts only on alerts **exposed to Assist**, as HA does
everywhere. Alerts aren't among the domains HA exposes by default, so Alert
Redux exposes each alert to Assist (only to Assist, never to Alexa or Google)
**once**, by the rule the alerts label follows (§11.5): a new alert when it's
first added, and an existing alert the first time phase 12 runs. The alert's
stored record remembers that it's been done. It's never forced back: an alert
unexposed stays unexposed, and voice can't reach it.

**Matching names.** A spoken name is matched against the exposed alerts' names
and their entity aliases, ignoring case, punctuation, a leading "the", and a
trailing "alert". An exact match wins; failing that, a name that contains the
spoken words, if only one does. When several alerts match, the reply names them
and asks which. [Phase 12 as built] Past four, it names four and asks for more
of the name, since a long list is no use spoken. A trailing "please", "thanks",
or "thank you" is ignored, in names and durations: a sentence's wildcard runs to
the end of what was said, which matters most through LLM pipelines, where people
speak more naturally.

**Commands with no name** ("acknowledge the alert") act only when exactly one
alert could take the action: the one unacknowledged alert for acknowledging, the
one acknowledged alert for removing it, and the one acknowledgeable firing alert
for snoozing. Otherwise the reply names the candidates and asks for one. No voice
command ever acts on more than one alert (principle 6).

**Snooze duration.** Without a duration, the alert's Snooze button duration
(§9.11) is used: its own, or else the **Snooze button duration** option. Spoken durations are digits or English number words with seconds,
minutes, or hours, plus "an hour", "half an hour", and "an hour and a half". The
LLM tool takes minutes. A duration that can't be understood snoozes nothing, and
the reply asks how long.

**The query** lists the firing alerts, highest priority first, saying which are
acknowledged or snoozed (and until when). Past a number that's reasonable to
hear, it ends "and N more". It doesn't list alerts that aren't exposed.

**Replies** say what happened, by name: "Acknowledged Back Door Open", "Snoozed
Back Door Open for 30 minutes", "Back Door Open isn't firing", "Server Room
Overheated can't be acknowledged", "Which one: Back Door Open or Garage Door
Open?".

**Sentences** (English; the final wording is settled when it's built and tried
by voice):

- `(acknowledge|ack) [the] {alert}`
- `(unacknowledge|un-acknowledge|unack) [the] {alert}`
- `remove [the] acknowledgement (from|for|on) [the] {alert}`
- `snooze [the] {alert} [for {duration}]`
- `(acknowledge|unacknowledge|snooze) [the] alert`, the forms with no name
- `(what|which) alerts are (firing|active|on)`, `are there any [active|firing]
  alerts`, `list [the] [active|firing] alerts`

In a sentence trigger, every `{…}` is a wildcard: it captures whatever was said,
and Alert Redux does the matching.

**Limitations.**

- **Speech-to-Phrase**, HA's local speech-to-text, recognises only sentences it
  was trained on, and can't be taught these wildcards by an integration. The
  sentences need a general-purpose speech-to-text (Whisper, Home Assistant Cloud,
  and so on). The README says so.
- Text sent straight to an LLM agent (the `conversation.process` action, rather
  than a pipeline) skips sentence triggers. The LLM tools still work.

### 14.2 Proxies for Alexa and Google Home

[Decided, phase 12 design] Researched against HA 2026.9's Alexa and Google
Assistant integrations, and built on the user's earlier design for Alert2.

**What the assistants can represent.** Neither supports a custom domain such as
`alert_redux`, so proxies are unavoidable.

- **Alexa:**
  - A `switch` gets on/off, and **also** a contact sensor that reads open while
    the switch is on, reported as it changes.
  - A `button` becomes a scene.
  - Binary sensors come through only as contact, motion, or presence sensors,
    which would make a firing alert "open".
  - A `number` is a bare range with no time units.
  - Devices, scenes, and groups share one namespace, so two with the same name
    confuse it.
- **Google:**
  - A `switch` gets on/off.
  - A `button` becomes a scene.
  - Binary sensors come through only as doors, windows, smoke detectors, and
    the like.
- Both work through Home Assistant Cloud (Nabu Casa) or the manual setups.
  Gemini for Home reportedly supports what Google Assistant did.

**Rejected alternatives.**

- **A binary sensor for the state** would be asked "is X open?".
- **Separate entities for firing and acknowledging** would each need a different
  name, because of Alexa's shared namespace. That means longer utterances ("turn
  off workshop door left open acknowledgement").
- **Acknowledge and unacknowledge buttons** ("acknowledge workshop door left
  open") read well, but add two more entities per alert.
- **Snooze** by one button per duration multiplies entities. By a number entity
  plus a button, it needs two utterances and a bare number of seconds.

**The proxy switch.** An opt-in per alert. It emulates the built-in `alert`
entity, which Alexa could already handle:

| Alert state | Switch | Turning it off | Turning it on |
|---|---|---|---|
| `active` | on | acknowledges the alert | nothing changes |
| `latched` [phase 15] | on | acknowledges (releases) it | refused with an error |
| `ack`, including snoozed | off | nothing changes | removes the acknowledgement, and any snooze |
| `idle`, `no_data`, `disabled` | off | nothing changes | refused with an error |

- "Is *X* on?" asks whether the alert needs attention.
- When a snooze runs out, the switch comes back on.
- An unacknowledgeable alert's switch still shows its state, but turning it off
  is refused (§6.1).
- On Alexa, the switch's contact sensor opens whenever the switch turns on. Alexa
  routines can start from a contact sensor, though not from a switch, so a routine
  can announce an alert as it fires, and again when a snooze runs out.
- The acknowledgements go through the existing actions, with the assistant's
  context, so §6 and §16 apply unchanged.

**The snooze button.** A second opt-in per alert, called "Snooze *name*". It
becomes a scene in both assistants. Pressing it snoozes the alert for its Snooze
button duration (§9.11): the alert's own, or else the **Snooze button duration**
option. The duration isn't in the name, so the name doesn't change when the
duration does, and Alexa needn't rediscover it. The button's attributes show the
duration. A press on an alert that can't be snoozed (not firing, or
unacknowledgeable) is refused with an error. Unsnoozing is the switch's turning
on.

**The proxies themselves.**

- They're a `switch` with the alert's exact name and a `button` named "Snooze
  *name*", both following the alert's renames. Their entity IDs come from those
  names when they're created (`switch.workshop_door_left_open`,
  `button.snooze_workshop_door_left_open`), and then stay put, as an alert's do
  (§12.2).
- They have no device (§11.5, "Why not a device").
- They copy the alert's area and labels (§11.6), but aren't given the alerts
  label (§11.5).
- Their options are in the alert's form. Generators have the same options, and
  apply them to each alert they make.
- Turning an option off removes that proxy.
- **Exposure:** when a proxy is created, it's exposed to Alexa and Google once,
  and **hidden from Assist** once, where it would clash with the alert's own
  name. Assist has better commands anyway (§14.1). The rule is the alerts
  label's: done once, never forced back. Manual (non-cloud) Alexa and Google
  setups choose entities with their own filters; the README explains.

**Checked in real HA** [Phase 12 as built] (Alexa through Home Assistant
Cloud, 2026-10-02):

- **The phrases** work: "Alexa, is *X* on?", "Alexa, turn off *X*" (acknowledges),
  "Alexa, turn on *X*" (removes the acknowledgement), and the snooze button as
  "Alexa, turn on Snooze *X*" or "Alexa, Snooze *X*".
- **Refusals** can't be heard: Alexa calls actions without waiting for them, so
  it says "OK", and then shows the switch's real state (off). Refusals still
  raise their error [Decided with the user], for the dashboard and automations;
  Home Assistant logs each one an assistant asks for as an error.
- **Routines** work: a routine started by the switch's contact sensor opening
  announced the alert as it fired.
- **Google Home** isn't connected to the instance it was built on, so it's
  unverified; the proxies use HA's Google integration in the ordinary way
  (on/off, and a scene).
- **Newer assistants:** Alexa+ wasn't distinguished; Gemini for Home is
  unverified, as above.

## 15. Startup, resilience, persistence

### 15.1 Restoring state

[Decided, F21] Alert Redux restores its state across restarts: firing status,
acknowledgement, snooze timer, disabled/suspended status and time, event-alert
expiry, pre-acknowledgements, throttle counters, and the reminder schedule position.
[Decided, phase 2] Also pending `delay_on` and `delay_off` deadlines. These are
honoured if the condition still holds when data first returns after the restart,
and dropped if not. Inputs that are still loading don't cancel them. Restarting the
timers from zero would delay an alert that was about to fire, which fails quiet.
[Decided, phase 1] This uses a single `Store`, saved shortly after every change, as
the one source of truth; `RestoreEntity` isn't used. Its periodic 15-minute save is
exactly the gap the Store closes, and some state that must persist (throttle
counters, held quiet-hours notifications, the retry queue) doesn't belong to any
entity, so a Store is needed anyway. Per-alert records are keyed by the entity's
unique ID, which also covers generated alerts. The records also tell Alert Redux
which alerts are new or deleted since the last run (for `_created`/`_deleted`,
§11.3), and whether an alert has been given the alerts label (§11.5) and
[phase 12] exposed to Assist (§14.1), and whether its proxies' exposure
has been set (§14.2).

After a restart:

- An alert that was firing and still is resumes quietly: **no** new on notification
  [Decided, R16 response].
- An alert that was firing and no longer is ends normally, with a done notification.
  [Decided, 1.0.0] When a firing's duration ran out during the restart, it ends
  just **after** the alert's first state is written, not before. HA's logbook
  leaves out an entity's first state after a restart, so an alert already idle
  by then showed "active" as its last row. Ending afterwards makes an ordinary
  active → idle row (§11.4). Its other deadlines wait for the ending, which
  clears or resets them, so a reminder that fell due before it ran out isn't
  sent just ahead of the done notification.
- A snooze or suspension that ran out during the restart ends as soon as HA is back.
- [Decided, phase 4] A reminder that fell due during the restart is sent as soon as
  HA is back. It isn't an on notification, so it doesn't break "resumes quietly".
- [Decided, phase 15] A **latched** alert (§10) stays latched, with its fire count
  and reminder schedule.

### 15.2 Notifier retry queue

[Decided, R16 response]

- If a group member doesn't exist yet or fails, the notification to that member is
  queued and retried with backoff, up to a timeout (default a few minutes,
  configurable). Retries are per member, so one broken member doesn't hold up the
  rest of its group.
- After the timeout, the failure is logged. If no member of any target group
  received the notification, it goes to the fallback group (§9.4).
- This applies all the time, not just at startup, so it also covers integrations
  restarting while HA is running.
- [Decided, phase 4] The backoff starts at 5 s and doubles, up to 60 s between
  tries, with a last try at the timeout itself. The timeout (the **retry timeout**
  option) defaults to 5 minutes, counted from when the notification was sent. A
  legacy action that's registered while members wait for it is retried at once.
- [Decided, phase 10] Held quiet-hours notifications are kept in the same
  store (§9.9).
- [Decided, phase 4] The queue is kept in the notifier module's own store, separate
  from the alerts' (so that the module stays extractable, §9.1), and resumes after a
  restart. A notification whose timeout passed while HA was down goes to the
  fallback as soon as it's back, unless a member had already received it.

### 15.3 Startup order

- Alerts start in `no_data` and evaluate as soon as their inputs report data
  [Decided, N33]. There's no `early_start` [Decided, R16].
- An optional startup grace period (global setting) delays the first evaluation.
  [Decided, phase 2] It's called the **startup delay** (default: none). It applies
  only while HA is starting, counted from when Alert Redux is set up, and not to
  later reloads or newly added alerts. During it, alerts that aren't firing show
  `no_data`, and firing alerts keep their restored state.
- Integrations or entities that disappear and come back are handled by the no-data
  mechanism (§4.4).
- [Decided, phase 5] Triggers (event alerts, on/off sides) attach once HA has
  started, and after the startup delay while HA is starting.

### 15.4 Logging

[Decided, R6] Alert Redux's own problems are logged; there are no internal alerts.

## 16. Actions

[Decided] All actions target alert entities in the standard way (`entity_id`,
area, label, …):

| Action | Purpose |
|---|---|
| `alert_redux.ack` / `alert_redux.unack` | Acknowledge, or remove the acknowledgement. |
| `alert_redux.snooze` | Snooze for a `duration`. |
| `alert_redux.disable` / `alert_redux.enable` | Disable or enable. Admin only (phase 6). |
| `alert_redux.suspend` | Suspend for a `duration`, or `until` a time. Admin only (phase 6). |
| `alert_redux.fire` / `alert_redux.dismiss` | Fire or dismiss a manual alert; `fire` can take `data`. |
| `alert_redux.press_button` | Run one of an alert's custom buttons (§9.11), as the main card does (§13.1). Takes the button's `label`. [Decided; phase 13] Labels are unique within an alert, so the label is enough. A label the alert doesn't have is the error `no_such_button`. It isn't admin-only: it runs only that button's action, as the caller. |
| `alert_redux.refresh_generator` | Re-evaluate a generator's targets now (debugging; §12.3). [Decided, phase 11] Takes the generators' sensors as `entity_id`. |
| `alert_redux.export` / `alert_redux.import` | Export or import alert and generator definitions; `import` takes `overwrite` (default off) and `dry_run` (default off). Not entity actions: `export` takes an optional `entity_id` list (alerts, or generators' sensors; default all). |

**Managing alert definitions by action** [Decided, Q10]. There are **no** separate
create or edit actions. Instead:

- The admin card creates and edits alerts through HA's own config-subentry flows
  (which the frontend can already drive), so there's only one validation path.
- **Export and import** (§13.2) are also actions. `alert_redux.export` returns alert
  and generator definitions as response data, and `alert_redux.import` takes them.
  Definitions can then be scripted through the same validation as the UI, without a
  second set of configuration code (R21).
- **Overwrite protection** [Decided]: `alert_redux.import` has an `overwrite` flag,
  off by default. Without it, an import that would replace an existing alert or
  generator is refused.
  - [Decided] Imports are all-or-nothing. Every definition is validated first, and
    if any fails validation, or would overwrite without the flag, **nothing** is
    imported. The error lists every conflict and problem, so a partial import can't
    leave things half-changed.
  - [Decided] "Existing" is decided by each definition's **stable ID**, which export
    includes. A new definition whose entity ID would clash with a different existing
    alert is also a conflict.
- [Decided; phase 13] **The file.** `{format: alert_redux, version: 1, alerts: [...],
  generators: [...]}`. Each definition is `id` (the subentry ID), `name` (the
  title), and the subentry's stored data, flattened as stored (no form sections;
  settings that use the default are absent), with `kind` as text. Instance-specific
  references are **names**: `notifier_groups` lists the groups' names, and a
  generator relationship's `generator` is the other generator's name. Import maps
  them back, ignoring case, and an unknown name is a problem. Groups, global
  options, runtime state, and the registry's area and labels are not exported.
  Alert references stay entity IDs; dangling ones are allowed, as in the forms
  (§12.4). Export/import of notifier groups, as a whole, to rebuild an instance,
  is a possible later feature.
- [Decided; phase 13] **Matching.** Import creates a new definition with the `id`
  it was exported with, so importing a file again, on this or another instance,
  finds the same definitions. A definition without an `id` (hand-written, or from a
  converter) matches the existing one of its type with the same name, ignoring
  case, else is new. A new definition (or a rename) with another's name is a
  conflict (`name_exists`), as is an `id` belonging to a subentry of another type.
- [Decided; phase 13] A definition identical to the existing one is `unchanged`,
  not a conflict, so repeating an import is harmless. A different one needs
  `overwrite`. An existing definition's **kind can't change** by import (the
  entities are made per kind, and the forms can't change it either).
- [Decided; phase 13] Import checks with the forms' own checks
  (`validation.py`), run over the definitions as the import would leave them, so
  supersession cycles across the file are caught. Leftovers a form would fill in
  are filled in: priority `warning`, acknowledgeable, and the kind's other
  defaults; durations may be seconds or `HH:MM:SS`.
- [Decided; phase 13] `dry_run` checks and reports without changing anything. The
  response lists `created`, `updated`, and `unchanged` definitions; a refusal is
  one `import_refused` error listing every problem.
- [Decided] Import is an **admin-only** action, since it changes configuration.
  Export is available to everyone, like reading any other entity data.
- There's no `alert_redux.delete` action for now. It can be added later if a use
  appears.

[Decided, phase 1] An action that doesn't apply to an alert's current state (such
as `ack` on an `idle` alert, `unack` on an `active` one, or `dismiss` on an `idle`
one) does nothing, and fires no event, so a call targeting several alerts doesn't
fail because some of them aren't in the right state. Actions the spec refuses are
errors: acknowledging or snoozing an unacknowledgeable alert (§6.1), and `fire` or
`dismiss` on an alert that isn't manual.

There's no bulk acknowledge [Decided, R19]. Targeting several entities in one call is
allowed, because HA's normal targeting permits it; there's just no dedicated "ack
all" action.

## 17. Not included

- YAML configuration and reloading [R21].
- Ad-hoc alerts [R4].
- A Python API [R20].
- Internal alerts [R6] (for now).
- Bulk acknowledge [R19] (for now).
- A separate escalation or `skip_first` feature [R8, R11]; use supersession.
- `early_start` [R16].
- Alert2's history view [N24]; use the Activity card.
- Separate notifier groups for the on, reminder, and done notifications [R10].
- Notifier groups chosen by template or entity [R13] (for now; not ruled out).
- A separate notifier integration [R24] (for now; the notifier module is built to
  be extracted later). Groups aren't exposed for outside use in the meantime.
- Migration code for the built-in `alert` inside the integration [F28]. Instead, a
  separate converter utility in this repository (not shipped in the integration)
  reads an `alert:` YAML section and writes a file for `alert_redux.import`. A
  similar standalone converter does the same for Alert2 alerts (phase 14). Both are
  in `tools/`, built.

## 18. Open questions

| # | Question | Refs |
|---|---|---|
| ~~Q1~~ | ~~Notifier model~~ Resolved: all three kinds, behind Alert Redux's own notifier groups; buttons, replacing and clearing (§9.1–§9.4, §9.10, §9.11). | R1, R24, R25, N37 |
| ~~Q2~~ | ~~Quiet-hours design~~ Resolved: loud groups, an external quiet-hours entity, a priority threshold, hold or soften (§9.9). | R9, R25 |
| ~~Q3~~ | ~~Should propagation optionally snooze?~~ Resolved: yes (§8.2). | N13 |
| ~~Q4~~ | ~~Generator details~~ Resolved: supersession can be generated; generators are entities (§12.3). | F20 |
| ~~Q5~~ | ~~Export/import~~ Resolved: yes, in the admin card, late phase (§13.2). | F27 |
| ~~Q6~~ | ~~Migration from built-in `alert:`~~ Resolved: no code in the integration; a separate converter utility that produces import files, late phase (§17, §20). | F28 |
| ~~Q7~~ | ~~One event per change, or one combined event?~~ Resolved: separate events (§11.3). | §11.3 |
| ~~Q8~~ | ~~Review the remaining proposals~~ Resolved: all approved. | — |
| ~~Q9~~ | ~~Dangling references~~ Resolved: fail-safe behaviour, with Repairs issues (§12.4). | §12.4 |
| ~~Q10~~ | ~~Create/edit/delete by action?~~ Resolved: export/import actions, with overwrite protection (§16). | §16 |
| ~~Q11~~ | ~~Remaining §9.9 details~~ Resolved: per-group threshold override; members that can't soften hold instead (§9.9). | §9.9 |
| ~~Q12~~ | ~~Done notifications while throttled~~ Resolved: held, and covered by the throttling summary (§9.7). | §9.7, §9.8 |
| Q13 | [Deferred] When should the condition alert kinds get a class or strategy object each? Not yet: the five kinds share one condition alert class, which branches on the kind in a few places (attributes, sources, judging, on/off edges), and the sources hide most of the differences. If more condition kinds are added, split it then. Event kinds are less likely to need this: a bus event alert is already just a trigger alert with an event trigger, so a new event kind would more likely be another trigger shape. | F23 |
| ~~Q14~~ | ~~Raise the minimum HA version for phase 12?~~ Resolved: raised to **2026.6**. Phase 12 itself didn't need it, but testing locally against older HA (as decided here) found that 1.0.0 never worked on its declared 2025.3: its subentry forms need `_get_entry` (HA 2025.4); before 2025.12, every alert form's object selectors with typed fields are refused; and before 2026.6, lists of objects (notification buttons, supersession relationships, group actions) can't be saved. 2026.6 is the oldest release that works without workarounds [Decided with the user]. The paths HA 2026.6–2026.8 still take (LLM tools before 2026.8, the 2026.8 tool naming, the `admin_only` fallback before 2026.9) are tested locally (`scripts/test-against-ha.sh`), apart from CI. | §14 |

## 19. Decision log

Decisions with their reasons, in the order they were made.

| Decision | Reason |
|---|---|
| Transparency through attributes; HA events for glue | Makes alerts easy to inspect and easy to build on [N1, N2]. |
| Condition, event, and manual kinds | Covers state-based, momentary, and externally controlled alerts [N3, N6, R2]. |
| Simple condition kinds alongside templates | Templates are too fiddly for common cases [N5]. |
| Event alerts have a duration | A momentary event still needs to be seen [N4]. |
| Only manual alerts can be dismissed | Other kinds end on their own; dismissing them would hide real problems [R3]. |
| No ad-hoc alerts | Everything that can fire is declared and visible [R4]. |
| Missing data is a state, not an error | Alert2's error behaviour was a pain point [N7]. |
| Five syslog-style priorities | Familiar, clear ordering [N10]. |
| Supersession, transitive, with debounce | Avoids redundant notifications; debounce avoids races [N11, R15]. |
| Acknowledgement propagation set per relationship; default None | Needed in the workshop case, wrong in the server-room case; opt-in is the safe default [N12]. |
| Propagation can snooze instead of acknowledging | So a superseding alert still speaks up if you take too long [N13]. |
| Superseded alerts collapsed on the card | Alerts implied by another alert shouldn't clutter the card [F7]. |
| Escalation and `skip_first` through supersession | One mechanism instead of three [R8, R11]. |
| Always send the done notification, even without an on notification | You want to know when it's over, whether or not you acknowledged it or heard it start; you may know the world's state some other way [R10, F25]. |
| Drop a superseded alert's done notification when both end together | One "door closed" message is enough [F25]. |
| `name` available in message templates | Messages don't repeat the name automatically, so it must be easy to include deliberately [N17]. |
| Snooze-end reminder rule: remind now unless a scheduled reminder is under 5 min away | The alert speaks up when the snooze ends, without a double reminder; reminders show the real firing duration [§6.2, §8.3]. |
| `subject_entity_name` (subject entity) in message templates | Generated alerts can share one message template without deriving names from the alert name [§9.5]. |
| Export/import actions instead of create/edit actions; import won't overwrite without a flag | One validation path; protects existing definitions from accidental replacement [Q10]. |
| Export files name notifier groups and generators, and keep subentry IDs | A file moves between instances, and re-imports find the same definitions [phase 13]. |
| Import checks with the forms' own checks, over the whole file, all or nothing | One validation path; a cycle between two imported alerts is caught [phase 13]. |
| All three notifier kinds supported | The entity model can't carry `data`, and mobile features still need the legacy actions [S1–S4]. |
| Alert Redux's own notifier groups, flagged loud or quiet | Integrations can't say whether they're noisy; only you know [N34, N35]. |
| Notifier layer as a self-contained module, not a separate integration (yet) | Avoids a two-step install and two-repo churn while the design settles; extract it later [N36, R24]. |
| Quiet hours driven by an external entity | Reuses HA's schedule editor; automations can control it [R25]. |
| Custom notification buttons defined independently of notifiers | Alerts can offer "Close door" without depending on mobile details; only configured actions run [N37]. |
| Done notifications throttle along with on notifications | Throttling is exceptional; the throttling summary covers it [§9.7]. |
| Quiet-hours summary gives start and end times | For alerts announced before quiet hours, the summary is where you learn they ended [§9.9]. |
| Priority palette: red, orange, yellow, green, blue | The two original reds were too close, and the darker one looked less urgent than Critical [§13.1]. |
| All alerts carry one automatically applied label | One selection covers every present and future alert on target-based cards. A single device was rejected: current HA prefixes device names to entity names and IDs [§11.5]. |
| Notifications after the main card, split into three phases | The card makes notification behaviour easier to debug; smaller phases [§20]. |
| Events built in from phase 1 | Easier than retrofitting every transition; useful for debugging [§20]. |
| Separate events per change, with a common prefix | Easy to filter; list-based event triggers cover listening for several [§11.3]. |
| Paired events when one change implies another | Snooze and ack don't always move together, so firing both gives the most information [§11.3]. |
| Per-priority counts as attributes, not sensors | Avoids multiplying entities [§11.2]. |
| A superseded alert is left out of the summary's unacknowledged figures, and counted by a `superseded` sensor | The card hides it and it sends nothing, so a signal light shouldn't ask for its acknowledgement; the firing figures stay factual, and nothing is hidden without a count [§11.2]. |
| Generators are entities, with a refresh action | Somewhere to show what they generated; refreshing helps debugging [§12.3]. |
| Supersession can be generated per target | Matches the main pattern (each door's *Left Open* over its *Open*) [§12.3]. |
| Dangling references fail towards more noise; flagged as Repairs issues | Losing a partner must never silence a working alert; Repairs is HA's standard place for configuration problems [§12.4]. |
| Card dismiss button for manual alerts is a per-alert setting | Some manual alerts are for a person to dismiss; others are dismissed by automation once the cause is fixed [§4.3]. |
| Reminder schedule lists | Proven in both the built-in `alert` and Alert2 [R12]. |
| UI-only configuration | HA is moving away from YAML; avoids writing configuration code twice [R21]. |
| Actions instead of a Python API | Keeps a single, public interface [R20]. |
| Log instead of internal alerts | Alert2's internal alerts caused trouble [R6]. |
| No bulk acknowledge | Alerts should be handled deliberately [R19]. |
| No history view on the card | Confusing in Alert2; the Activity card does it better [N24]. |
| "Suspend" for timed disabling | Keeps "snooze" meaning what it usually means [N22]. |
| Persist with a single Store, not `RestoreEntity` | Saves on every change; some persistent state isn't tied to an entity, so a Store is needed anyway [§15.1]. |
| Inapplicable actions are no-ops, not errors | Calls that target several alerts shouldn't fail because some are in the wrong state [§16]. |
| Firing alerts stay `active`/`ack` through the no-data grace period | "Firing" is defined by state, so signal lights and automations shouldn't see a dropout; attributes and the `_no_data` event show it [§4.4]. |
| The extra condition, and the event-alert condition, are templates | Templates can be tracked reactively; HA conditions can't, so time-based ones would need polling. The same form for both kinds keeps things consistent [§4.1, §4.2]. |
| A state alert can target `unavailable`/`unknown` | "Lock unavailable for 10 minutes" is a common use of the built-in `alert` [§4.1]. |
| Template results must be clearly true or false | Reading garbage as false would silently hide a broken alert [§4.1]. |
| No data in any input means no data for the alert | Literal reading of §4.4; the alert depends on every input [§4.1]. |
| Pending delays survive restarts | Restarting them from zero fails quiet [§15.1]. |
| `_ended` carries a reason | Done messages must tell a resolved alert from one that lost its data (and, later, one that was disabled) [§11.3]. |
| Subentry changes applied in place, not by reloading the entry | A reload made every alert briefly `unavailable`, and would push condition alerts through `no_data` [§20]. |
| The card shows the default on message when none is configured | The default is a fallback; seeing it is a reminder to write a real message, and hiding it would special-case something that shouldn't happen [§9.5]. |
| Card messages rendered by the integration, with the on notification's context | One template engine, and the card shows what the notification says [§9.5]. |
| Browser refresh: a notification per new card version, plus a reload banner in the card | Resources load once per page; nothing server-side can reload a browser [§20]. |
| An unacknowledged Emergency alert's glow pulses | The one level that should catch the eye from across the room; acknowledging it stops [§13.1]. |
| Firing again resends the on message only while unacknowledged | Keeping the acknowledgement exists to stop repeats from nagging [§4.2]. |
| No default groups: send to the fallback, and raise a Repairs issue | Alerts notify somewhere from day one, and the admin is told why rather than it being buried in a log [§9.4]. |
| Default reminder schedule `[10, 20, 30, 60]` | Alert2's 60 minutes was too long for everyday use, and 10 minutes throughout too frequent; escalating gaps settle at hourly [§9.6]. |
| Unacknowledging resumes reminders on the original schedule | Consistent with how snooze-end counts slots; missed slots aren't made up [§9.6]. |
| Done message wording depends on why the firing ended | A lost-data end must never read as resolved [§9.5]. |
| Last retry at the timeout itself | So the timeout means what it says, rather than giving up at the last backoff that fits [§15.2]. |
| The retry queue has its own store | Keeps the notifier module extractable [§15.2]. |
| A new on/off alert whose on criterion is already true fires | An unknown previous value counts as false, which fails loud; persisting the edge state stops restarts and dropouts from creating false edges [§4.1]. |
| On/off delays need a template on their side | A delay needs the criterion to hold, which a trigger alone can't [§4.1]. |
| Threshold limits are templates | One field per limit covers a number, an entity, and anything computed, like the other template fields [§4.1]. |
| Per-priority event durations 60/30/15/10/5 minutes | More serious events stay visible for longer [§4.2]. |
| An event alert's condition with no data fires the alert | A broken condition must never silence the alert [§4.2, §12.4]. |
| Triggers attach once HA has started, after the startup delay | Entities loading at startup would otherwise fire trigger alerts, as automations avoid [§4.2, §15.3]. |
| Event alerts' trigger variables are `trigger`, stored JSON-safe | The same name as in automations; storing them keeps the card and done message right across restarts [§9.5]. |
| Duration changes apply from the next fire | A running firing keeps the expiry it was given [§4.2]. |
| Acknowledging a snoozed alert makes the acknowledgement lasting | Gives "keep it acknowledged" without unack-then-ack [§6.1]. |
| Snooze durations are a preset menu, configurable per card | Quick to use on a phone; the card option covers other needs [§13.1]. |
| Re-snoozing replaces the deadline, even with a sooner one | "Re-snooze or extend" means the latest choice wins [§6.2]. |
| No reminder when a snooze ends on an alert without reminders | It opted out of reminders [§6.2]. |
| Disabling detaches the alert's inputs | Nothing can fire it, and nothing is evaluated while it's off [§6.3]. |
| Re-enabling starts from scratch, with on/off edges re-armed | A condition that still holds fires anew; fails loud [§6.3]. |
| Disable and suspend: the latest call wins | Simple to explain, and each is announced by `_disabled` [§6.4]. |
| Disable, enable, and suspend are admin-only | They're maintenance and debugging tools, not everyday operations [§6.3]. |
| The admin card's controls are for admins only | Matches the admin-only actions; others get a read-only list [§13.2]. |
| Both cards ship in one bundle | Nothing new to register, and one refresh covers both [§13.2]. |
| Alerts refer to other alerts by entity ID, following renames | Readable in attributes and Repairs issues; an alert deleted and recreated under the same name gets the same ID, so references to it work again [§8.1, §12.4]. |
| `superseded_by` lists firing superseders, transitively, whether or not the alert is firing | Shows at a glance what is suppressing it; the card groups by it [§8.1, §13.1]. |
| The debounce applies only to alerts that something supersedes | Nothing else has a reason to wait [§8.1]. |
| The done window counts a superseding alert ending before or after | Two alerts with different `delay_off`s end in either order [§9.7]. |
| The alert state kind's time is its `delay_on` | One mechanism, already kept across restarts [§4.1]. |
| Propagating to an already active superseding alert acts at once | "You're there, you know" applies whether or not it has fired yet [§8.2]. |
| Propagation follows direct relationships; a pre-acknowledged firing passes it on | Each relationship's setting means what it says; an acknowledged alert is acknowledged, however it got there [§8.2]. |
| `pre_acked_by` is a list | Several superseded alerts can pre-acknowledge one alert [§8.3]. |
| Pre-acknowledgements are kept by unique ID | They survive renames without depending on the order of registry events [§8.3]. |
| The edit form lists an alert's referrers, instead of the delete dialog | HA gives integrations no hook into the subentry delete dialog [§12.4]. |
| Restart checks ride on install restarts | Development already restarts HA to install each subphase; pytest covers every restore path in its own phase, and a ledger confirms them in real HA one install later [§20]. |
| The logbook describes only events that add to the state rows | The state rows already show each state change and who made it; describing the rest would show those changes twice [§11.4]. |
| `_data_restored` event | Data returning to a firing alert in its grace period changes no state, so nothing else would show it [§11.3]. |
| The no-data count includes firing alerts in their grace period | A broken input shows at once (fail loud) [§11.2]. |
| The notifier remembers where each notification is showing | Clears reach the members actually showing it, after group edits and for fallback deliveries [§9.1, §9.10]. |
| Snoozing and pre-acknowledgement clear notifications | Both are acknowledging [§9.10]. |
| Newer notifications and clears drop waiting retries for the same tag | A retried notification must not arrive after it was replaced or cleared [§9.10]. |
| A member's mobile features are automatic, or set explicitly | `notify.mobile_app_*` just works; a legacy notify group of phones can opt in [§9.3]. |
| Button action IDs use the unique ID and a hash of the button | Taps survive renames, and an edited button's old taps can't run a different action [§9.11]. |
| At most three buttons on every mobile member | Android's limit, and the platform isn't known for notify groups [§9.11]. |
| Snooze button duration: 1 hour by default | Long enough to deal with most things, short enough not to forget [§9.11]. |
| Throttling counts held notifications, and ends when the rate drops | Follows Alert2: a flapping alert stays quiet until it calms down, then says once what happened [§9.8]. |
| The throttling summary's wording is fixed | It reports what Alert Redux did, not what the alert is about [§9.8]. |
| Generators make condition alerts only | The target fills in the kind's entity or a template; triggers can't be templated [§12.3]. |
| Target criteria: AND across, OR within | Narrowing by several criteria (every battery sensor in the garage) is the common need [§12.3]. |
| Generated alerts are keyed by the target's registry ID | A renamed target keeps its alert and its state [§12.3]. |
| Generated alerts are never targets | Alert state generators can't feed on themselves or each other [§12.3]. |
| Diagnostic entities can be targets | Battery levels and connectivity are obvious alert targets [§12.3]. |
| No removals until a grace period after startup | Slow integrations and external sources don't make alerts flap [§12.3]. |
| Generated supersession resolves live, per target | A partner generator without an alert for a target is normal, not a broken reference [§12.3]. |
| Cycles are checked with generators standing for all their alerts | A cycle between generators would appear as soon as they shared a target [§12.3]. |
| A renamed target keeps its alert's pending delays | Restarting them would hold back an alert about to fire, which fails quiet [§12.3]. |
| Quiet hours live in the notifier, with urgencies | Holding and softening are delivery; the notifier stays free of alerts [§9.1, §9.9]. |
| The owner says what's sent when quiet hours end | Only Alert Redux knows which alerts are still active and how to summarise them [§9.9]. |
| An unavailable quiet-hours entity isn't quiet, but doesn't release what's held | New notifications fail loud; a blip in the night doesn't deliver the morning summary [§9.9]. |
| One quiet-hours summary line per alert | A door opened three times in the night is one line, with the times it was opened and for how long in all [§9.9]. |
| The notification button is "Snooze Alert", and the app's own snooze options stay | Tells ours apart without taking away something people may use [§9.11]. |
| A superseded alert's reminder waits for a superseding alert about to fire; sent late if it doesn't | A reminder and the superseding on notification arriving together is noise, and no setting should be needed to avoid it; a lost reminder would fail quiet [§8.1]. |
| Logbook messages are capitalised | They sit beside the translated states, which are [§11.4]. |
| Manual alerts can end by themselves after a duration, as an option, not a new kind | Fills the gap between manual and event alerts without a ninth kind, and without overturning R2 or R3 [§4.3]. |
| 1.0.0 is 0.11.1 plus self-ending manual alerts and an entity refactor, after a shorter soak of its own | The 0.11.1 soak found only trivia, and a 1.0.0 identical to it would add nothing; the refactor keeps manual-only code out of the base class every kind shares [§20]. |
| An alert's area and labels live in the entity registry; the form edits them there | One place for the values, so edits on the entity's settings page aren't overwritten, and proxies can follow the alert whichever way it was edited [§11.6]. |
| Generated alerts default to their target's area (provisionally) | The alerts a generator makes are usually about entities in different areas, e.g. each door's *Left Open* alert [§11.6]. |
| A generator's area and labels follow changes, as a diff | Editing a generator should reach the alerts it has made, without undoing what a user set by hand or the alerts label [§11.6]. |
| Card filters are either scope, in the card's configuration (area, label), or view, on the card (hide acknowledged, priorities) | Scope is set once per placement, e.g. a card per room page; the view is what you change while looking at the card [§13.1]. |
| The admin card can be paged; the main card isn't | The admin card lists every alert and gets long; the main card shows only firing alerts, which must never be hidden on another page [§13.2]. |
| Custom buttons show on the main card too, from the same definitions | A *Close door* button is as useful on the dashboard as on the phone, and one definition can't drift apart from another [§13.1]. |
| Assist sentences are HA's conversation triggers, attached by the integration | The one public way for an integration to add sentences; custom sentence files would mean writing into the user's configuration (R21), and pipelines check triggers before any agent, LLM agents included [§14.1]. |
| Four intents carry the voice behaviour; sentences, LLM tools, and custom sentences all reach them | One implementation, whichever way the command arrives, and other languages can be added without code [§14.1]. |
| Voice acts only on alerts exposed to Assist; each alert is exposed once, never forced back | Follows HA's convention and leaves the user in control, without making every alert need exposing by hand [§14.1, §11.5]. |
| Voice can ask which alerts are firing | You can find out what's wrong before acknowledging it, and LLM agents learn the alerts' names from it [§14.1]. |
| A command with no name acts only if exactly one alert fits | Convenient when one thing is wrong, and never acts on several alerts at once (principle 6) [§14.1]. |
| Phase 12 is 1.1.0 | It follows 1.0.0, so it's a 1.x release [§20]. |
| The proxy switch emulates the built-in `alert`: on while active, off to acknowledge | "Is X on?" asks whether it needs attention, and on Alexa the switch's contact sensor can start a routine as the alert fires; separate firing and acknowledgement entities would need longer names [§14.2]. |
| One optional snooze button per alert, "Snooze *name*", for the alert's snooze button duration | One utterance; more durations would multiply entities, and a number entity needs two utterances and bare seconds; the name stays put when the duration changes [§14.2]. |
| Proxies are exposed to Alexa and Google once, and hidden from Assist once | Opting in means wanting them there; in Assist they'd clash with the alerts' own names [§14.2]. |
| The minimum HA version stays 2025.3 for phase 12 | Nothing in phase 12 needs a newer one; older paths are tested locally instead [§18, Q14]. |
| ~~The minimum stays 2025.3~~ The minimum HA version is 2026.6 | Local testing found 1.0.0's forms needed 2026.6 all along; it's the oldest release that works without workarounds, and keeping a stated minimum that doesn't work helps nobody [§18, Q14]. |
| Proxy refusals keep raising their error, though Alexa can't say so | The dashboard and automations still need to hear it; Alexa says "OK" but shows the real state, and Home Assistant logs the refusal [§14.2]. |
| A duration that ran out while HA was down ends just after the first state is written | HA's logbook leaves out an entity's first state after a restart, so an ending before it had no row [§11.4, §15.1]. |
| Alert Redux ships an agent skill, checked against the code by a test | Agents can drive Alert Redux through MCP, but had to dig through the forms' schemas to do it; a test keeps the skill from drifting as the code changes [§20]. |
| Latching alerts (§10) replace the acknowledgement queue (R7), in a late phase 15 | The real need is a firing that ended before anyone saw it; a per-alert setting answers it on the existing model, where a queue would be a subsystem. One item per alert, with the fire count shown, is simpler than one per firing [§10]. |
| iOS interruption levels follow priority (Emergency critical, Critical time-sensitive), without a setting | Apple's levels match our top two priorities; a member's own `push` data is the escape hatch, and a setting waits for demand [§9.3]. |
| Form layout unchanged, except Area and labels moves up beside the name, priority, and icon | A review found nothing else worth regrouping; the sections left at the bottom are alphabetical [§12.1]. |
| The quiet-hours summary stays an ordinary notification | The queue it might have used is gone; the summary already tells you what you missed [§9.9]. |
| Displayed state names in a state alert are dropped (N38) | Translations, device classes, and entities' own state names make recognising them a lot of complexity for marginal gain; a state alert's target stays the real state. Revisit if HA's state selector becomes usable for it [§4.1]. |
| Phase 13 is 1.2.0, phase 14 1.2.1, phase 15 1.3.0 | Integration feature phases are minor releases; phase 14 ships tools, not integration features, so it takes a patch version [§20]. |
| Converters take only the shapes users have to hand, and drop what has no equivalent with a warning | A single alert's YAML (as the Alert Manager card shows it) is the commonest conversion request; generators and a few options can't be translated faithfully, so the report names them rather than guessing [§20]. |
| Latching alerts are a state, `latched`, with user choices on the details (phase 15) | A state shows in automations, history, and the alert state kind; latched alerts count as unacknowledged so signal lights stay on; snoozing one puts its reminders off; a dismissal latches only without a user, since a person dismissing it has seen it [§10]. |
| `ack_reminders_only` needs no conversion (phase 15) | In Alert2 it only keeps the done notification of an acknowledged alert, which Alert Redux always sends (§9.7); the phase plan had grouped it with `ack_required` [§20]. |

## 20. Phase plan

[Decided] Each phase is small enough to build, test, and live with before the next
one starts, and each ends with a usable release.

**Every phase ends with:**

- smoke tests for the new behaviour (`pytest-homeassistant-custom-component`), and
  the card type-checked and rebuilt;
- a run in a real HA instance; [Decided, phase 6] checks of behaviour across a
  restart don't get restarts of their own. They're set up at the end of a run and
  checked after the next install restart, through the ledger in
  `docs/restart-checks.md`;
- CI green, and a release (manifest version bumped, card rebuilt; `0.N.0` before 1.0.0, then see below), so HACS
  can install it;
- the spec updated if building the phase changed any decisions.

**Choices built into this ordering:**

- **Notifications come after the main card** (your suggestion). With the card in
  place, you can see an alert's state while debugging what was or wasn't sent.
- **Notifications are split in two.** Phase 4 does basic delivery. Phase 9 does the
  device-specific features (replacing, clearing, buttons), and phase 10 does
  throttling and quiet hours.
- **Events come with the core (phase 1), not with the summary sensors.** Every state
  change fires its event (§11.3). Building that in from the start is simpler than
  adding it to every transition later, and events are useful for debugging too.
  Summary sensors and the logbook descriptions stay in phase 8.
- **Alert configuration forms arrive with each alert kind.** Configuration is UI-only
  (R21), so an alert kind is unusable until its subentry form exists. Each phase that
  adds a kind also adds its form.
- **The alert state condition kind moves to phase 7.** It refers to other alerts, so
  it belongs with the rest of the alert-to-alert machinery (supersession, dangling
  references).

### Phase 1 — Core alert entity and manual alerts (0.1.0)

- The alert entity: `idle`, `active`, and `ack` states, with translations; core
  attributes (§11.1); state restored across restarts (§15.1).
- Manual alerts (§4.3), with their subentry form: name, priority, icon,
  acknowledgeable, dismissable from the card.
- Actions: `fire`, `dismiss`, `ack`, `unack` (§16), with who-did-it recorded (R18).
- Events for every transition so far (§11.3).

*Done when* a manual alert can be created in the UI, fired and dismissed by action,
and acknowledged, and it survives a restart.

### Phase 2 — Condition alerts I (0.2.0)

- **State** and **template** condition kinds (§4.1), with their forms.
- `delay_on`, `delay_off`, and the optional extra condition.
- The `no_data` state and its grace period (§4.4); startup behaviour (§15.3).
- The subject entity and its attribute (§9.5).
- **Stop reloading the entry on subentry changes.** Phase 1 reloads the whole
  config entry whenever an alert is added, edited, or removed. That makes every
  alert briefly `unavailable`, which may confuse automations that depend on them.
  From this phase it would also push condition alerts through `no_data` and
  re-evaluation. Add, update, and remove individual alert entities in place instead.

*Done when* a door-sensor alert and a template alert fire and end correctly,
including through sensor dropouts and restarts.

[Phase 2 as built] Global defaults are set in the integration's options flow:
the no-data grace period and the startup delay. Adding an alert starts with a menu of
kinds, and editing uses the alert's own kind's form; the kind can't be changed.
Editing a condition alert keeps its firing if the new condition still holds, and
otherwise lets `delay_off` run from the edit.

### Phase 3 — Main card (0.3.0)

- `alert-redux-card` (§13.1): sub-cards sorted and coloured by priority, icon, name,
  and on or display message (rendered by the integration); acknowledge control;
  dismiss button where enabled; the no-data section; the empty state.
- Styling after weather_alerts_card (N31).
- **Browser refresh after install or upgrade.** A newly registered or updated card
  resource isn't picked up until the browser does a hard refresh. Until then, the
  dashboard shows "Custom element not found". Look into triggering the refresh
  automatically once the integration is set up (or the card version changes). If
  that isn't possible, tell the user it's needed, e.g. with a persistent
  notification or a README note.

*Done when* the card shows the alerts from phases 1–2 correctly, and acknowledging and
dismissing from the card works.

[Phase 3 as built] Every alert kind gets optional **on message** and **card
message** (display message) templates; the integration renders them for the card
(§9.5, §11.1). The on message is the one phase 4 sends. For the browser refresh:
the frontend loads dashboard resources once per page load and never reloads them,
so the integration can't force a refresh. Instead, it raises a persistent
notification the first time it serves a new card version. The card also asks the
integration for its version (the `alert_redux/info` websocket command), and shows a
**Reload** banner if the two differ. The banner works only from 0.3.0 on, since
older cards don't check. The card's styling was settled on a preview page
(`frontend/dev/preview.html`), which runs the card against a mock `hass`.

### Phase 4 — Notifications I (0.4.0)

- The notifier module (§9.1), supporting all three notifier kinds (§9.2).
- Notifier groups, as subentries with their form (§9.3). The loud/quiet flag is
  stored, but unused until phase 10.
- The default and fallback groups (§9.4); the retry queue (§15.2); a Repairs issue
  for missing legacy actions.
- Messages and their template context (§9.5), reminders (§9.6), the done-notification
  rules except supersession (§9.7).

*Done when* alerts deliver on, reminder, and done notifications to a mobile app, a
notify entity, and persistent notifications, and a missing notifier falls back
correctly.

[Phase 4 as built] Built in two parts: 4a (delivery) and 4b (retries, the
fallback group, and missing-action issues), released together as 0.4.0. The notifier
module is the `notifier/` package; the alert side is `notifications.py`. Every alert
kind has optional reminder and done message templates alongside the on and card
messages, all in a collapsed **Notifications and messages** section of its form.
The choices between "the defaults" and the alert's own setting are three-way (the
default, a list, or an explicitly empty list), so each is a "use the default"
checkbox plus a field: a groups multi-select, and a reminder schedule typed as
minutes (`10, 20, 30, 60`). Legacy action members are edited as a list, each with
its action, `data`, and `target`; the action can be one that isn't registered yet.
The options gain the default groups and reminder schedule, the fallback group, and
the retry timeout. Decisions from building it are recorded in §4.2, §9.2, §9.4–§9.6,
§11.1, §15.1, and §15.2.

### Phase 5 — Condition alerts II and event alerts (0.5.0)

- **On/off** and **threshold** condition kinds (§4.1).
- **Trigger** and **bus event** alerts (§4.2): duration, per-priority default
  durations, firing again while firing. The trigger kind's condition is a template
  (decided in phase 2; §4.2).
- The card's progress bar for event alerts.

*Done when* every alert kind except alert state works end to end.

[Phase 5 as built] Built in two parts: 5a (trigger and bus event alerts, their
shared trigger machinery in `triggers.py`, the per-priority durations, and the
card's progress bar) and 5b (on/off and threshold alerts), released together as
0.5.0. A condition alert's sources, including the extra condition, are reported
together and judged by the kind's own rule, since threshold and on/off answers
depend on whether the alert is firing. The per-priority durations are a collapsed
**Event alert durations** section of the options. The card's bar drains a step per
render, re-rendering every second while one is shown, with a matching transition,
rather than with a CSS animation, which would restart whenever Lit reused an
element for a different alert. Decisions from building it are recorded in §4.1,
§4.2, §9.5, §9.6, §11.1, and §15.3.

### Phase 6 — Snooze, disable, suspend; admin card (0.6.0)

- Snoozing and the snooze-end reminder rule (§6.2); disabling (§6.3); suspending
  (§6.4). Actions and events for each.
- The card's snooze control and countdown, and the disabled-alerts count line.
- `alert-redux-admin-card`, basic version (§13.2): all alerts by priority, with
  enable, disable, and suspend.

*Done when* snoozes, disables, and suspensions behave as specified, across restarts.

[Phase 6 as built] Built in two parts: 6a (snoozing, with the card's snooze
control) and 6b (disabling and suspending, the card's disabled-alerts line, and the
admin card), released together as 0.6.0. Disable, enable, and suspend are made
admin-only with HA's `admin_only` flag on entity actions, which arrived in HA
2026.9; on older versions they're registered as admin actions that dispatch to the
entities in the same way, so the minimum HA version stays 2025.3 (raised to 2026.6 in
phase 12; see Q14). The entities' one-shot timers
share a `PointTimer` helper, and the runtime's deadlines (reminder, snooze,
suspension, event expiry) are synced to them in one place. Decisions from building
it are recorded in §6.1–§6.4, §7.2, §9.5, §11.1, §11.3, §12.1, §13.1, §13.2, §16,
and §20.

### Phase 7 — Supersession (0.7.0)

- Supersession: transitive, with debounce (§8.1); the done window (§9.7).
- Propagation (None, Acknowledge, Snooze), pre-acknowledgement and pre-snoozing
  (§8.2, §8.3).
- The **alert state** condition kind (§4.1).
- Dangling references: fail-safe behaviour, Repairs issues, `broken_references`, the
  delete warning (§12.4).
- The card's collapsed superseded alerts.

*Done when* the *Door Open* / *Door Left Open* and workshop examples behave exactly as
the spec describes.

[Phase 7 as built] Built in two parts: 7a (supersession with its debounce and
done window, the alert state kind, and the card's superseded alerts) and 7b
(propagation, pre-acknowledgement and pre-snoozing, and dangling references),
released together as 0.7.0. Supersession lives in `supersession.py`: a graph of
the relationships, and a coordinator the alerts share, which each alert tells
when it starts or stops firing, or gains or loses its acknowledgement. Alerts
refer to each other by entity ID, following renames; the delete warning became
a list of referrers in the edit form, since HA offers no hook into the delete
dialog. Decisions from building it are recorded in §4.1, §8.1–§8.3, §9.7,
§11.1, §11.3, §12.1, §12.4, and §13.1.

### Phase 8 — Summary sensors and logbook (0.8.0)

- The summary sensors (§11.2), including the diagnostic disabled count.
- The logbook platform (§11.4).
- A pass over the event set and its data (§11.3), plus the ready-to-paste list of
  event types.

*Done when* the signal-light glue can be written as a single-entity automation, and
the Activity card reads well.

[Phase 8 as built] The summary sensors are a sensor platform reading a summary
the alerts report to as they write their state (`summary.py`). The logbook
platform describes only the events that add to the state rows, since the
logbook already shows each state change with its user; the review of the event
set added `_data_restored`. Decisions from building it are recorded in §11.2,
§11.3, and §11.4.

### Phase 9 — Notifications II: replacing, clearing, buttons (0.9.0)

- Replacing and clearing (§9.10).
- Built-in and custom buttons, tap handling, and require unlock (§9.11).

*Done when* a mobile notification updates in place, clears when acknowledged, and
"Close door" works from the phone.

[Phase 9 as built] Built in two parts: 9a (replacing and clearing) and 9b
(buttons), released together as 0.9.0. The notifier keeps live records of which
members show each alert's notification, so clears reach exactly those, and new
notifications and clears drop retries they replace. Button taps are handled in
`buttons.py`. Decisions from building it are recorded in §9.1, §9.3, §9.10,
§9.11, §11.1, and §12.1.

### Phase 10 — Throttling and quiet hours (0.10.0)

- Throttling, including held done notifications and the throttling summaries (§9.8).
- Quiet hours: the entity, per-group overrides, threshold, hold and soften, and the
  end-of-quiet-hours reminder and summary (§9.9).

*Done when* a night with quiet hours on produces exactly the specified morning
summary.

[Phase 10 as built] Built in two parts: 10a (throttling) and 10b (quiet hours),
released together as 0.10.0. Throttling is the alert's, kept with its stored
state; it follows Alert2 in counting held notifications. Quiet hours are the
notifier's, deciding by a generic urgency, and hand what's held back to Alert
Redux when they end, which sends one reminder per active alert and one summary
per group. Decisions from building it are recorded in §9.1, §9.3, §9.5, §9.8,
§9.9, §11.1, §12.1, and §15.2.

### Phase 11 — Generators (0.11.0)

- Generator subentries and entities; target selection; dynamic creation and removal
  (§12.3).
- Generated supersession; the `refresh_generator` action.

*Done when* one generator covers every door lock, including a lock added later.

[Phase 11 as built] Built in two parts: 11a (generators) and 11b (generated
supersession, and the admin card's "generated" marker), released together as
0.11.0. Generators make condition alerts only, and match targets AND across the
criteria and OR within each. Alert entities are now built from an
`AlertDefinition`, which a generator makes per target, adding the `target` and
`target_name` template variables. Removals wait for a startup grace period, so
slow integrations don't make alerts flap. Decisions from building it are
recorded in §9.5, §11.1, §12.1, §12.3, §13.2, and §16.

### Minor fixes (0.11.1)

Small issues that don't belong to a phase, gathered between phases 11 and 12.
Live testing waits for the next real-HA run.

- Capitalise the logbook messages, to match the translated states (§11.4).
- Add the snooze durations to the main card's visual editor (§13.1).
- Rename the notification button Snooze to Snooze Alert, to tell it apart from
  the HA app's own snooze options (§9.11; moved from phase 13).
- Hold a superseded alert's reminder for a superseding alert about to fire, so
  the two don't arrive together (§8.1).
- The admin card marks firing alerts that are currently superseded (§13.2;
  moved from phase 13).
- The README gains screenshots of the cards, and a section thanking the authors
  of [Alert2](https://github.com/redstone99/hass-alert2) and
  [weather_alerts_card](https://github.com/seevee/weather_alerts_card) for their
  inspiration (moved from phase 13).

### 1.0.0 — Manual alerts that end by themselves, and a tidier alert entity

- The *End by itself after* option for manual alerts (§4.3). The duration handling
  moves out of the event alerts into a part both kinds share: the expiry timer,
  restoring the expiry after a restart, gating reminders, and the attributes.
- The option and its duration on the manual alert form.
- A refactor of the alert entity, with no change in behaviour: manual alerts get
  their own class, leaving the shared base class with only what every kind uses;
  manual and event alerts share one path for starting a firing; and the alert
  state kind's watched alert moves to the condition alerts.
- Found in the restart checks: a duration that ran out while HA was down ends
  just after the alert's first state is written, so the logbook shows it
  (§11.4, §15.1).
- The edit forms' warning about broken references appears only when something
  refers to the alert or generator.
- [Decided, 1.0.0] **An agent skill**, shipped in this repository
  (`plugins/alert-redux/`): how-tos and best practices for agents that
  configure, operate, and build on Alert Redux, e.g. through an MCP server. It's
  written in terms of Home Assistant itself (subentry flows, actions, events),
  with the HA-MCP server's tool names and quirks in a file of their own. It
  follows the [Agent Skills](https://agentskills.io) format, so any agent that
  supports it can use the folder, and the repository is also a Claude Code
  plugin marketplace that lists it. The plugin's version follows the
  integration's. A test checks the skill against the code (every action, event,
  attribute, form field, error, Repairs issue, and card option), so it can't
  silently go stale. Until HA-MCP can offer skills that custom integrations
  provide (raised with its maintainers), shipping it here is how agents get it.

Planned as 1.1.0, to leave the daily-use soak of 0.11.1 undisturbed. The soak
found only trivia, and a 1.0.0 identical to 0.11.1 would add nothing, so this
became 1.0.0 instead [Decided]. As it wasn't part of that soak, it gets a
shorter soak of its own on the real instance before release.

### Phase 12 — Voice control (1.1.0)

- **First, a spike** in real HA: a conversation trigger attached by the
  integration, whose action's reply is spoken, through both the built-in agent
  and an LLM agent's pipeline. Everything else in §14.1 rests on it.
- Assist (§14.1): the four intents (acknowledge, unacknowledge, snooze, and the
  firing-alerts query); the English sentence triggers; the `llm.py` tools; name
  matching, commands with no name, and spoken durations; each alert exposed to
  Assist once; and the README's notes on custom sentences and Speech-to-Phrase.
- Proxies (§14.2): the optional per-alert proxy switch and snooze button, their
  options in the alert and generator forms, and their exposure (Alexa and Google
  once, hidden from Assist once); the real-HA checks listed in §14.2.
- The paths only older HA takes (LLM tools before 2026.8, the `admin_only`
  fallback before 2026.9) tested locally against an older HA, apart from CI (Q14).
- Testing notes: `conversation` and `llm` go in `after_dependencies`, not
  `dependencies`. Tests that load `conversation` need the core `homeassistant`
  component set up first, and a pinned HA's matching `hassil` and intents
  packages.

*Done when* acknowledging, unacknowledging, snoozing, and the query work by
voice through a pipeline with an LLM agent and through the built-in agent, an
LLM agent can use the tools on its own, and the proxies work with Alexa and
Google Home.

It was planned as 0.12.0, before 1.0.0 came first; it's now 1.1.0 [Decided].

[Phase 12 as built] Built in two parts: 12a (Assist, after a spike that showed
an integration's conversation trigger speaking its reply through both the
built-in agent and a Claude pipeline) and 12b (the proxies), released together
as 1.1.0. The intents and sentences are `voice.py`, the matching and replies
`speech.py`, the LLM tools `llm.py`, and the proxies `proxies.py`, `switch.py`,
and `button.py`. Exposing once is `exposure.py`, recorded in the alert's stored
record beside the label. The real-HA run changed the replies (a long ambiguity
asks for more of the name; courtesy words are ignored), found the snooze
duration needed passing as seconds so the recorded action call can be stored,
and confirmed the Alexa phrases and routine; Google Home is unverified. Testing
against older HA raised the minimum to 2026.6 (Q14), and found the `llm`
platform arrived in 2026.8. Decisions from building it are recorded in §14.1,
§14.2, §18, and §19.

### Phase 13 — Late features (1.2.0)

- Card filters: scope by area and label in the card's configuration, and
  hide-acknowledged and per-priority controls on the card (§13.1).
- Paging for the admin card (§13.2).
- Custom notification buttons on the main card, and the `alert_redux.press_button`
  action (§13.1, §16).
- Creating and editing alerts from the admin card (§13.2).
- The export and import actions (§16; implemented) and their admin-card controls (§13.2).
- The admin card shows a copyable summary of an alert's settings on request
  (§13.2).
- iOS interruption levels for Emergency and Critical alerts (§9.3).
- Setting an alert's area and labels in its configuration form, when it's created
  or edited, with the registry as where they live; and for generators, labels and
  a fixed area or the target's area (§11.6).

[Phase 13 as built] Built feature by feature, and released together as 1.2.0. The
export and import actions are `portable.py`, over the checks the forms share in
`validation.py`; the admin card gained paging, summary, export and import (YAML),
and add, edit, and delete through the subentry flows (`flow-client.ts`,
`flow-dialog.ts`); the main card gained custom buttons and filters; area and labels
are `placement.py`. Off the plan: the summary sensors leave superseded alerts out of
the unacknowledged figures and gain `sensor.alert_redux_superseded` (§11.2). Dropped
or moved: the acknowledgement queue became latching alerts, phase 15 (§10), and
displayed state names in state alerts (N38) were dropped (§4.1). Decisions from
building it are recorded in §4.1, §8.1, §9.3, §9.11, §11.2, §11.6, §12.1, §13.1, §13.2,
and §16.

### Phase 14 — Converter utilities (1.2.1)

- Standalone tools in this repository, not shipped in the integration, that
  convert into an import file (§17):
  - an `alert:` YAML section from the built-in `alert` integration;
  - Alert2 alerts.

[Phase 14 as built] Two scripts in `tools/`, `convert_alert.py` and
`convert_alert2.py`, over `_convert_common.py` (stdlib and PyYAML; Home Assistant
isn't needed). They write the §16 file without `id`s, so a converted file matches
existing alerts by name, and print a report (what was converted, skipped, or
approximated, and the notifier groups to create). Decided in building:

- **Input shapes.** The built-in tool takes the `alert:` section or a whole
  configuration; the Alert2 tool takes an `alert2:` block (with `defaults:`), a
  single alert's YAML as the Alert Manager card shows it, or a list of alerts.
- **Notifiers** become groups of the same name, or as a `--group-map` file says
  (a value may be a name, a list, or empty to drop); groups can't be in an import
  file, so the report lists those to create.
- **Kinds.** Built-in alerts are all state alerts. Alert2's `condition` is a
  state alert (an entity) or a template alert; `condition_on`/`_off` and
  `trigger_on`/`_off` are on/off alerts; `trigger` a trigger alert; `threshold` a
  threshold alert; an event alert with none of them (reported with `alert2.report`)
  a manual alert that ends by itself. Priorities low, medium, high are notice,
  warning, critical (Alert2's default is low). Alert2's template variables
  `on_time_str` and `on_secs` become `duration` and `duration_seconds`.
- **Naming** [Decided with the user]. An Alert2 alert is named by a plain
  `friendly_name`, else by its `domain` and `name` together ("House Door open"):
  `name` alone is cryptic and clashes across domains. Shared friendly names get
  the domain in front.
- **`skip_first`** [Decided with the user]. The built-in `alert`'s has no exact
  equivalent. `--skip-first-as-delay` turns it into a `delay_on` of the first
  `repeat` interval, which is what people moving to Alert2 usually do though the
  behaviour differs; without the option it's a warning.
- **Generators** [Decided with the user]. Not converted, but the report gives the
  settings of an Alert Redux generator that match the body (kind, messages,
  priority, delays, reminders, groups; `genElem` becomes `target`), with a
  `targets` placeholder and Alert2's list or template quoted, as a head start.
- **Checked on a live instance** (a dry-run import of the Alert2 documentation's
  alerts, with notifiers mapped onto the instance's existing groups): all accepted,
  nothing created. Without the map the same file was refused for its unknown
  groups, which is why the migration guide (`tools/README.md`) has the user map or
  create groups first, and dry-run before importing.
- **Template conditions that only compare one entity's state** (`{{ states('x') ==
  'v' }}`, `{{ is_state('x', 'v') }}`) become state alerts, which report missing
  data precisely (§4.1); Alert2's own migration example is one. Any other
  template stays a template alert.
- **Tested on the documentation's own examples** (the built-in `alert` page, and
  Alert2's README and Recipes), kept as fixtures. They showed what the forms of
  real configurations need: a `clear_notification` done message isn't text;
  notifiers can be templates or entities (dropped, leaving the default groups,
  never "nobody"); `condition: true` is a YAML boolean; on/off alerts need both
  sides, so Alert2's on-only alerts (`manual_off`) become template alerts;
  domains and names can hold spaces and capitals (entity IDs are slugged for
  supersession); and generators' selections can often be read for their domain and
  an entity ID glob.
- **Not converted**, and reported: `skip_first` (without the option), titles,
  notifier `data` and `target`, `ack_required` (converted since phase 15), `done_notifier:
  false`, `early_start`, and the other options with no equivalent. `--strict` makes
  any of them an error.
- A test runs each fixture's output through the import action's `dry_run`.

### Phase 15 — Latching alerts (1.3.0)

[Decided; provisional, until the rest of the list is done] Last, because it changes
the alert lifecycle (§7).

- Latching alerts (§10): the *keep until acknowledged* setting, the state or flag
  for an alert whose firing ended unacknowledged, its place on the main card (with
  the fire count shown when it's more than one), acknowledging it by every route
  that acknowledges an alert, and what it does to reminders, notifications, the
  summary sensors, and supersession.
- [Decided; with phase 14] Go back to the Alert2 converter (`tools/convert_alert2.py`)
  and convert `ack_required` (and `ack_reminders_only`) to the latching setting,
  which is its equivalent, instead of dropping it with a warning; update
  `tools/README.md` and the converter's tests with it.

[Phase 15 as built] The design is recorded in §10, with the user's choices
marked: a `latched` state; latched alerts count as unacknowledged; snoozing one
puts its reminders off; a dismissal latches only without a user. The runtime
(`model.py`) keeps the latch and the item's start (`latch_anchor`), and its
`end`, `ack`, `snooze`, and `plan_reminder` handle it; `supersession.py` passes
an acknowledgement on between latched alerts; the card lists latched alerts with
the firing ones. The converter turns `ack_required` into `latching`. Correcting
the item above: `ack_reminders_only` isn't latching. In Alert2 it only keeps an
acknowledged alert's done notification, which Alert Redux always sends (§9.7),
so it needs nothing.

**Versions from 1.0.0** [Decided]: a phase that adds integration features is a minor
release, so phase 12 is 1.1.0, phase 13 1.2.0, and phase 15 1.3.0. Phase 14 ships
tools that aren't part of the integration, so it doesn't bump the minor version: the
release cut after it is 1.2.1. (Phases 13 and 14 are done in order, so 1.2.1 follows
1.2.0; phase 15 follows as 1.3.0.)

**1.0.0** comes after phase 11, once the core feature set is proven in daily use,
with phases 12–15 as 1.x releases [Decided, provisionally]. It adds self-ending
manual alerts and the entity refactor to 0.11.1 (above).
