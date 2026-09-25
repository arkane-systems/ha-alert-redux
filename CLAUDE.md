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
0.3.1 (the Alert Redux label, spec §11.5).

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
    rather than reloading the entry; announces alerts deleted since the last run.
  - `alert_redux.py` — the entity platform for our own domain, loaded by
    `EntityComponent.async_setup_entry`; adds one entity per alert subentry, linked
    with `config_subentry_id` so HA removes it with the subentry, and keeps the
    add-entities callback for alerts added later.
  - `entity.py` — `AlertEntity` (manual alerts; state, attributes, actions, events,
    persistence, and the rendered messages while firing) and `ConditionAlertEntity` (state/template kinds: watches a source,
    runs the delays and no-data grace period on one timer).
  - `model.py` — `AlertRuntime`, the HA-free state machine (including condition
    evaluation, `evaluate()`), its serialization, and the global `Settings`.
  - `sources.py` — condition inputs reporting true/false/no data: `StateSource`,
    `TemplateSource`, and `AndSource` for the extra condition.
  - `messages.py` — the message template context (`message_context`, shared with
    notifications from phase 4) and `MessageTracker`, which renders the on and display
    messages and re-renders them as the entities they read change.
  - `store.py` — `AlertStore`, the single persistent `Store` (no `RestoreEntity`);
    also remembers the card version the user was last told to refresh for, and the
    alerts label's ID.
  - `labels.py` — the "Alert Redux" label: created once; each alert is given it
    once, tracked by `labelled` in its stored record; never forced back.
    **Don't give alert entities a device**: since HA 2026.4 the device name is
    prefixed to their names and entity IDs (spec §11.5).
  - `config_flow.py` — single-instance config flow (`single_config_entry` in the
    manifest makes HA enforce the one-instance rule), the options flow (global
    defaults), and the alert subentry flow (a menu of kinds, then a form per kind).
  - `services.yaml`, `icons.json` — action definitions and icons.
  - `frontend.py` — serves `frontend/` via a static path and registers the card as a
    storage-mode Lovelace resource with a `?v=<manifest version>` cache-buster, updating
    an existing resource in place on upgrade; falls back to `add_extra_js_url` when the
    resource collection isn't available (YAML-mode dashboards). Also the
    `alert_redux/info` websocket command (the integration version, which the card
    compares with its own), and the "refresh your browser" notification, raised once
    per card version.
  - `frontend/alert-redux-card.js` — **build output, do not edit by hand.**
  - `strings.json` / `translations/en.json` — keep in sync manually; `en.json` is
    `strings.json` with `[%key:...%]` references resolved to literal text.
  - `brand/icon.png`, `brand/icon@2x.png` — integration icon (256 and 512 px),
    rendered from `assets/alert-redux-icon.svg`.
- **`frontend/`** — card source (TypeScript + Lit), bundled with esbuild.
  - `src/alert-redux-card.ts` — the main card element; `alerts.ts` (reading, sorting,
    and classifying alert entities), `format.ts`, `styles.ts`, `types.ts`.
  - `dev/preview.html` + `dev/preview.ts` — the card against a mock `hass`, in light
    and dark themes, with stub `ha-card`/`ha-icon`. `npm run preview` builds it into
    `dev/dist/` (gitignored); serve `frontend/dev/` over HTTP and open
    `preview.html` (`?empty` and `?stale` preset its toggles). Not shipped.
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
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

CI also runs HACS validation and hassfest.

## Versioning

`manifest.json` `version` is the release version (semantic; bump on release, then
rebuild the card so its reported version and resource cache-buster match).
`config_flow.VERSION` / `MINOR_VERSION` are the config entry schema version and are
only bumped for changes to stored entry data/options — they are unrelated.
