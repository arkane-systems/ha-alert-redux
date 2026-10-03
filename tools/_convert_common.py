"""Shared parts of the converters from other alerting setups to an Alert Redux
import file (spec §16, §17).

Home Assistant isn't needed: these tools use only the standard library and
PyYAML, and write the file `alert_redux.import` takes. They are not part of the
integration.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
import json
import re
import sys
from typing import Any

import yaml

FILE_FORMAT = "alert_redux"
FILE_VERSION = 1

# Tags that configuration.yaml uses, which we can't resolve: kept as text.
_OPAQUE_TAGS = ("!secret", "!include", "!include_dir_list", "!include_dir_named",
                "!include_dir_merge_list", "!include_dir_merge_named", "!env_var",
                "!input")


class _Loader(yaml.SafeLoader):
    """A loader that accepts Home Assistant's tags as opaque text."""


def _opaque(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> str:
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    else:
        value = ""
    return f"{node.tag} {value}".strip()


for _tag in _OPAQUE_TAGS:
    _Loader.add_multi_constructor(_tag, _opaque)


def load_yaml(text: str) -> Any:
    """Parse YAML, leaving Home Assistant's `!secret`, `!include` and similar
    tags as text."""
    return yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader subclass


def is_opaque(value: Any) -> bool:
    """Return whether a value is a tag the loader couldn't resolve."""
    return isinstance(value, str) and value.split(" ", 1)[0] in _OPAQUE_TAGS


def is_template(value: Any) -> bool:
    """Return whether text contains a Jinja template."""
    return isinstance(value, str) and ("{{" in value or "{%" in value)


def slugify(text: str) -> str:
    """Return text as Home Assistant makes an entity ID's object ID from a name."""
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return text.strip("_")


@dataclass
class Report:
    """What a conversion did that the user should know about."""

    converted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    groups: set[str] = field(default_factory=set)

    def warn(self, alert: str, text: str) -> None:
        """Record something that wasn't converted exactly."""
        self.warnings.append(f"{alert}: {text}")

    def skip(self, alert: str, text: str) -> None:
        """Record an alert that wasn't converted."""
        self.skipped.append(f"{alert}: {text}")

    def format(self) -> str:
        """Return the report as text."""
        lines = [f"Converted {len(self.converted)} alert(s)."]
        for title, items in (
            ("Not converted", self.skipped),
            ("Warnings", self.warnings),
            ("Notes", self.notes),
        ):
            if items:
                lines.append(f"{title}:")
                lines.extend(f"  - {item}" for item in items)
        if self.groups:
            lines.append(
                "Notifier groups to create before importing (names match "
                "ignoring case): " + ", ".join(sorted(self.groups))
            )
        lines.append(
            "Check the file with alert_redux.import and dry_run: true before "
            "importing it."
        )
        return "\n".join(lines)


class GroupMap:
    """Maps old notifiers (notify services) to Alert Redux notifier group names.

    Without a mapping, a notifier is a group of the same name, without its
    `notify.` prefix. A mapping value may be a name, a list of names, or empty
    (the notifier is dropped, so the alert uses the default groups).
    """

    def __init__(self, mapping: Mapping[str, Any] | None = None) -> None:
        self._mapping = {
            self._key(key): ([value] if isinstance(value, str) else list(value or []))
            for key, value in (mapping or {}).items()
        }

    @staticmethod
    def _key(notifier: str) -> str:
        return str(notifier).strip().lower().removeprefix("notify.")

    def groups_for(
        self, notifiers: Iterable[str], report: Report, alert: str
    ) -> list[str]:
        """Return the group names for an alert's notifiers."""
        groups: list[str] = []
        for notifier in notifiers:
            if not isinstance(notifier, str) or is_template(notifier):
                report.warn(
                    alert, f"notifier {notifier!r} isn't a plain service name; dropped"
                )
                continue
            key = self._key(notifier)
            for group in self._mapping.get(key, [key]):
                if group.lower() not in (g.lower() for g in groups):
                    groups.append(group)
        report.groups.update(groups)
        return groups


def as_list(value: Any) -> list[Any]:
    """Return a value as a list: a missing one is empty, a single one is wrapped."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def seconds_duration(seconds: Any) -> dict[str, Any]:
    """Return a number of seconds as an import duration."""
    value = float(seconds)
    return {"seconds": int(value) if value.is_integer() else value}


def reminder_schedule(value: Any) -> list[float] | None:
    """Return a reminder interval (minutes, or a list of them) as a schedule."""
    if value is None or value is False:
        return None
    return [
        int(item) if float(item).is_integer() else float(item) for item in as_list(value)
    ]


def envelope(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return alert definitions as an import file."""
    return {
        "format": FILE_FORMAT,
        "version": FILE_VERSION,
        "alerts": alerts,
        "generators": [],
    }


Converter = Callable[[Any, GroupMap], "tuple[list[dict[str, Any]], Report]"]


def main(argv: list[str] | None, description: str, convert: Converter) -> int:
    """Run a converter as a command: read YAML, write an import file, report."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", help="YAML file to convert, or - for standard input")
    parser.add_argument("-o", "--output", help="file to write (default: standard output)")
    parser.add_argument(
        "--group-map",
        help="YAML file mapping old notifiers to notifier group names",
    )
    parser.add_argument("--format", choices=("yaml", "json"), default="yaml")
    parser.add_argument(
        "--strict", action="store_true", help="fail, writing nothing, on any warning"
    )
    args = parser.parse_args(argv)

    try:
        text = sys.stdin.read() if args.input == "-" else open(args.input).read()  # noqa: SIM115
        data = load_yaml(text)
        mapping = None
        if args.group_map:
            with open(args.group_map) as handle:
                mapping = load_yaml(handle.read())
            if mapping is not None and not isinstance(mapping, dict):
                raise ValueError("the group map must be a mapping")
        alerts, report = convert(data, GroupMap(mapping))
    except (OSError, yaml.YAMLError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    print(report.format(), file=sys.stderr)
    if args.strict and (report.warnings or report.skipped):
        print("error: --strict, and there are warnings", file=sys.stderr)
        return 1
    document = envelope(alerts)
    rendered = (
        json.dumps(document, indent=2)
        if args.format == "json"
        else yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    )
    if args.output:
        with open(args.output, "w") as handle:
            handle.write(rendered)
    else:
        print(rendered)
    return 0
