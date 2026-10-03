#!/usr/bin/env python3
"""Convert the built-in `alert:` integration's YAML to an Alert Redux import file.

    convert_alert.py alert.yaml -o alerts.yaml [--group-map map.yaml]

The input is the `alert:` section (with or without the `alert:` line), or a whole
configuration.yaml that has one. Every alert becomes a state alert.
"""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _convert_common import (  # noqa: E402
    GroupMap,
    Report,
    as_list,
    is_opaque,
    is_template,
    main,
    reminder_schedule,
)


def _section(data: Any, report: Report) -> dict[str, Any]:
    """Return the alerts, by object ID, from whatever was given."""
    if isinstance(data, dict) and "alert" in data:
        data = data["alert"]
    if is_opaque(data):
        raise ValueError(
            f"the alert section is {data!r}, which can't be followed; "
            "convert that file itself"
        )
    if not isinstance(data, dict) or not data:
        raise ValueError("expected the `alert:` section: a mapping of alerts")
    return data


def convert(
    data: Any, groups: GroupMap
) -> tuple[list[dict[str, Any]], Report]:
    """Return the import definitions for an `alert:` section, and the report."""
    report = Report()
    alerts: list[dict[str, Any]] = []
    for object_id, config in _section(data, report).items():
        label = f"alert.{object_id}"
        if not isinstance(config, dict) or "entity_id" not in config:
            report.skip(label, "not an alert (it has no entity_id)")
            continue
        name = config.get("name") or object_id
        if is_template(name):
            report.warn(label, f"its name is a template ({name!r}); using the ID")
            name = object_id
        definition: dict[str, Any] = {
            "name": str(name),
            "kind": "state",
            "entity_id": config["entity_id"],
            "target_state": str(config.get("state", "on")),
        }
        if "can_acknowledge" in config:
            definition["acknowledgeable"] = bool(config["can_acknowledge"])
        if (schedule := reminder_schedule(config.get("repeat"))) is not None:
            definition["reminder_schedule"] = schedule
        for source, target in (("message", "message"), ("done_message", "done_message")):
            if config.get(source):
                definition[target] = config[source]
        if "notifiers" in config:
            definition["notifier_groups"] = groups.groups_for(
                as_list(config["notifiers"]), report, label
            )
        if config.get("skip_first"):
            report.warn(
                label,
                "skip_first has no equivalent; the first notification is sent at once"
                " (use a delay_on, or put the alert in a supersession, instead)",
            )
        if config.get("title"):
            report.warn(
                label,
                "title dropped: notifications are titled with the alert's name",
            )
        if config.get("data"):
            report.warn(
                label,
                "data dropped: set it on the notifier group's members instead",
            )
        for key in config.keys() - {
            "name", "entity_id", "state", "repeat", "can_acknowledge", "skip_first",
            "message", "done_message", "notifiers", "title", "data",
        }:
            report.warn(label, f"unknown option {key!r} ignored")
        report.converted.append(label)
        alerts.append(definition)
    report.notes.append("Priority is left at the default (warning).")
    return alerts, report


if __name__ == "__main__":
    sys.exit(main(None, __doc__.splitlines()[0], convert))
