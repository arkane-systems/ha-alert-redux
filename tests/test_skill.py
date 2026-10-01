"""The agent skill (plugins/alert-redux) against the code it describes.

The skill is documentation for agents, so it can drift from the integration
without anything failing. These tests check that it names every action, event,
attribute, form field, error, Repairs issue, and card option the code defines,
and that the events and card options it names exist.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import yaml

from custom_components.alert_redux import const

ROOT = Path(__file__).parent.parent
COMPONENT = ROOT / "custom_components" / "alert_redux"
PLUGIN = ROOT / "plugins" / "alert-redux"
SKILL = PLUGIN / "skills" / "alert-redux"


def _files() -> dict[str, str]:
    return {path.name: path.read_text() for path in sorted(SKILL.glob("*.md"))}


def _text() -> str:
    return "\n".join(_files().values())


def _named(text: str) -> set[str]:
    """Return everything the skill puts in backticks."""
    return set(re.findall(r"`([^`\n]+)`", text))


def _missing(expected: set[str], named: set[str]) -> list[str]:
    return sorted(item for item in expected if item not in named)


def _strings() -> dict:
    return json.loads((COMPONENT / "translations" / "en.json").read_text())


def test_frontmatter() -> None:
    """SKILL.md has the frontmatter the Agent Skills format requires."""
    text = (SKILL / "SKILL.md").read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match
    meta = yaml.safe_load(match.group(1))
    assert re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"])
    assert 0 < len(meta["description"]) <= 1024
    assert len(text.splitlines()) < 500


def test_reference_files_linked() -> None:
    """Every reference file is linked from SKILL.md, and every link resolves."""
    skill = (SKILL / "SKILL.md").read_text()
    links = set(re.findall(r"\]\(([\w-]+\.md)\)", skill))
    files = set(_files()) - {"SKILL.md"}
    assert links == files


def test_plugin_manifests() -> None:
    """The plugin follows the integration's version, and the marketplace lists it."""
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert plugin["version"] == manifest["version"]
    assert [entry["name"] for entry in market["plugins"]] == [plugin["name"]]
    assert market["plugins"][0]["source"] == "./plugins/alert-redux"


def test_actions() -> None:
    """Every action is described."""
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    expected = {f"alert_redux.{name}" for name in services}
    assert _missing(expected, _named(_text())) == []


def test_events() -> None:
    """Every event is described, and every event named exists."""
    named = _named(_text())
    assert _missing(set(const.EVENT_TYPES), named) == []
    events = {item for item in named if re.fullmatch(r"alert_redux_\w+", item)}
    assert sorted(events - set(const.EVENT_TYPES)) == []


def test_attributes() -> None:
    """Every attribute and event data key is described."""
    expected = {
        value
        for name, value in vars(const).items()
        if name.startswith("ATTR_") and isinstance(value, str)
    }
    assert _missing(expected, _named(_text())) == []


def test_form_fields() -> None:
    """Every field of every form, and every section, is described."""
    strings = _strings()
    expected: set[str] = set()
    steps = [
        step
        for subentry in strings["config_subentries"].values()
        for step_id, step in subentry["step"].items()
        if not step_id.startswith("reconfigure")
    ]
    steps += list(strings["options"]["step"].values())
    for step in steps:
        expected |= set(step.get("data", {}))
        expected |= set(step.get("menu_options", {}))
        for section_id, section in step.get("sections", {}).items():
            expected.add(section_id)
            expected |= set(section.get("data", {}))
    assert _missing(expected, _named(_text())) == []


def test_errors_and_issues() -> None:
    """Every form error, action error, and Repairs issue is described."""
    strings = _strings()
    expected = {
        key
        for subentry in strings["config_subentries"].values()
        for key in subentry.get("error", {})
    }
    expected |= set(strings.get("exceptions", {}))
    expected |= set(strings.get("issues", {}))
    assert _missing(expected, _named(_text())) == []


def test_card_options() -> None:
    """Every card option is described, and the examples use only real ones."""
    types = (ROOT / "frontend" / "src" / "types.ts").read_text()
    options: dict[str, set[str]] = {}
    for card, interface in (
        ("custom:alert-redux-card", "AlertReduxCardConfig"),
        ("custom:alert-redux-admin-card", "AlertReduxAdminCardConfig"),
    ):
        body = re.search(rf"interface {interface} \{{(.*?)\n\}}", types, re.DOTALL)
        assert body
        options[card] = set(re.findall(r"^\s+(\w+)\??:", body.group(1), re.MULTILINE))
    named = _named(_text())
    for card_options in options.values():
        assert _missing(card_options - {"type"}, named | _yaml_keys()) == []
    for block in re.findall(r"```yaml\n(.*?)```", _text(), re.DOTALL):
        config = yaml.safe_load(block)
        if isinstance(config, dict) and config.get("type") in options:
            assert set(config) <= options[config["type"]], config


def _yaml_keys() -> set[str]:
    """Return the top-level keys of the skill's YAML examples."""
    keys: set[str] = set()
    for block in re.findall(r"```yaml\n(.*?)```", _text(), re.DOTALL):
        config = yaml.safe_load(block)
        if isinstance(config, dict):
            keys |= set(config)
    return keys
