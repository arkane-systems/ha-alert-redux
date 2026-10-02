# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration, **Alert Redux** (domain `alert_redux`), intended to
replace the deprecated built-in `alert` integration, plus the Lovelace card(s) for using
it. Both live in this one repository and are delivered by a single HACS *integration*
install: the card bundle ships inside the integration package and the integration serves
and registers it itself.

Phases 1 (manual alerts) and 2 (state and template condition alerts, no-data
handling) and 3 (the main card, with messages rendered for it) are implemented, plus
0.3.1 (the Alert Redux label, spec §11.5), phase 4 (notifications: groups, on /
reminder / done, retries and the fallback), phase 5 (on/off and threshold
condition alerts, trigger and bus event alerts, and the card's progress bar), and
phase 6 (snoozing, disabling, and suspending, the card's snooze control, and the
admin card), phase 7 (supersession, propagation and pre-acknowledgement, the
alert state kind, dangling references, and the card's superseded alerts), and
phase 8 (the summary sensors, the logbook platform, and the `_data_restored`
event), and phase 9 (replacing and clearing notifications, and notification
buttons), and phase 10 (throttling and quiet hours), and phase 11 (generators,
including generated supersession), and, for 1.0.0, manual alerts that end by
themselves (spec §4.3), and phase 12 (voice control: Assist commands, and proxy
switches and snooze buttons for Alexa and Google Home), and, so far in phase 13,
the export and import actions.

## Specification

**`docs/SPEC.md` is the authoritative design** for the integration and cards. Read it
before implementing anything, and follow its phase plan (§20): build one phase at a
time, each ending with tests, a run in real HA, green CI, and a `0.N.0` release.

- Every point is tagged **[Decided]**, **[Deferred]**, and so on. Don't reopen a
  Decided point while implementing. If building a phase shows that a decision
  doesn't work, raise it with the user and update the spec, including its decision
  log (§19), rather than quietly diverging.
- `docs/spec-notes.md` is the brainstorming record the spec was built from. The
  bracketed IDs in the spec (N7, R2, F12, …) refer to it. Use it for background and
  rationale; it isn't a source of requirements in its own right.

## Layout

- **`custom_components/alert_redux/`** — the integration (what HACS installs).
  - `__init__.py` — creates the `EntityComponent` for the `alert_redux` entity domain
    and registers the actions; config entry setup/unload; applies subentry and
    option changes **in place** (adding, updating, and forgetting alert entities)
    rather than reloading the entry, including notifier group subentries (given to
    the `Notifier` in place) and generator subentries (given to the
    `GeneratorManager`); announces alerts deleted since the last run (any stored
    record that's neither an alert subentry's nor a generated alert's); the
    `refresh_generator` action.
  - `alert_redux.py` — the entity platform for our own domain, loaded by
    `EntityComponent.async_setup_entry`; adds one entity per alert subentry, linked
    with `config_subentry_id` so HA removes it with the subentry, then starts the
    generators, and keeps the add-entities callback for alerts added later.
  - `definitions.py` — `AlertDefinition`, what an alert entity is built from:
    unique ID, name, data, and for a generated alert its generator, target, and
    extra template variables. Fixed alerts' come from their subentries
    (`from_subentry`).
  - `generators.py` — generators (spec §12.3): `TargetCriteria` (HA-free
    matching, AND across and OR within), `async_candidates` (the entities that
    can be targets), `Generator` (one subentry: its alert template and the
    definitions it has made, by target key), and `GeneratorManager` in
    `hass.data`, which adds, updates, and removes generated alerts as the
    registries and states change (debounced), holding back removals until the
    startup grace has passed. It also resolves generated alerts' relationships
    to other generators into their alerts for the same target
    (`resolve_relationships`, set on each generated alert as its
    `relationship_resolver`). Generated alerts are added with the generator's
    `config_subentry_id`, and kept in `DATA_ENTITIES` by unique ID like the
    fixed ones. Also `async_forget_alert`, which drops a deleted alert's record
    and announces it.
  - `validation.py` — the checks of an alert's or generator's stored data that the
    config flows and import share: kind checks, references and supersession
    cycles (over `Definitions`: the alerts and generators as they are or as an
    import leaves them).
  - `portable.py` — export and import (spec §16): `export_definitions`, the stored-data
    schemas per kind, `async_plan_import` (collects every problem; names to IDs,
    create / update / unchanged), `async_apply_import`. The actions are in
    `__init__.py`.
  - `entity.py` — `AlertEntity`, the base every kind shares and never used on its
    own (state, attributes, actions, events, persistence, and the rendered messages
    while firing; snoozing, disabling, and suspending; durations and their expiry,
    for event alerts and self-ending manual alerts; starting a manual or event
    alert's firing; supersession's on debounce, skipped and held reminders, and
    held done notifications; throttling on and done notifications, and the
    throttling summary). Differences between kinds are class attributes
    (`_awaits_data`, `_has_duration`, `_fire_data_is_trigger`) and overridden
    hooks, not checks on the kind; `fire` and `dismiss` are stubs raising
    `not_manual`, since HA calls entity actions by name on every entity.
    `ManualAlertEntity` (fire, dismiss, and the manual settings),
    `ConditionAlertEntity`
    (state, on/off, threshold, template, and alert state kinds: watches its sources,
    judges them
    by the kind's rule in `_judge`, and runs the delays and no-data grace period on
    one timer), and `EventAlertEntity` (trigger and bus event kinds: fires on its
    triggers, for a duration). One-shot timers use `PointTimer`, and
    `_async_update_timers` sets them from the runtime's deadlines (reminder,
    snooze, suspension, event expiry, throttling's end). Kinds detach and re-attach their inputs on
    disable and enable through `_async_inputs_stopped` / `_async_inputs_started`.
  - `model.py` — `AlertRuntime`, the HA-free state machine (including condition
    evaluation, `evaluate()`, event durations, and on/off edges), its
    serialization, the threshold rule (`threshold_holds`), the throttle rule
    (`Throttle`, `AlertRuntime.throttle_note` / `throttle_expire`), and the
    global `Settings`.
  - `sources.py` — condition inputs reporting their result or no data:
    `StateSource`, `TemplateSource`, `ThresholdSource` (a `Reading`), and
    `SourceSet`, which reports a kind's sources (and the extra condition) together.
  - `supersession.py` — `SupersessionGraph` (HA-free: relationships by entity ID,
    their transitive closure, `find_cycle`) and `Supersession`, the coordinator in
    `hass.data` that the entities share: it builds the graph from the entities'
    own configuration, answers `superseded_by`, when a superseding alert is due to
    fire (`superseder_due`, for holding reminders), and the done-window
    decision, and
    passes on an alert starting or stopping firing, and propagates
    acknowledgements as pre-acknowledgements (the entities call it from
    `async_write_ha_state`). Pre-acknowledgements are kept by the source's
    unique ID. It also reports each alert's `broken_references`.
  - `summary.py` — `summarise` (HA-free: the counts, entity-ID lists, and
    highest priorities across all alerts; a firing alert that's superseded counts
    as firing but not as active, and is listed as superseded) and `SummaryCoordinator` in
    `hass.data`, which each alert reports to (by unique ID) from
    `async_write_ha_state` and withdraws from when removed; it recomputes once
    per burst of reports and tells the sensors.
  - `sensor.py` — the summary sensors (spec §11.2), one of the platforms forwarded
    from the config entry, and a `GeneratorSensor` per generator (§12.3). No
    device and no label; their entity IDs are set explicitly, whatever the
    names.
  - `logbook.py` — describes only the events that add to the logbook's state rows
    (spec §11.4). A describer can't drop a row, so events like `_acked`, which
    would duplicate their state rows, are simply not registered.
  - `triggers.py` — `TriggerWatcher`: attaches HA triggers once HA has started and
    after the startup delay, handing on each firing's variables made JSON-safe.
    Used by event alerts and on/off sides.
  - `speech.py` — what voice commands hear and say, without HA (spec §14.1):
    normalising and matching spoken alert names (`Candidate`, `match`),
    spoken durations (`parse_duration`), and the English replies.
  - `voice.py` — the four intents (acknowledge, unacknowledge, snooze, and
    which alerts are firing), registered with the entry, and their English
    sentences, attached as HA's own conversation triggers once HA has started
    (a pipeline checks them before any agent). The intents act through the alert
    actions with the speaker's context; `async_exposed_alerts` is the alerts
    exposed to an assistant.
  - `llm.py` — the LLM tools platform (HA 2026.8+): the intents as
    `alert_redux__…` tools. Only the `llm` integration imports it; older HA
    offers registered intents to LLM agents by itself.
  - `exposure.py` — `async_set_exposure`: exposing an entity to assistants, done
    once and remembered in the alert's stored record (`assist_exposed`,
    `proxies_exposed`), like the label.
  - `proxies.py` — the voice proxies (spec §14.2): `ProxyEntity`, the base of
    the proxy switch and snooze button, and `ProxyManager` in `hass.data`, which
    the alerts report to from `async_write_ha_state`: it makes and removes
    proxies to match each alert's options (with the alert's or generator's
    `config_subentry_id`), keeps their state, copies the alert's area and labels
    (not the alerts label), exposes them to Alexa and Google and hides them from
    Assist once, and removes them when an alert is forgotten
    (`generators.async_forget_alert`).
  - `switch.py`, `button.py` — the proxy platforms: `ProxySwitch` (on while the
    alert is active; off acknowledges, on unacknowledges, refused with
    `not_firing` while it isn't firing) and `ProxySnoozeButton`. Not to be
    confused with `buttons.py`, the notification buttons.
  - `messages.py` — the message template context (`message_context`, shared with
    notifications) and `MessageTracker`, which renders the on and display messages
    for the card and re-renders them as the entities they read change.
  - `notifications.py` — the alert side of notifying: which groups an alert sends
    to (its own, the defaults, or the fallback), rendering the on / reminder / done
    messages, and handing them to the notifier with the alert's lifecycle key;
    telling the notifier when an alert is acknowledged, deleted, or renamed; the
    throttling summary's text; and `async_quiet_hours_ended`, the notifier's
    owner callback when a group's quiet hours end (one reminder per active
    alert, one summary of the firings that ended). Reminder timing lives in `model.py`
    (`AlertRuntime.next_reminder`, `next_reminder_slot`) and `entity.py`.
  - `notifier/` — the **self-contained notifier module** (spec §9.1): groups and
    members (`model.py`), delivery per member kind (`members.py`), the retry queue's
    records (`retry.py`), missing-action Repairs issues (`repairs.py`), and the
    `Notifier` (`__init__.py`). **It must not import anything Alert-Redux-specific**,
    so it can be extracted later; its owner passes in the store key and issue domain.
    It keeps its own `Store` (the retry queue, the *live records* of which
    members are showing each key's notification, so clears reach exactly those,
    spec §9.10, and notifications held for quiet hours). Quiet hours (§9.9) are
    the notifier's: notifications carry an `urgency` (Alert Redux maps it from
    the priority), loud groups hold or soften, and when their quiet-hours entity
    turns off, the owner's `on_quiet_ended` callback says what to send. Named `notifier`, not `notify`: a `notify.py` would be loaded as
    a notify platform.
  - `buttons.py` — notification buttons (spec §9.11): building an alert's
    (custom, then Acknowledge and Snooze), their action IDs
    (`ALERT_REDUX_<unique ID>_<button>`), and the `mobile_app_notification_action`
    listener, which hands a tap to the alert (`AlertEntity.async_button_tapped`).
  - `issues.py` — Alert Redux's own Repairs issues (the unset default groups, and
    references to alerts that don't exist). `__init__.py` follows alert renames
    in the entity registry, rewriting the references to them. Not
    called `repairs.py`, which HA would take for the repairs platform.
  - `store.py` — `AlertStore`, the single persistent `Store` (no `RestoreEntity`);
    also remembers the card version the user was last told to refresh for, and the
    alerts label's ID.
  - `labels.py` — the "Alert Redux" label: created once; each alert is given it
    once, tracked by `labelled` in its stored record; never forced back.
    **Don't give alert entities a device**: since HA 2026.4 the device name is
    prefixed to their names and entity IDs (spec §11.5).
  - `config_flow.py` — single-instance config flow (`single_config_entry` in the
    manifest makes HA enforce the one-instance rule), the options flow (global
    defaults), the alert subentry flow (a menu of kinds, then a form per kind, with a
    collapsed notifications `section` flattened into the stored data), the
    generator subentry flow (a menu of the condition kinds, then the kind's alert
    form with `generator=True`: a name template and a `targets` section, stored
    nested, instead of the kind's entity and the subject entity), and the
    notifier group subentry flow.
  - `services.yaml`, `icons.json` — action definitions and icons.
  - `frontend.py` — serves `frontend/` via a static path and registers the card as a
    storage-mode Lovelace resource with a `?v=<manifest version>` cache-buster, updating
    an existing resource in place on upgrade; falls back to `add_extra_js_url` when the
    resource collection isn't available (YAML-mode dashboards). Also the
    `alert_redux/info` websocket command (the integration version, which the card
    compares with its own), and the "refresh your browser" notification, raised once
    per card version.
  - `frontend/alert-redux-card.js` — **build output, do not edit by hand.**
  - `strings.json` / `translations/en.json` — `en.json` is `strings.json` with
    `[%key:...%]` references resolved to literal text. Edit `strings.json`, then
    regenerate `en.json` with `resolve()` from `tests/test_translations.py`, whose
    `test_en_matches_strings` fails if they drift.
  - `brand/icon.png`, `brand/icon@2x.png` — integration icon (256 and 512 px),
    rendered from `assets/alert-redux-icon.svg`.
- **`frontend/`** — card source (TypeScript + Lit), bundled with esbuild.
  - `src/main.ts` — the bundle's entry point, importing both cards.
  - `src/dialog.ts`, `src/transfer-dialog.ts`, `src/describe.ts` — the admin card's
    modal dialog element; its summary / export / import dialog (from the export and
    import actions); and `describe`, the pure text summary of an exported definition.
  - `src/flow-client.ts`, `src/flow-dialog.ts` — create and edit from the admin
    card: a client for HA's subentry flow REST API (and the entity registry /
    delete calls), and the dialog that renders each flow step with HA's `ha-form`,
    labelled from the integration's translations.
  - `src/alert-redux-card.ts` — the main card element; `src/alert-redux-admin-card.ts`
    — the admin card; `alerts.ts` (reading, sorting, and classifying alert entities),
    `format.ts`, `styles.ts` (`sharedStyles` for both cards, plus the main card's),
    `types.ts`.
  - `dev/preview.html` + `dev/preview.ts` — the card against a mock `hass`, in light
    and dark themes, with stub `ha-card`/`ha-icon`. `npm run preview` builds it into
    `dev/dist/` (gitignored); serve `frontend/dev/` over HTTP and open
    `preview.html` (`?empty` and `?stale` preset its toggles; `?admin` shows the
    admin card and `?user` shows it as a non-admin; `?menu=<object ID>` opens that
    alert's snooze or suspend menu, and `?until` its date and time field). Not
    shipped.
- **`assets/`** — the icon's SVG master, the 32 px README header icon, and
  `screenshots/`, the README's pictures of the cards: the dev preview's theme
  columns (without its toolbar), at 1.5× scale, quantized to 256 colours.
- **`tests/`** — smoke tests using `pytest-homeassistant-custom-component`.
- **`scripts/test-against-ha.sh`** — runs the tests against an older HA (see
  Testing).
- **`plugins/alert-redux/`** — the **agent skill** (spec §20, 1.0.0): how-tos and
  best practices for agents configuring, operating, and building on Alert Redux
  (`skills/alert-redux/SKILL.md` and its reference files), packaged as a Claude
  Code plugin (`.claude-plugin/plugin.json`). **`.claude-plugin/marketplace.json`**
  at the root makes the repository a plugin marketplace that lists it.

## Card development

```sh
cd frontend
npm ci
npm run typecheck
npm run build      # or: npm run watch
```

`build.mjs` writes the bundle into `custom_components/alert_redux/frontend/`, injecting
the manifest version as `__CARD_VERSION__`. **Commit the rebuilt bundle with any change
to the card source** (and after bumping the manifest version) — HACS installs straight
from the repo, so there is no build step on the user's side. The Frontend CI workflow
fails if the committed bundle differs from a fresh build.

Lit components use `static properties` + `declare` fields rather than decorators, which
keeps the build free of decorator-transform configuration.

## Testing

```sh
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

The test plugin tracks current HA, which needs Python 3.14; keep
`requirements_test.txt` close to the HA version actually in use, since HA behaviour
changes between releases (spec §11.5 records one that bit us). CI also runs HACS
validation and hassfest. The voice tests set up `conversation`, so
`requirements_test.txt` also pins its components' requirements (`hassil` and
the rest); when bumping the plugin, update them from the new HA's manifests
(`conversation`, `assist_pipeline`, `tts`, `ffmpeg`, `stt`, `wake_word`).

CI tests only the current HA. The minimum (`hacs.json`, 2026.6) and the paths
only older HA takes (LLM tools before 2026.8, `admin_only` before 2026.9) are
tested locally with `scripts/test-against-ha.sh <plugin version>`, which builds
`.venvs/<version>` for that `pytest-homeassistant-custom-component` release (with
packages as of its release date) and runs pytest there: `0.13.340` is HA 2026.6,
`0.13.357` is HA 2026.8. Run it before a release that touches HA APIs. Before
writing a workaround for an older HA, find with it how far the minimum would
have to move, and take the options to the user.

Checks of behaviour across a restart on the real HA instance don't get restarts of
their own: they're set up at the end of a real-HA run and checked after the next
install restart. `docs/restart-checks.md` is the ledger of pending and done checks,
with a note on this instance's restart timing. Read it at the start of every
real-HA run.

The real instance has a permanent alerting and notification test rig, older than
Alert Redux and moved over to it unchanged:

- **Test Alert** (`alert_redux.test_alert`): a state alert, firing while
  `input_boolean.test_alert` is on.
- **Test Event Alert** (`alert_redux.test_event_alert`): a bus event alert, fired
  by pressing `input_button.test_event_alert`.

Both send to the Quiet and Office Only groups. Use them freely in real-HA runs,
but don't change their configuration permanently (restore anything a test
changes), and never delete them or their helpers when cleaning up a run's test
entities.

## The agent skill

The skill in `plugins/alert-redux/skills/alert-redux/` is user-facing
documentation for agents. **Update it with any change to the forms, actions,
events, attributes, errors, Repairs issues, or card options, and with any
change in behaviour it describes.** `tests/test_skill.py` fails when the skill
leaves out a name the code defines, or names an event or card option that
doesn't exist, but it can't check that the descriptions are still right. Write
it in terms of Home Assistant itself (subentry flows, actions, events), with
HA-MCP specifics only in `ha-mcp.md`. Keep `SKILL.md` under 500 lines, with
every reference file linked from it.

## Versioning

`manifest.json` `version` is the release version (semantic; bump on release, then
rebuild the card so its reported version and resource cache-buster match).
`config_flow.VERSION` / `MINOR_VERSION` are the config entry schema version and are
only bumped for changes to stored entry data/options — they are unrelated.
The plugin's `version` (`plugins/alert-redux/.claude-plugin/plugin.json`) follows
the manifest's, so a release also updates installed skills; `tests/test_skill.py`
checks they match.
