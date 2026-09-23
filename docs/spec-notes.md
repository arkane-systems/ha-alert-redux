# Alert Redux — specification notes (raw capture)

Working notes gathered during brainstorming, before they're reconciled into
`docs/SPEC.md`. Items are recorded roughly as stated, in the order given, and tagged
so they can be referred to by ID. Nothing here is a settled decision yet.

## Captured thoughts

### Batch 1

- **N1 — Transparency (general principle).** An alert entity should be transparent:
  its attributes should expose everything needed to understand its state, plus as much
  of its configuration as can reasonably fit.
- **N2 — Event propagation (general principle).** Use Home Assistant events to
  propagate useful information about state changes, both per alert and in a more
  global sense, so that glue to other integrations (e.g. ha-accent-signal-light) is
  easy to write.
- **N3 — Alert kinds.** Keep Alert2's basic split between condition-based and
  event-based alerts; support both.
- **N4 — Event alert duration.** Event-based alerts fire on a momentary trigger but
  stay firing for a configurable duration afterwards. The duration can be set per
  alert as a time, or by priority.
- **N5 — Condition alert subclasses.** Keep a maximally general template condition
  alert (as in Alert2), but also provide simpler, easier-to-configure subclasses, e.g.:
  - binary sensor on/off;
  - separate conditions for turning on and turning off;
  - numeric thresholds with hysteresis;
  - (etc.)

  All condition alerts support time-based `delay_on` hysteresis, as in Alert2.
- **N6 — Manual alerts.** A third kind of alert that is simply turned on and off by
  service calls.
- **N7 — Unavailable/unknown inputs.** When templates or source entities an alert
  depends on yield `unavailable`/`unknown`, don't treat it as an error (as Alert2
  does); reflect it as an "insufficient data" state on the alert.
- **N8 — Alert entity states.** Replace the built-in alert's `idle`/`on`/`off` with
  these core states:
  - `idle` — not triggered;
  - `active` — triggered;
  - `ack` — acknowledged;
  - `unavailable` — not enough information;
  - `disabled` — disabled, won't fire.

### Batch 2 — alert configuration

- **N9 — Unacknowledgeable alerts.** As with the original `alert`, an alert can be
  marked as unacknowledgeable, so it can't be silenced. This is for things that
  mustn't be ignored, such as fires and leaks.
- **N10 — Priorities.** Use a modified syslog hierarchy: Emergency, Critical,
  Warning, Notice, Informational. It's mainly for display: the card orders and colours
  alerts by priority. When alerts compete for attention, they're also sorted by
  priority.
- **N11 — Supersession.** An alert can supersede, and so suppress, another alert.
  Example: *Back Door Left Open* (fires after 10 minutes) supersedes *Back Door Open*
  (fires immediately).
- **N12 — Ack propagation along supersession (configurable per relationship).** In
  some cases, acknowledging the superseded alert should also acknowledge the alert
  that supersedes it:
  - Yes: acknowledging *Workshop Door Open* when you go to work there means you won't
    be nagged by *Workshop Door Left Open*. You're there and you know.
  - No: acknowledging *Server Room Overheated (Warning)* when you turn the A/C on
    must *not* acknowledge *Server Room Overheated (Critical)*.
- **N13 — Auto-snooze instead of auto-ack (maybe).** Propagation could optionally
  snooze rather than acknowledge, so that if you take long enough, the superseding
  alert speaks up again. You flagged this as possibly too much complexity.
- **N14 — Identity and presentation.** Each alert has a name and a friendly name, and
  an icon. Icons might be chosen from a list associated with each priority.
- **N15 — Notifiers.** Each alert can specify its own list of notifiers (`notify.*`
  entities), which may be empty. If it isn't specified, the defaults are used.
- **N16 — Reminder intervals.** Each alert can set its own reminder schedule. If it
  isn't set, the default is used.
- **N17 — Messages.** The alert's friendly name is the notification title and isn't
  repeated in the message body. There are default forms for three messages:
  - on firing;
  - on stopping firing;
  - the reminder, sent on the N16 schedule while the alert is still firing.
- **N18 — Throttling.** Each alert can set its own throttling. If it isn't set, the
  default is used. Throttling handles flickering inputs and event alerts that fire
  repeatedly.

### Batch 3 — acknowledging, snoozing, and disabling

- **N19 — Acknowledging.** Acknowledging an alert marks it as acknowledged on the
  card, where it sorts below unacknowledged alerts of the same priority, and it stops
  reminder notifications. You can remove the acknowledgement manually. It also clears
  automatically when the alert stops firing, so a new occurrence of an alert always
  starts out unacknowledged.
- **N20 — Snoozing.** Snoozing is acknowledging with a time limit. It acknowledges the
  alert immediately and starts a snooze timer. If the alert is still firing when the
  timer runs out, the alert becomes unacknowledged and reminders start again. The
  timer is cleared if the alert stops firing, or if you remove the acknowledgement
  manually.
- **N21 — Disabling.** Disabling stops an alert from firing at all. It turns the
  whole thing off.
- **N22 — Timed disabling.** A disable that ends on its own, either after a set
  duration or at a set time, may also be useful. Alert2 calls this "snoozing", which
  departs from the standard meaning of that word. It needs a distinct name here.

### Batch 4 — voice control, cards, generators, and startup

#### Voice control

- **N23 — Acknowledging and snoozing by voice.** It must be possible to acknowledge
  alerts by voice, and preferably to snooze them too. This is something you couldn't
  get working with Alert2. There must be a fallback for Alexa, which is very limited
  here; switch entities acting as voice proxies are acceptable if that's the best
  available, but the fallback is required. This is probably a late-phase feature, but
  the design should allow for it from the start.

#### Cards

- **N24 — No built-in history view.** Don't copy Alert2's history feature, which shows
  every alert fired within a time window; it's confusing. The same information should
  come from a standard activity (logbook) card pointed at the alert entities.
- **N25 — Main card layout.** One card containing a sub-card for each alert, sorted by
  priority and coloured by priority. In each sub-card:
  - top left: the icon, and the alert title in bold;
  - below that: the alert's on-message, optionally including entity values (e.g. the
    current temperature for *Server Room Overheated*);
  - bottom right: controls for acknowledging (showing the current acknowledgement
    state), snoozing, and so on.
- **N26 — Progress bar for event alerts.** An event alert's sub-card shows a progress
  bar that empties as its remaining firing time runs out.
- **N27 — Section for unavailable alerts.** A section at the bottom of the card lists
  alerts that currently lack data (the N7/N8 state), so you know about them.
- **N28 — Empty state.** When nothing is firing, the card is still shown, with a small
  grey "no alerts are firing" message.
- **N29 — Snooze timer shown.** If a snooze timer is running, it's shown in the
  controls area.
- **N30 — Where alerts are configured, and an admin card.** You'd considered
  configuring alerts under the integration, or among HA's helpers, but either option
  seems to make enabling and disabling awkward. So a separate admin card may be
  needed: it lists alerts grouped by priority, and lets you enable, disable, and
  possibly configure them.
- **N31 — Design references.** General inspiration:
  [bartjanisse/ha-alert](https://github.com/bartjanisse/ha-alert) and
  [djdevil/AlertTicker-Card](https://github.com/djdevil/AlertTicker-Card). For
  styling, the preferred model is
  [seevee/weather_alerts_card](https://github.com/seevee/weather_alerts_card).

#### Generators

- **N32 — Generators.** We need a way to create many alerts for entities with similar
  names and properties, e.g. the same alert on every door or every lock, set up in an
  elegant way. It doesn't have to work the way Alert2's generators do. One idea is
  `alert_generator` entities that create alert entities flagged as immutable, or
  something equally elegant.

#### Startup and resilience

- **N33 — Resilience.** HA sometimes starts up slowly. Waiting until HA reports it has
  started and allowing a grace period are both acceptable. Whatever else is done,
  Alert Redux must cope with:
  - notifiers that become available late;
  - entities used by alerts that become available late;
  - integrations, notifiers included, that go down, come back up, or restart while HA
    is running.

## Prior-art gaps (P-series)

Features found in the documentation of
[Alert2](https://github.com/redstone99/hass-alert2),
[ha-alert](https://github.com/bartjanisse/ha-alert), and HA's built-in
[alert](https://www.home-assistant.io/integrations/alert/) that aren't covered by
N1–N33, plus a few features common to alerting systems generally. Each needs a
decision: adopt it, adapt it, or exclude it deliberately.

### Notification delivery

- **P1 — Notifier `data`, `target`, and `title` passthrough** (all three). Each alert
  has a dict passed through to the notify call, templatable. Mobile push depends on
  this for its `tag`, `channel`, `priority`/`interruption-level` (critical alerts),
  and similar settings.
- **P2 — Replacing and clearing mobile notifications** (built-in `alert`, Alert2).
  Using the same `tag` means a reminder replaces the earlier notification on the
  phone instead of adding another. Sending `clear_notification` when the alert stops
  firing, or is acknowledged, removes it from the phone.
- **P3 — Actionable notifications** (built-in `alert` via Telegram inline keyboards).
  Mobile notifications include Acknowledge and Snooze buttons that call back into HA.
  This is a second route to N23's aim of acknowledging without the dashboard.
- **P4 — Done-notification control** (all three). Alert2 has `done_notifier`
  (separate recipients, or none). The built-in `alert` sends `done_message` only if
  an "on" notification was actually sent. Alert2 also skips the done notification
  for an acknowledged alert, unless `ack_reminders_only` is set.
- **P5 — Delaying the first notification (`skip_first`)** (built-in `alert`). The
  alert fires immediately, so its state and the card show it, but the first
  notification waits for the first reminder interval. This is different from N5's
  `delay_on`, which delays the *state* change.
- **P6 — Escalating reminder schedules** (built-in `alert` `repeat`, Alert2).
  Reminder intervals can be a list, e.g. `[15, 30, 60]`: the gaps grow, then the last
  value repeats.
- **P7 — Notifier lists from a template or entity** (Alert2). The recipient list
  comes from a template or an entity's state, e.g. "whoever's home".
- **P8 — `persistent_notification` as a notifier, with grouping** (Alert2). Each
  message kept separately, or collapsed into one, or collapsed and dismissed when the
  alert stops firing.
- **P9 — Throttling summaries** (Alert2). When throttling starts, the notification is
  marked "[Throttling starts]". When it ends, a summary is sent, e.g. "fired 10× in
  the period, most recently 15 m ago".
- **P10 — Nagging until acknowledged (`ack_required`)** (Alert2). Reminders continue
  until someone acknowledges, even after the alert has stopped firing. Applies to
  event alerts too: a momentary event nags until acknowledged.
- **P11 — Escalation** (common in alerting generally, not in these three). If an
  alert is still unacknowledged after some time, notify more or different notifiers,
  or raise its priority.
- **P12 — Quiet hours** (common generally). Hold back notifications below a given
  priority during a schedule, e.g. overnight. Holding back vs. dropping, and whether
  to send a summary afterwards, would need deciding.

### Alert sources and lifecycle

- **P13 — Firing an event alert by service call** (Alert2 `report`, ha-alert
  `create`). An automation fires a declared event alert, passing a message and data.
  N3/N4 don't yet say whether event alerts are triggered by HA triggers, by a service
  call, or both.
- **P14 — Ad-hoc, undeclared alerts** (ha-alert). An automation creates an alert at
  runtime with a message, priority, and an optional condition for dismissing it
  automatically. Alert2 instead requires alerts to be declared, and raises an
  "undeclared alert" error otherwise. Should N6 manual alerts be declared in advance?
- **P15 — Dismissing** (ha-alert). This removes an alert from the active list, which
  is different from acknowledging it. For event alerts it could mean "end the
  duration now". Should manual alerts and event alerts be dismissable?
- **P16 — Event alert with a condition** (Alert2). The trigger fires the alert only if
  a condition is also true at that moment.
- **P17 — Supersession details** (Alert2). Supersession is transitive (A ⊃ B ⊃ C).
  It suppresses notifications only; the superseded alert's state is unchanged. It
  also has a debounce (default 0.5 s), so that two related alerts turning on almost
  together don't both notify. This bears on F7.
- **P18 — Threshold details** (Alert2). Minimum and/or maximum limits, which can come
  from templates or entities, and optionally combined (AND) with a condition.

### Monitoring the alert system itself

- **P19 — Internal alerts** (Alert2). Built-in alerts for Alert Redux's own
  configuration errors, internal errors, and (optionally) unhandled exceptions
  anywhere in HA. If the configured notifier is broken, they fall back to
  `persistent_notification`. The underlying question is who raises the alarm when
  the alerting system itself is broken.
- **P20 — Startup-watchdog support** (Alert2). `early_start` lets an alert be
  monitored before HA has finished starting. There's also a helper entity for
  alerting when HA startup takes too long. This bears on N33.

### Glue, aggregates, and API

- **P21 — Aggregate entities** (ha-alert). Sensors counting active alerts per
  priority. For N2 glue such as driving a signal light, a "highest active priority"
  sensor, plus active and unacknowledged counts, would make most integrations a
  single-entity automation.
- **P22 — Lifecycle events** (Alert2). Alert2 fires `create`, `delete`, `fire`, `on`,
  `off`, `ack` and `unack` events. Our list would add snooze, unsnooze, disable,
  enable, and supersession events.
- **P23 — Who did it** (common generally). Record which user acknowledged, snoozed,
  or disabled an alert, and when, in attributes and event data. This fits N1.
- **P24 — Bulk actions** (Alert2 `ack_all`). Acknowledge everything, or everything at
  or below a given priority.
- **P25 — Python API** (Alert2). Other custom integrations can raise alerts directly.
- **P26 — Reload without restarting** (Alert2). Applies if YAML configuration is
  supported (F19).
- **P27 — Card filters** (ha-alert). Hide acknowledged alerts, and show or hide
  alerts by priority, as options on the card or controls in its header.
- **P28 — Template context variables** (Alert2). How long the alert has been on,
  firing counts, and the trigger payload for event alerts, all available inside
  message templates.

## Responses to the prior-art gaps

### Batch 5

- **R1 — P1–P3, P8 (mobile and notification features): deferred for a longer
  discussion.** HA notifications are changing: the legacy `notify.<name>` actions are
  being deprecated in favour of `notify.*` entities, and it isn't clear where things
  will end up. You're reluctant to build support for the old system in the meantime.
  This ties in with F8.
- **R2 — P13, P16 (how alerts are raised): decided.** There are two kinds of event
  alert:
  - **Trigger event alerts**, fired by an HA trigger as in Alert2, with an optional
    condition (P16).
  - **Bus event alerts**, fired when a matching event is received on the HA event bus.

  Neither kind can be fired or dismissed manually. **Manual alerts** are a separate
  kind, fired and dismissed by a pair of service calls.
- **R3 — P15 (dismissing): decided.** Only manual alerts can be dismissed. Condition
  alerts end when their condition changes, and event alerts end when their duration
  runs out.
- **R4 — P14 (ad-hoc alerts): decided, excluded.** There are no ad-hoc alerts. Manual
  alerts must always be declared in advance.
- **R5 — P21 (summary sensors): decided, adopted.** A comprehensive set of summary
  sensors is wanted.
- **R6 — P19 (internal alerts): decided, excluded for now.** There are no internal
  alerts to begin with; problems are logged instead. A fallback notifier is wanted,
  though.
- **R7 — P10 (nagging until acknowledged): liked, deferred to a late phase.** Rather
  than complicating the alert cycle, this could be a separate "needs
  acknowledgement" system. When an alert stops firing unacknowledged, it's handed off
  to that system. Several unacknowledged firings would then produce several separate
  items to acknowledge, which is the preferred behaviour. The details are to be worked
  out later.
- **R8 — P11 (escalation): excluded as a separate feature.** Supersession already
  covers it, as the *Back Door Open* / *Back Door Left Open* pair shows. It might also
  be worth thinking about in connection with generators.
- **R9 — P12 (quiet hours): adopted; design still open.**
  - Quiet hours apply to, for example, every priority below Warning.
  - Suggested behaviour: alerts still firing when quiet hours end notify again then.
    Alerts that started and stopped during quiet hours are presented as a summary,
    possibly using the same mechanism as R7.
  - Quiet hours may need to be per notifier, since a silent text message at night is
    very different from a loud announcement.
  - How these features fit together still needs thinking about.
- **R10 — P4 (done notifications): decided.** The done notification is always sent,
  even for an acknowledged alert, with no option to turn that off. Separate notifiers
  for the on, reminder, and done notifications are probably not worth the
  implementation cost.
- **R11 — P5 (`skip_first`): excluded.** Supersession already covers it.
- **R12 — P6 (escalating reminder schedules): decided, adopted.**

### Batch 6

- **R13 — P7 (notifiers chosen by template or entity): not now, but don't rule it
  out.** The design shouldn't prevent it, but it won't be implemented yet. You've never
  needed it in Alert2.
- **R14 — P9 (throttling summaries): a good idea if throttling is happening, but low
  priority.** In practice, the only throttling you see in Alert2 comes from its
  internal-error alerts at startup. Throttling itself matters, but it isn't a
  priority feature.
- **R15 — P17 (supersession details): decided.** Supersession is transitive, as in
  Alert2. Include the debounce as a safeguard.
- **R16 — P20 (early start): excluded; see the response below.** HA runs far more
  often than it starts up. Condition alerts fire as soon as their data is available
  anyway, and event alerts wouldn't be reliable during startup regardless. A retry
  queue for notifiers that aren't ready yet may be worthwhile, but whoever is
  restarting HA is usually right there watching.
- **R17 — P22 (lifecycle events): decided, adopted.**
- **R18 — P23 (who did it): decided, adopted.** The activity/logbook view must display
  it properly (see F18).
- **R19 — P24 (bulk actions): excluded for now.** Anything serious enough to be an
  alert shouldn't be dismissed in bulk. Revisit if it becomes a problem in real use.
- **R20 — P25 (Python API): excluded.** Other components interact through actions;
  if they need more, add more actions.
- **R21 — P26 (reload) and configuration method: leaning towards UI-only.** Reload is
  only needed if there's YAML configuration. You're inclined not to support YAML at
  all: HA as a whole is moving away from it, and it would mean writing a second set of
  configuration code. This largely answers F19.
- **R22 — P27 (card filters): adopted, late phase, in the card.**
- **R23 — P28 (template variables): decided, adopted.** Needed for custom reminder
  messages and the like. Templates can also read entity states and attributes (as in
  N25), so that *Server Room Overheated* reminders can say exactly how hot it is.

### Response to R16

The early-start part is agreed. A notifier retry queue should stay, though, because
restarts often happen with nobody watching:

- recovery after a power cut;
- HA OS or Supervisor restarts, including watchdog restarts after a crash;
- scheduled restarts;
- an integration reloading itself while HA is running.

N33 already requires coping with notifiers that arrive late, and a small queue with
a timeout is the simplest way to meet that. Without it, an alert that fires during
the startup window, e.g. a leak sensor that came up wet, would reach no one.

One related point about restarts: an alert that was active before the restart and is
still active afterwards should resume quietly (F21). It shouldn't send a fresh "on"
notification.

## Notifier and quiet-hours discussion

### Status quo (confirmed against HA core 2026.9 `dev`)

- **S1 — Notify entities.** `notify.send_message` sends only `message`, and `title`
  if the entity supports it. There's no `data` and no `target`. Notify entities are
  real entities, so they can be selected, labelled, and grouped.
- **S2 — Persistent notifications.** `persistent_notification.create` takes a
  `notification_id`, so a notification can be replaced, and `.dismiss` removes it.
  The legacy `notify.persistent_notification` action also reads `notification_id`
  from `data`. Persistent notifications aren't entities.
- **S3 — Legacy notify actions.** These take `data` and `target`. Deprecation happens
  per integration, through a Repairs "migrate notify" issue, as each integration
  moves to entities. In HA 2026.2, about 59 integrations were still legacy and about
  15 had entities.
- **S4 — `mobile_app` has both kinds.** Its notify entity sends only message and
  title. Actionable buttons, `tag`, `clear_notification`, and critical alerts are
  still possible only through the legacy `notify.mobile_app_*` action.

### Batch 7

- **N34 — Integrations can't report whether they're quiet.** Some couldn't even if
  there were an interface: `notify_mqtt` can't know who is listening on its topic.
  So whether a notifier is quiet has to be recorded where notifiers are configured
  in Alert Redux.
- **N35 — Notifier groups.** Alert Redux has its own internal notifier groups. A group
  can contain notifiers of any of the three kinds (S1–S3). Each group is flagged
  **quiet** or **loud**: quiet hours silence loud groups but not quiet ones. Alerts
  are configured in terms of these groups.
- **N36 — Maybe a separate integration.** The notifier-group and quiet-hours layer
  could be a general-purpose "notify unbreaker" and quiet-hours provider in its own
  integration, which Alert Redux depends on and which is developed, debugged, and
  released separately.

### Batch 8

- **R24 — N36 (separate integration): decided, not yet.** The notifier layer is built
  as a self-contained module inside Alert Redux, with a narrow interface, so it can
  be extracted into its own integration later.
- **R25 — N35 (notifier groups): adopted, with these refinements:**
  - Each group member can carry settings specific to its kind of notifier: `data`
    templates, `target`, and `notification_id` schemes. Alerts refer only to groups.
  - Quiet hours are driven by an **external on/off entity**, e.g. a Schedule helper.
    There's a global one, and a loud group can optionally use its own instead.
  - Priority still overrides quiet hours, as in R9.
  - A loud group chooses its quiet-hours behaviour: **hold** notifications, or
    **send them differently** using alternative data, e.g. silently on mobile.
  - The defaults and the fallback are groups.
- **N37 — Custom buttons from alerts.** Alerts should be able to see slightly past
  the group abstraction. For example, *Garage Door Left Open* could offer a "Close
  door" button, which the group passes only to notifiers that support it (the mobile
  apps).

## Flags for the reconciliation pass

Points to raise once the capture phase is over. These are not objections yet.

- **F1 (N8, N7):** `unavailable` is a reserved state in Home Assistant. The frontend,
  history, and templates treat it as "the entity itself isn't working", and
  `available = False` makes attributes disappear. That seems to clash with N1
  (transparency), since an alert in this state would lose its attributes. It may need
  a different state name, e.g. `no_data`.
- **F2 (N4):** When an event alert fires again while it's still within its duration,
  does that extend the duration, restart it, or get ignored? And how does
  acknowledging interact with the duration?
- **F3 (N8, N13, N20):** N20 makes snoozing a general feature. Is it its own state,
  `snoozed`? Or is it `ack` with a `snoozed_until` attribute, since N20 defines
  snoozing as a timed acknowledgement? The attribute option keeps the state set small.
  The separate-state option makes snoozed alerts easy to see from state alone, which
  helps N2 glue.
- **F12 (N19, N5, N18):** "Stops firing" needs a precise meaning. Does the `delay_on`
  or throttle logic also apply when an alert turns *off*? If the input flickers off
  and on again for a moment, does that clear the acknowledgement? That would conflict
  with N18's aim of handling flicker.
- **F13 (N19, F5):** N19 says acknowledgements clear when an alert stops firing, so
  new occurrences always start unacknowledged. The N12 pre-acknowledgement is an
  exception: the superseding alert starts out acknowledged. The spec should state
  that exception explicitly.
- **F14 (N9, N20–N22):** Can an unacknowledgeable alert be snoozed? Presumably not,
  since snoozing is a form of acknowledging. Can it be disabled, with or without a
  time limit? Disabling is presumably still allowed for maintenance, but that should
  be stated.
- **F15 (N21):** What happens when you disable an alert that's currently `active`?
  Presumably it goes to `disabled`, and should an "ended" notification be sent? And
  when it's re-enabled while its condition is still true, does it fire immediately
  (skipping `delay_on`?) and send a fresh notification?
- **F16 (N22):** Name ideas for timed disabling: *suspend* (probably the best fit;
  distinct from "disable" and from "snooze"), *pause*, *hold*. Is it a separate
  state, or `disabled` with a `disabled_until` attribute?
- **F17 (N23):** Voice options:
  - For Assist, the integration can register its own intents, e.g. "acknowledge the
    back door alert" and "snooze the server room alert for 30 minutes". These match
    against alert names, so they don't need a proxy entity for every alert.
  - For Alexa, the practical options are one proxy switch per alert (turning it on
    acknowledges; turning it off removes the acknowledgement) or exposed scripts.
    Alexa has no good way to pass a snooze duration, so it may only get a fixed-length
    snooze. Should proxy switches be optional per alert, so that entities aren't
    doubled?
- **F18 (N24, N1):** For a logbook or activity card to read well, our state values
  need translations (`idle` → "Idle", `ack` → "Acknowledged", and so on) through the
  entity's `translation_key`. Our HA events could also get readable logbook entries
  from a logbook platform (`async_describe_events`). That fits N1 and N2 too.
- **F19 (N30):** This is a major decision: how are alerts defined?
  - YAML, as with Alert2 and the original `alert`;
  - UI, where each alert could be a **config subentry** of the single integration
    entry (a feature of recent HA versions);
  - both.

  Separately, our own `disabled` state must be distinct from HA's entity-registry
  disable, which removes the entity entirely and would conflict with N1. That may be
  the awkwardness you had in mind. Since N30 imagines configuring from the admin card,
  UI configuration seems to be a goal.
- **F20 (N32):** Generator questions:
  - How are target entities selected? Glob or regex on entity ID, labels, areas,
    device classes? (Labels fit well with how ha-recorder-throttle works.)
  - When the set of matching entities changes, e.g. a new door lock is added, are
    alerts created and removed automatically?
  - Can a generated alert override any settings, such as notifiers, and is its entity
    ID stable?
- **F21 (N33):** State isn't restored across restarts. Acknowledgements, snoozes,
  disabled/suspended status, and event-alert timers should all survive an HA restart
  (`RestoreEntity` or a `Store`). Also: when a notifier is down while a notification
  is due, is the notification retried, queued, or dropped and logged?
- **F22 (N25, N17):** Is the on-message shown on the card the same template as the
  notification message, or can it be configured separately? It would also help to
  decide whether disabled and suspended alerts appear on the main card at all, or
  only on the admin card.
- **F23 (R2):** A bus event alert is equivalent to a trigger event alert using an
  `event` trigger (event type plus data filter). Keeping it as a separate, simpler
  kind for configuration is still reasonable. Internally, both kinds could share one
  engine.
- **F24 (R8, R11):** Supersession fires based on how long the superseded alert has
  been *firing*, not how long it has gone *unacknowledged*. To escalate only when
  nobody has acknowledged, the superseding alert's condition would have to check the
  superseded alert's state, e.g. "`alert.x` has been `active` (not `ack`) for 30
  minutes". This fits N1 well. Should it get its own simple condition kind ("another
  alert unacknowledged for X"), so that people don't have to write templates for it?
- **F25 (R10, R9, N11):** "Always send the done notification" needs a boundary case.
  If the *on* notification was never sent, because of supersession, quiet hours,
  throttling, or an empty notifier list, is the done notification still sent? The
  built-in `alert` sends it only if an on notification went out. A done notification
  arriving with nothing before it is probably confusing.
- **F26 (R6):** Where does the fallback notifier apply? Only when the configured
  notifiers are missing or failing, or also for alerts that have no notifiers
  configured? (N15 allows an empty list, which presumably means "notify nobody", not
  "fall back".)
- **F27 (R21):** UI-only configuration makes each alert, and presumably each
  generator (N32), a config subentry. Consequences:
  - The UI flows must handle templates and triggers well. HA's template and trigger
    selectors can do this, but the forms will be large.
  - Configuration can't be kept in version control or edited as text. It could be
    worth adding export/import of alert definitions in the admin card later.
- **F28 (R21):** There's no YAML import, so there's no automatic migration from the
  built-in `alert`. Would a one-off migration service that reads `alert:` YAML be
  worthwhile? Or is it out of scope, given how simple those alerts are to recreate?
- **F4 (N4, N10):** The priority levels are now defined in N10. Still open: does
  priority set defaults for anything besides display? N4 suggests event-alert
  duration, and could reminders, notifiers, or icons (N14) default by priority too?
- **F5 (N12):** Propagating an acknowledgement usually happens *before* the
  superseding alert fires. You acknowledge *Workshop Door Open* before *Left Open*
  exists. So this is really a pre-acknowledgement of an alert that isn't active yet.
  How long does it last? Presumably until the superseded alert returns to idle.
- **F6 (N9, N12):** What happens when propagation targets an unacknowledgeable
  alert? It presumably must not work, and should that be a configuration validation
  error?
- **F7 (N11):** Supersession semantics: is it one level or chained (A ⊃ B ⊃ C)? Is
  the superseded alert's state changed, or does it just stop notifying? Does it still
  appear on the card, maybe grouped under the superseding alert?
- **F8 (N15):** Many notifiers, notably mobile app push, are still legacy
  `notify.<name>` *actions* rather than `notify.*` *entities*. Entity-based
  notification can't send critical or actionable mobile notifications at present.
  Should both be supported?
- **F9 (N16, N18):** How do reminders and throttling interact? Is throttling about
  notifications only, or about the alert's state too? For example, does a flickering
  input make the entity flicker but notify only once?
- **F10 (N10):** The terms "alert" and "notification" are used interchangeably. The
  spec should keep them distinct: the alert is the entity and its state, and a
  notification is a message sent about it.
- **F11 (N14):** "Name" versus "friendly name": presumably the name is the
  slug/entity ID and the friendly name is the display name. To confirm.
