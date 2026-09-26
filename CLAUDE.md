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
event).

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
    the `Notifier` in place); announces alerts deleted since the last run.
  - `alert_redux.py` — the entity platform for our own domain, loaded by
    `EntityComponent.async_setup_entry`; adds one entity per alert subentry, linked
    with `config_subentry_id` so HA removes it with the subentry, and keeps the
    add-entities callback for alerts added later.
  - `entity.py` — `AlertEntity` (manual alerts; state, attributes, actions, events,
    persistence, and the rendered messages while firing; snoozing, disabling, and
    suspending, for every kind; supersession's on debounce, skipped reminders, and
    held done notifications), `ConditionAlertEntity`
    (state, on/off, threshold, template, and alert state kinds: watches its sources,
    judges them
    by the kind's rule in `_judge`, and runs the delays and no-data grace period on
    one timer), and `EventAlertEntity` (trigger and bus event kinds: fires on its
    triggers, for a duration). One-shot timers use `PointTimer`, and
    `_async_update_timers` sets them from the runtime's deadlines (reminder,
    snooze, suspension, event expiry). Kinds detach and re-attach their inputs on
    disable and enable through `_async_inputs_stopped` / `_async_inputs_started`.
  - `model.py` — `AlertRuntime`, the HA-free state machine (including condition
    evaluation, `evaluate()`, event durations, and on/off edges), its
    serialization, the threshold rule (`threshold_holds`), and the global
    `Settings`.
  - `sources.py` — condition inputs reporting their result or no data:
    `StateSource`, `TemplateSource`, `ThresholdSource` (a `Reading`), and
    `SourceSet`, which reports a kind's sources (and the extra condition) together.
  - `supersession.py` — `SupersessionGraph` (HA-free: relationships by entity ID,
    their transitive closure, `find_cycle`) and `Supersession`, the coordinator in
    `hass.data` that the entities share: it builds the graph from the entities'
    own configuration, answers `superseded_by` and the done-window decision, and
    passes on an alert starting or stopping firing, and propagates
    acknowledgements as pre-acknowledgements (the entities call it from
    `async_write_ha_state`). Pre-acknowledgements are kept by the source's
    unique ID. It also reports each alert's `broken_references`.
  - `summary.py` — `summarise` (HA-free: the counts, entity-ID lists, and
    highest priorities across all alerts) and `SummaryCoordinator` in
    `hass.data`, which each alert reports to (by unique ID) from
    `async_write_ha_state` and withdraws from when removed; it recomputes once
    per burst of reports and tells the sensors.
  - `sensor.py` — the summary sensors (spec §11.2), the one platform forwarded
    from the config entry. No device and no label; their entity IDs are set
    explicitly, whatever the translated names.
  - `logbook.py` — describes only the events that add to the logbook's state rows
    (spec §11.4). A describer can't drop a row, so events like `_acked`, which
    would duplicate their state rows, are simply not registered.
  - `triggers.py` — `TriggerWatcher`: attaches HA triggers once HA has started and
    after the startup delay, handing on each firing's variables made JSON-safe.
    Used by event alerts and on/off sides.
  - `messages.py` — the message template context (`message_context`, shared with
    notifications) and `MessageTracker`, which renders the on and display messages
    for the card and re-renders them as the entities they read change.
  - `notifications.py` — the alert side of notifying: which groups an alert sends
    to (its own, the defaults, or the fallback), rendering the on / reminder / done
    messages, and handing them to the notifier. Reminder timing lives in `model.py`
    (`AlertRuntime.next_reminder`, `next_reminder_slot`) and `entity.py`.
  - `notifier/` — the **self-contained notifier module** (spec §9.1): groups and
    members (`model.py`), delivery per member kind (`members.py`), the retry queue's
    records (`retry.py`), missing-action Repairs issues (`repairs.py`), and the
    `Notifier` (`__init__.py`). **It must not import anything Alert-Redux-specific**,
    so it can be extracted later; its owner passes in the store key and issue domain.
    It keeps its own `Store` (the retry queue). Named `notifier`, not `notify`: a
    `notify.py` would be loaded as a notify platform.
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
    collapsed notifications `section` flattened into the stored data), and the
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
- **`assets/`** — the icon's SVG master and the 32 px README header icon.
- **`tests/`** — smoke tests using `pytest-homeassistant-custom-component`.

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
validation and hassfest.

Checks of behaviour across a restart on the real HA instance don't get restarts of
their own: they're set up at the end of a real-HA run and checked after the next
install restart. `docs/restart-checks.md` is the ledger of pending and done checks,
with a note on this instance's restart timing. Read it at the start of every
real-HA run.

## Versioning

`manifest.json` `version` is the release version (semantic; bump on release, then
rebuild the card so its reported version and resource cache-buster match).
`config_flow.VERSION` / `MINOR_VERSION` are the config entry schema version and are
only bumped for changes to stored entry data/options — they are unrelated.
