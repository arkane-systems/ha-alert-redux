"""Checks on the translation strings."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

COMPONENT = Path(__file__).parent.parent / "custom_components" / "alert_redux"
# The frontend reads translations as ICU messages, where braces are placeholders:
# anything else in braces (such as template syntax) shows as a translation error.
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def _strings(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}" if path else key)
    elif isinstance(value, str):
        yield path, value


@pytest.mark.parametrize("name", ["strings.json", "translations/en.json"])
def test_braces_are_placeholders(name: str) -> None:
    data = json.loads((COMPONENT / name).read_text())
    for path, text in _strings(data):
        remainder = PLACEHOLDER.sub("", text)
        assert "{" not in remainder and "}" not in remainder, f"{name}: {path}"


# Home Assistant's common strings, as they're resolved in translations/en.json.
COMMON = {
    "common::config_flow::abort::single_instance_allowed": (
        "Already configured. Only a single configuration possible."
    ),
    "common::config_flow::abort::reconfigure_successful": (
        "Re-configuration was successful"
    ),
}
REFERENCE = re.compile(r"\[%key:([a-z_:]+)%\]")


def resolve(strings: dict) -> dict:
    """Return strings.json with its references resolved, as en.json should be."""

    def lookup(key: str) -> str:
        if key in COMMON:
            return COMMON[key]
        value = strings
        for part in key.removeprefix("component::alert_redux::").split("::"):
            value = value[part]
        return REFERENCE.sub(lambda match: lookup(match.group(1)), value)

    def walk(value):
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return REFERENCE.sub(lambda match: lookup(match.group(1)), value)

    return walk(strings)


def test_en_matches_strings() -> None:
    strings = json.loads((COMPONENT / "strings.json").read_text())
    en = json.loads((COMPONENT / "translations" / "en.json").read_text())
    assert en == resolve(strings)
