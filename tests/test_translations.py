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
