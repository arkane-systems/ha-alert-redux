# Alert Redux — Specification

**Status:** draft 2. All sections reviewed, except the notifier model (Q1), quiet
hours (Q2), and the items listed in §18. Built from the notes in
[spec-notes.md](spec-notes.md); IDs in brackets (N7, R2, F12, …) refer to that file.

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
| **State** | One entity plus a target state, e.g. `binary_sensor.leak` is `on`. The simple case, equivalent to the built-in `alert`. |
| **On/off** | Separate *on* and *off* criteria, each a condition and/or trigger. Turns on when the on criterion becomes true, and off when the off criterion becomes true (edge-triggered, as in Alert2). |
| **Threshold** | A numeric value (from an entity, attribute, or template) with a minimum and/or maximum, and hysteresis. The limits can themselves come from entities or templates [P18]. |
| **Template** | A template that evaluates to true or false. The fully general option. |
| **Alert state** | [Decided, F24] Fires when another alert has been in a given state (e.g. `active`, meaning unacknowledged) for a given time. This gives escalation without templates (§8.4). |

All condition alerts support:

- **`delay_on`** [Decided, N5]: the condition must hold continuously for this long
  before the alert fires.
- **`delay_off`** [Decided, F9, F12]: the condition must be false continuously for
  this long before the alert stops firing. This absorbs flicker at the *state* level.
  Otherwise a momentary drop would end the firing, which clears its acknowledgement
  (§6.1) and sends a done notification.
- An optional extra **condition** combined (AND) with the main criterion (threshold
  kind in particular) [P18].

### 4.2 Event alerts

An event alert fires on a momentary occurrence and then stays firing for a set
**duration** [Decided, N4]. It can't be fired or dismissed manually; it ends when the
duration runs out [Decided, R2, R3].

| Kind | Configuration |
|---|---|
| **Trigger** | Any HA trigger, plus an optional condition that must be true when the trigger fires [Decided, R2, P16]. |
| **Bus event** | An event type on the HA event bus, plus an optional filter on the event data [Decided, R2]. |

- **Duration** comes from the alert's own setting, or else from its priority's default
  (§5) [Decided, N4].
- **Firing again while still firing** [Decided, F2]: restarts the duration from the
  new event, adds one to the fire count, and updates the message context. It
  **doesn't** clear an acknowledgement. The alert is still the same firing, so an
  event that repeats frequently doesn't cause repeated nagging. The fire-again
  notification is subject to throttling (§9.6).
- The card shows a draining progress bar for the remaining duration (§13.1).
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

### 4.4 Missing data

When an entity or template that an alert depends on is `unavailable` or `unknown`, or
won't parse (e.g. a non-numeric threshold value), the alert goes into its
**no-data** state instead of raising an error [Decided, N7].

- [Decided] If the alert was firing, it keeps its firing state and acknowledgement
  while it waits for data, until a grace period runs out. That way a sensor briefly
  dropping out doesn't end the firing and trigger done and "on" notifications. The
  grace period is set per alert, with a global default.
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
- which alerts quiet hours apply to (§9.7) [Decided, R9].

[Decided, F4] Priority does **not** set default notifiers or reminder schedules.
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

### 6.4 Suspending

[Decided, N22, F16] Suspending disables an alert until a given time, or for
a given duration, after which it re-enables automatically as in §6.3. The name
*suspend* keeps it clearly separate from *disable* and *snooze*.

[Decided, F16] As with snoozing, there's no separate state: a suspended alert is
`disabled` with a `disabled_until` attribute.

## 7. States and lifecycle

### 7.1 States

[Decided, N8, F1]

| State | Meaning |
|---|---|
| `idle` | Enabled and has data, but not firing. |
| `active` | Firing and not acknowledged. |
| `ack` | Firing and acknowledged (or snoozed; see `snoozed_until`). |
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

   any enabled state ── inputs missing ──▶ no_data ── inputs return ──▶ re-evaluate
   any state ── disable / suspend ──▶ disabled ── enable / suspension ends ──▶ no_data
```

(While in `no_data`, a firing alert keeps its firing/ack status for the grace period;
see §4.4.)

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
  stop firing before the alert that supersedes it; that's fine.
- [Decided] While the superseding alert is firing, the superseded alert sends no on
  or reminder notifications. Its **done** notification follows §9.5: it's dropped
  only if both alerts stop firing together.
- [Decided, F7] On the main card, superseded alerts are **hidden behind a
  disclosure toggle** under the alert that supersedes them, e.g. "▸ 1 superseded
  alert", and collapsed by default. Alerts that are implied by another alert then
  don't clutter the card (§13.1).
- Supersession cycles (A ⊃ B ⊃ A) are a configuration error.

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
- [Decided] Its done notification is still sent (§9.5). In the workshop example,
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
- The done notification follows in due course, as always (§9.5).

### 8.4 Escalation and delayed notification

These are done with supersession, not as separate features [Decided, R8, R11]:

- **Escalation:** a superseding alert with a longer `delay_on`, a higher priority, or
  different notifiers. To escalate only when nobody has acknowledged, use the **alert
  state** condition kind (§4.1) against the superseded alert.
- **Delayed first notification** (the built-in `skip_first`): a first alert with an
  empty notifier list shows up on the card at once, and a superseding alert with a
  `delay_on` sends the notification.

## 9. Notifications

### 9.1 Notifiers

- Each alert has a list of notifiers, or else uses the global default list. An
  explicitly **empty** list means "notify nobody" [Decided, N15, F26].
- Separate notifiers for the on, reminder, and done notifications: **not** planned
  [Decided, R10].
- Notifier lists chosen by template or entity: not planned for now, but nothing in
  the design should rule it out [Decided, R13].
- **Which kind of notifier to support (`notify.*` entities vs. legacy
  `notify.<name>` actions), and whether to pass through `data`, `target`, tags,
  clearing, and actionable buttons: [Deferred, R1, F8]** for a separate discussion.
  §9.1–§9.6 are written so that either answer fits.

### 9.2 Fallback notifier

[Decided, R6, F26] A global fallback notifier (default:
`persistent_notification`) receives a notification when *all* of an alert's
notifiers are missing or fail, after the retry queue (§15.2) gives up. It isn't used
for alerts with an explicitly empty notifier list.

### 9.3 Messages

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
  - the reason for the notification (`on`, `reminder`, or `done`).
- [Decided] The default wording is deliberately generic. It's a starting point,
  meant to be overridden with something more specific.
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
- [Decided, F22] The card shows the **on** message by default. An optional separate
  **display** message can be set for the card.

### 9.4 Reminders

- Each alert has a reminder schedule, or else uses the global default [Decided, N16].
- A schedule is a list of intervals, e.g. `[15, 30, 60]`: the gaps follow the list,
  and the last value repeats [Decided, R12]. An empty list means no reminders.
- Reminders are sent only while the alert is `active`.
- [Decided] Event alerts send reminders only if their duration is longer than the
  first reminder interval. Short event alerts just fire and expire.

### 9.5 The done notification

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
- [Open] **Done notifications while throttling is active.** Throttling holds back on
  notifications (§9.6). If every flicker still sends a done notification, a
  flickering alert produces a stream of done notifications, which defeats the point
  of throttling. Suggested: while an alert is throttled, its done notifications are
  held too, and when throttling ends, one done notification (or the throttling
  summary) is sent if the alert is no longer firing.
- [Open] **Done notifications during quiet hours:** sent immediately, or held and
  included in the quiet-hours summary? This is part of the quiet-hours design (§9.7).

### 9.6 Throttling

[Decided, N18, F9]

- Throttling applies to **notifications** only; state never flickers because of it.
  (Flicker at the state level is handled by `delay_off`, §4.1.)
- Format: `[count, minutes]` — at most *count* on notifications in any *minutes*
  window. Set per alert, or else from the global default (default: no throttling).
- It doesn't affect reminders.
- Throttling summaries ("[Throttling starts]" / "fired 10× in this period") are part
  of the feature [Decided, R14].

### 9.7 Quiet hours

[Decided, R9; design Open] Quiet hours hold back notifications for alerts below a
chosen priority (e.g. below Warning) during a schedule.

- [Decided-ish, R9] When quiet hours end, alerts still firing notify again, and alerts
  that fired and stopped during quiet hours are sent as a summary. The summary could
  share its mechanism with the acknowledgement queue (§10).
- [Open, R9] Should quiet hours be set per notifier (a silent text at night is fine;
  a loud announcement isn't), per priority, or both? How does this interact with the
  notifier decisions in R1?

## 10. Acknowledgement queue

[Deferred, R7] A late phase adds a separate "needs acknowledgement" system. When an
alert stops firing without being acknowledged, it's handed off to this queue. Several
unacknowledged firings produce several separate items to acknowledge. The quiet-hours
summary (§9.7) may use the same mechanism. The details are to be designed when it's
built.

## 11. Integration surface: attributes, sensors, events

### 11.1 Alert entity attributes

[Decided, N1] Every alert entity has, at minimum:

- **State details:** `kind`, `priority`, `firing_since`, `last_fired`, `last_ended`,
  `fire_count` (current firing), `event_expires` (event alerts), `snoozed_until`,
  `disabled_until`, `pre_acked_by`, `superseded_by`, `no_data_since`, the input
  entities that are missing data, and the time and user of the last acknowledge,
  snooze, disable, or enable [Decided, R18].
- **Configuration:** `acknowledgeable`, `supersedes`, `notifiers`,
  `reminder_schedule`, `throttle`, `delay_on`/`delay_off`, `duration`, the source
  entity or entities, and the on message (rendered).
- **Generator provenance:** `generated_by` (§12.3).

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

### 11.3 Events

[Decided, N2, R17] Every change fires its own HA event, with the common prefix
`alert_redux_`: `alert_redux_fired`, `…_ended`, `…_acked`, `…_unacked`,
`…_snoozed`, `…_snooze_expired`, `…_disabled`, `…_enabled`, `…_no_data`,
`…_superseded`, `…_created`, `…_deleted`. Every event carries `entity_id`, `name`,
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
  `_acked`, and the `_acked` data carries `pre_acked_by`.

### 11.4 Logbook / Activity

[Decided, N24, R18, F18]

- Entity states are translated (`ack` → "Acknowledged", `no_data` → "No data", …)
  through `translation_key`.
- A logbook platform describes Alert Redux events in readable text, including who did
  what, e.g. "Back Door Open acknowledged by Alistair". This is what lets a standard
  Activity card stand in for Alert2's history view.

## 12. Configuration

### 12.1 Structure

[Decided, R21, F27]

- One integration config entry (already in place) holds the **global defaults**:
  notifiers, fallback notifier, reminder schedule, throttle, the per-priority event
  durations and icons, quiet hours, and the no-data grace period. They're edited
  through its options flow.
- Each **alert** is a **config subentry** of that entry, created and edited in the
  UI (and, later, from the admin card, §13.2).
- Each **generator** is also a subentry (§12.3).
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
- Superseded alerts are hidden behind a collapsed disclosure toggle under the alert
  that supersedes them [Decided, F7, §8.1].
- A **no-data section** at the bottom lists alerts that currently lack data.
- **Empty state:** the card always shows, with a small grey "No alerts are firing"
  when there's nothing to show.
- [Decided, F22] Disabled and suspended alerts aren't shown on the main card; they
  appear on the admin card only. The main card shows a one-line count instead, e.g.
  "3 alerts disabled".
- Filters (hide acknowledged; per priority) [Decided, R22, late phase].
- Styling follows [weather_alerts_card](https://github.com/seevee/weather_alerts_card)
  [Decided, N31].

### 13.2 Admin card (`alert-redux-admin-card`)

[Decided, N30]

- Lists **all** alerts grouped by priority, showing each one's state.
- Controls to enable, disable, and suspend each alert.
- Later phase: create and edit alerts and generators from the card, making it a
  friendlier front end to the subentry flows.
- [Decided, F27; late phase] Export/import of alert definitions, to make up for
  losing YAML's version control and text editing. Also available as actions (§16).

## 14. Voice control

[Decided, N23, F17; late phase]

- **Assist:** the integration registers its own voice commands for acknowledging,
  removing an acknowledgement, and snoozing (with a duration), matching alerts by
  name. For example: "acknowledge the back door alert", "snooze the server room
  alert for 30 minutes". No extra entities are needed.
- **Alexa (and other limited assistants):** each alert can optionally expose a
  **proxy switch**: turning it on acknowledges the alert, and turning it off removes
  the acknowledgement. Optionally, a second switch per alert, or a per-alert setting,
  gives a fixed-duration snooze. The switches are opt-in per alert so that entities
  aren't doubled across the board.
- The design must allow for this from the start: anything the card can do must also
  be available as an action, and alerts need names that make sense when spoken.
- [Decided, to verify] The limited-assistant solution must also work with **Google
  Assistant / Google Home**, not just Alexa. Proxy switches should work there too,
  through HA's Google Assistant integration (Nabu Casa or manual), but this needs
  checking when the phase is built.

## 15. Startup, resilience, persistence

### 15.1 Restoring state

[Decided, F21] Alert Redux restores its state across restarts: firing status,
acknowledgement, snooze timer, disabled/suspended status and time, event-alert
expiry, pre-acknowledgements, throttle counters, and the reminder schedule position.
This uses `RestoreEntity` together with a `Store`, saved whenever something important
changes, rather than relying only on HA's 15-minute periodic save.

After a restart:

- An alert that was firing and still is resumes quietly: **no** new on notification
  [Decided, R16 response].
- An alert that was firing and no longer is ends normally, with a done notification.
- A snooze or suspension that ran out during the restart ends as soon as HA is back.

### 15.2 Notifier retry queue

[Decided, R16 response]

- If a notifier doesn't exist yet or fails, the notification is queued and retried
  with backoff, up to a timeout (default a few minutes, configurable).
- After the timeout, the fallback notifier is used (§9.2), and the failure is logged.
- This applies all the time, not just at startup, so it also covers integrations
  restarting while HA is running.

### 15.3 Startup order

- Alerts start in `no_data` and evaluate as soon as their inputs report data
  [Decided, N33]. There's no `early_start` [Decided, R16].
- An optional startup grace period (global setting) delays the first evaluation.
- Integrations or entities that disappear and come back are handled by the no-data
  mechanism (§4.4).

### 15.4 Logging

[Decided, R6] Alert Redux's own problems are logged; there are no internal alerts.

## 16. Actions

[Decided] All actions target alert entities in the standard way (`entity_id`,
area, label, …):

| Action | Purpose |
|---|---|
| `alert_redux.ack` / `alert_redux.unack` | Acknowledge, or remove the acknowledgement. |
| `alert_redux.snooze` | Snooze for a `duration`. |
| `alert_redux.disable` / `alert_redux.enable` | Disable or enable. |
| `alert_redux.suspend` | Suspend for a `duration`, or `until` a time. |
| `alert_redux.fire` / `alert_redux.dismiss` | Fire or dismiss a manual alert; `fire` can take `data`. |
| `alert_redux.refresh_generator` | Re-evaluate a generator's targets now (debugging; §12.3). |
| `alert_redux.export` / `alert_redux.import` | Export or import alert and generator definitions; `import` takes `overwrite` (default off). |

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
- [Decided] Import is an **admin-only** action, since it changes configuration.
  Export is available to everyone, like reading any other entity data.
- There's no `alert_redux.delete` action for now. It can be added later if a use
  appears.

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
- Separate notifiers for the on, reminder, and done notifications [R10].
- Notifier lists from a template or entity [R13] (for now; not ruled out).
- Migration code for the built-in `alert` inside the integration [F28]. Instead, a
  separate converter utility in this repository (not shipped in the integration)
  reads an `alert:` YAML section and writes a file for `alert_redux.import`.

## 18. Open questions

| # | Question | Refs |
|---|---|---|
| Q1 | Notifier model: `notify.*` entities, legacy actions, or both; `data`/`target` passthrough; mobile tag replacement, clearing, actionable buttons. | R1, F8, P1–P3, P8 |
| Q2 | Quiet-hours design: per notifier, per priority, or both; how the summary is delivered. | R9, §9.7 |
| ~~Q3~~ | ~~Should propagation optionally snooze?~~ Resolved: yes (§8.2). | N13 |
| ~~Q4~~ | ~~Generator details~~ Resolved: supersession can be generated; generators are entities (§12.3). | F20 |
| ~~Q5~~ | ~~Export/import~~ Resolved: yes, in the admin card, late phase (§13.2). | F27 |
| ~~Q6~~ | ~~Migration from built-in `alert:`~~ Resolved: no code in the integration; a separate converter utility that produces import files, late phase (§17, §20). | F28 |
| ~~Q7~~ | ~~One event per change, or one combined event?~~ Resolved: separate events (§11.3). | §11.3 |
| ~~Q8~~ | ~~Review the remaining proposals~~ Resolved: all approved. | — |
| ~~Q9~~ | ~~Dangling references~~ Resolved: fail-safe behaviour, with Repairs issues (§12.4). | §12.4 |
| ~~Q10~~ | ~~Create/edit/delete by action?~~ Resolved: export/import actions, with overwrite protection (§16). | §16 |

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
| `subject_entity_name` (subject entity) in message templates | Generated alerts can share one message template without deriving names from the alert name [§9.3]. |
| Export/import actions instead of create/edit actions; import won't overwrite without a flag | One validation path; protects existing definitions from accidental replacement [Q10]. |
| Separate events per change, with a common prefix | Easy to filter; list-based event triggers cover listening for several [§11.3]. |
| Paired events when one change implies another | Snooze and ack don't always move together, so firing both gives the most information [§11.3]. |
| Per-priority counts as attributes, not sensors | Avoids multiplying entities [§11.2]. |
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

## 20. Phase plan

To be written once §18 is resolved. Rough shape, for discussion:

1. Core alert entity: states, attributes, restore; manual alerts; ack/unack; actions.
2. Condition alerts (state, template), `delay_on`/`delay_off`, no data.
3. Notifications: notifiers, fallback, messages, reminders, retry queue.
4. Main card, basic version.
5. Remaining condition kinds (on/off, threshold, alert state); event alerts; card
   progress bar.
6. Snooze, disable, suspend; admin card, basic version.
7. Supersession, propagation, pre-acknowledgement.
8. Summary sensors, events, logbook.
9. Throttling, quiet hours.
10. Generators.
11. Voice control.
12. Acknowledgement queue; card filters; admin-card editing; export/import.
13. Converter utility from built-in `alert:` YAML to import files.
