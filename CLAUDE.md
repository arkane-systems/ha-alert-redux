# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration, **Alert Redux** (domain `alert_redux`), intended to
replace the deprecated built-in `alert` integration, plus the Lovelace card(s) for using
it. Both live in this one repository and are delivered by a single HACS *integration*
install: the card bundle ships inside the integration package and the integration serves
and registers it itself.

The project is at the scaffolding stage: the integration sets up (single-instance
config entry) and registers a placeholder card, but no alerting behavior exists yet.

## Layout

- **`custom_components/alert_redux/`** — the integration (what HACS installs).
  - `__init__.py` — config entry setup/unload.
  - `config_flow.py` — single-instance config flow (`single_config_entry` in the
    manifest makes HA enforce the one-instance rule).
  - `frontend.py` — serves `frontend/` via a static path and registers the card as a
    storage-mode Lovelace resource with a `?v=<manifest version>` cache-buster, updating
    an existing resource in place on upgrade; falls back to `add_extra_js_url` when the
    resource collection isn't available (YAML-mode dashboards).
  - `frontend/alert-redux-card.js` — **build output, do not edit by hand.**
  - `strings.json` / `translations/en.json` — keep in sync manually; `en.json` is
    `strings.json` with `[%key:...%]` references resolved to literal text.
- **`frontend/`** — card source (TypeScript + Lit), bundled with esbuild.
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
