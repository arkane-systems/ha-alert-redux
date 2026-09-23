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
  notification is subject to throttling (§9.8).
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
  or reminder notifications. Its **done** notification follows §9.7: it's dropped
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
  | Quiet-hours `data` | Legacy action | Alternative `data` used when the group *softens* during quiet hours (§9.9). |

- **Loud or quiet** [Decided, N35]. Only you know which notifiers make noise, and
  integrations can't tell us (N34: `notify_mqtt` can't even know who's listening).
  So every group is flagged:
  - **quiet**, e.g. a text message: delivered at any time;
  - **loud**, e.g. a speaker announcement: quiet hours apply (§9.9).

  A group holding both kinds of destination should be split into two groups, and an
  alert can use both.
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

### 9.6 Reminders

- Each alert has a reminder schedule, or else uses the global default [Decided, N16].
- A schedule is a list of intervals, e.g. `[15, 30, 60]`: the gaps follow the list,
  and the last value repeats [Decided, R12]. An empty list means no reminders.
- Reminders are sent only while the alert is `active`.
- [Decided] Event alerts send reminders only if their duration is longer than the
  first reminder interval. Short event alerts just fire and expire.

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
- [Decided] **Done notifications are throttled too.** While an alert is throttled, its
  done notifications are held along with its on notifications. The throttling
  summary sent when throttling ends (§9.8) covers what happened. Throttling is
  expected to be exceptional, and usually means someone goes to the console for
  details anyway; revisit if it proves a problem.
- [Decided] **Done notifications during quiet hours** for affected alerts on loud
  groups are held and folded into the end-of-quiet-hours summary (§9.9).

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
- [Deferred, R7] The summary may later be delivered through the acknowledgement
  queue (§10) instead.

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

### 9.11 Buttons

[Decided, N37, P3] Alerts can put buttons on notifications, and members that support
buttons show them. Currently that means legacy mobile members; Telegram inline
keyboards could be added later. Other members leave the buttons out.

- **Custom buttons** [Decided, N37]: each alert can define buttons, each with a
  label and the HA action it runs. For example, *Garage Door Left Open* has "Close
  door", which runs `cover.close_cover` on `cover.garage_door`. The definition says
  nothing about mobile; the member converts it into its own format.
- **Built-in buttons** [Decided, P3]: **Acknowledge**, and **Snooze** for a fixed
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

## 10. Acknowledgement queue

[Deferred, R7] A late phase adds a separate "needs acknowledgement" system. When an
alert stops firing without being acknowledged, it's handed off to this queue. Several
unacknowledged firings produce several separate items to acknowledge. The quiet-hours
summary (§9.9) may use the same mechanism. The details are to be designed when it's
built.

## 11. Integration surface: attributes, sensors, events

### 11.1 Alert entity attributes

[Decided, N1] Every alert entity has, at minimum:

- **State details:** `kind`, `priority`, `firing_since`, `last_fired`, `last_ended`,
  `fire_count` (current firing), `event_expires` (event alerts), `snoozed_until`,
  `disabled_until`, `pre_acked_by`, `superseded_by`, `no_data_since`, the input
  entities that are missing data, and the time and user of the last acknowledge,
  snooze, disable, or enable [Decided, R18].
- **Configuration:** `acknowledgeable`, `supersedes`, `notifier_groups`, `buttons`,
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
  the default and fallback notifier groups, reminder schedule, throttle, snooze
  duration for notification buttons, the per-priority event durations and icons, the
  quiet-hours entity and priority threshold, and the no-data grace period. They're
  edited through its options flow.
- Each **alert** is a **config subentry** of that entry, created and edited in the
  UI (and, later, from the admin card, §13.2).
- Each **generator** is also a subentry (§12.3).
- Each **notifier group** is also a subentry (§9.3).
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

- If a group member doesn't exist yet or fails, the notification to that member is
  queued and retried with backoff, up to a timeout (default a few minutes,
  configurable). Retries are per member, so one broken member doesn't hold up the
  rest of its group.
- After the timeout, the failure is logged. If no member of any target group
  received the notification, it goes to the fallback group (§9.4).
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
- Separate notifier groups for the on, reminder, and done notifications [R10].
- Notifier groups chosen by template or entity [R13] (for now; not ruled out).
- A separate notifier integration [R24] (for now; the notifier module is built to
  be extracted later). Groups aren't exposed for outside use in the meantime.
- Migration code for the built-in `alert` inside the integration [F28]. Instead, a
  separate converter utility in this repository (not shipped in the integration)
  reads an `alert:` YAML section and writes a file for `alert_redux.import`.

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
| All three notifier kinds supported | The entity model can't carry `data`, and mobile features still need the legacy actions [S1–S4]. |
| Alert Redux's own notifier groups, flagged loud or quiet | Integrations can't say whether they're noisy; only you know [N34, N35]. |
| Notifier layer as a self-contained module, not a separate integration (yet) | Avoids a two-step install and two-repo churn while the design settles; extract it later [N36, R24]. |
| Quiet hours driven by an external entity | Reuses HA's schedule editor; automations can control it [R25]. |
| Custom notification buttons defined independently of notifiers | Alerts can offer "Close door" without depending on mobile details; only configured actions run [N37]. |
| Done notifications throttle along with on notifications | Throttling is exceptional; the throttling summary covers it [§9.7]. |
| Quiet-hours summary gives start and end times | For alerts announced before quiet hours, the summary is where you learn they ended [§9.9]. |
| Notifications after the main card, split into three phases | The card makes notification behaviour easier to debug; smaller phases [§20]. |
| Events built in from phase 1 | Easier than retrofitting every transition; useful for debugging [§20]. |
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

[Decided] Each phase is small enough to build, test, and live with before the next
one starts, and each ends with a usable release.

**Every phase ends with:**

- smoke tests for the new behaviour (`pytest-homeassistant-custom-component`), and
  the card type-checked and rebuilt;
- a run in a real HA instance;
- CI green, and a `0.N.0` release (manifest version bumped, card rebuilt), so HACS
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

*Done when* a door-sensor alert and a template alert fire and end correctly,
including through sensor dropouts and restarts.

### Phase 3 — Main card (0.3.0)

- `alert-redux-card` (§13.1): sub-cards sorted and coloured by priority, icon, name,
  and on or display message (rendered by the integration); acknowledge control;
  dismiss button where enabled; the no-data section; the empty state.
- Styling after weather_alerts_card (N31).

*Done when* the card shows the alerts from phases 1–2 correctly, and acknowledging and
dismissing from the card works.

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

### Phase 5 — Condition alerts II and event alerts (0.5.0)

- **On/off** and **threshold** condition kinds (§4.1).
- **Trigger** and **bus event** alerts (§4.2): duration, per-priority default
  durations, firing again while firing.
- The card's progress bar for event alerts.

*Done when* every alert kind except alert state works end to end.

### Phase 6 — Snooze, disable, suspend; admin card (0.6.0)

- Snoozing and the snooze-end reminder rule (§6.2); disabling (§6.3); suspending
  (§6.4). Actions and events for each.
- The card's snooze control and countdown, and the disabled-alerts count line.
- `alert-redux-admin-card`, basic version (§13.2): all alerts by priority, with
  enable, disable, and suspend.

*Done when* snoozes, disables, and suspensions behave as specified, across restarts.

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

### Phase 8 — Summary sensors and logbook (0.8.0)

- The summary sensors (§11.2), including the diagnostic disabled count.
- The logbook platform (§11.4).
- A pass over the event set and its data (§11.3), plus the ready-to-paste list of
  event types.

*Done when* the signal-light glue can be written as a single-entity automation, and
the Activity card reads well.

### Phase 9 — Notifications II: replacing, clearing, buttons (0.9.0)

- Replacing and clearing (§9.10).
- Built-in and custom buttons, tap handling, and require unlock (§9.11).

*Done when* a mobile notification updates in place, clears when acknowledged, and
"Close door" works from the phone.

### Phase 10 — Throttling and quiet hours (0.10.0)

- Throttling, including held done notifications and the throttling summaries (§9.8).
- Quiet hours: the entity, per-group overrides, threshold, hold and soften, and the
  end-of-quiet-hours reminder and summary (§9.9).

*Done when* a night with quiet hours on produces exactly the specified morning
summary.

### Phase 11 — Generators (0.11.0)

- Generator subentries and entities; target selection; dynamic creation and removal
  (§12.3).
- Generated supersession; the `refresh_generator` action.

*Done when* one generator covers every door lock, including a lock added later.

### Phase 12 — Voice control (0.12.0)

- Assist intents for acknowledge, unacknowledge, and snooze (§14).
- Optional per-alert proxy switches, checked with Alexa and Google Home.

### Phase 13 — Late features (0.13.0 onwards; may be split)

- The acknowledgement queue (§10).
- Card filters (§13.1).
- Creating and editing alerts from the admin card (§13.2).
- The export and import actions and admin-card controls (§13.2, §16).

### Phase 14 — Converter utility

- A standalone tool in this repository, not shipped in the integration, that
  converts an `alert:` YAML section into an import file (§17).

**1.0.0** comes after phase 11, once the core feature set is proven in daily use,
with phases 12–14 as 1.x releases [Decided, provisionally].
