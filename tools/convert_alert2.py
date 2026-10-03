#!/usr/bin/env python3
"""Convert Alert2 alerts to an Alert Redux import file.

    convert_alert2.py alerts.yaml -o alerts-redux.yaml [--group-map map.yaml]

The input is an `alert2:` block (or a configuration.yaml that has one), a single
alert's YAML as the Alert Manager card shows it, or a list of such alerts.
"""

from __future__ import annotations

import os
import re
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
    seconds_duration,
    slugify,
)

PRIORITIES = {"low": "notice", "medium": "warning", "high": "critical"}
# Alert2's template variables, and Alert Redux's for the same things.
VARIABLES = {"on_time_str": "duration", "on_secs": "duration_seconds"}
# Alert2's own defaults, under any `defaults:` and the alert's own settings.
BUILT_IN_DEFAULTS = {"priority": "low"}

# Options with no equivalent, and what to do instead.
UNSUPPORTED = {
    "early_start": "Alert Redux waits for its inputs after startup (spec §15)",
    "manual_on": "use a manual alert",
    "manual_off": "use a manual alert",
    "actions_on": "use an automation on the alert's events",
    "title": "notifications are titled with the alert's name",
    "target": "set it on the notifier group's members",
    "data": "set it on the notifier group's members",
    "annotate_messages": "Alert Redux doesn't annotate messages",
    "persistent_notifier_grouping": "set persistent members' options on the group",
    "ack_reminder_message": "Alert Redux has one reminder message",
    "summary_notifier": "summaries go to the groups' own quiet hours (spec §9.9)",
    "supersede_debounce_secs": "the debounce is a global option",
}
KNOWN = {
    "domain", "name", "friendly_name", "condition", "condition_on", "condition_off",
    "trigger", "trigger_on", "trigger_off", "threshold", "delay_on_secs", "priority",
    "reminder_frequency_mins", "message", "done_message", "reminder_message",
    "display_msg", "icon", "notifier", "done_notifier", "throttle_fires_per_mins",
    "ack_required", "ack_reminders_only", "supersedes", "generator", "generator_name",
    "supersedes_generator",
} | UNSUPPORTED.keys()
ENTITY_ID = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def _alerts_from(data: Any) -> tuple[dict[str, Any], list[Any]]:
    """Return the defaults and the alerts in whatever shape was given."""
    if isinstance(data, dict) and "alert2" in data:
        data = data["alert2"]
    if is_opaque(data):
        raise ValueError(f"the alerts are {data!r}, which can't be followed")
    if isinstance(data, list):
        return {}, data
    if not isinstance(data, dict):
        raise ValueError("expected an alert2: block, an alert, or a list of alerts")
    if "domain" in data and "name" in data:
        return {}, [data]
    if "alerts" in data:
        return data.get("defaults") or {}, as_list(data["alerts"])
    raise ValueError("expected an alert2: block, an alert, or a list of alerts")


def _rewrite(text: Any) -> Any:
    """Return a template with Alert2's variables as Alert Redux's."""
    if not is_template(text):
        return text
    return re.sub(
        r"\b(" + "|".join(VARIABLES) + r")\b", lambda m: VARIABLES[m.group(1)], text
    )


def _humanise(name: str) -> str:
    text = name.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def _display_name(domain: Any, name: Any) -> str:
    """Return an alert's name from its domain and name, which together are what
    identify it in Alert2 (its entity ID is alert2.<domain>_<name>)."""
    return f"{_humanise(str(domain))} {_humanise(str(name))}"


def _names(alerts: list[dict[str, Any]], report: Report) -> dict[int, str]:
    """Return a name for each alert (by position): its friendly name where it has
    a plain one, else its domain and name. Friendly names that clash are
    prefixed with the domain."""
    names: dict[int, str] = {}
    for index, alert in enumerate(alerts):
        friendly = alert.get("friendly_name")
        if friendly and not is_template(friendly):
            names[index] = str(friendly)
            continue
        if friendly:
            report.warn(
                f"alert2.{alert['domain']}_{alert['name']}",
                "friendly_name is a template; named from the domain and name",
            )
        names[index] = _display_name(alert["domain"], alert["name"])
    counts: dict[str, int] = {}
    for name in names.values():
        counts[name.lower()] = counts.get(name.lower(), 0) + 1
    for index, alert in enumerate(alerts):
        if counts[names[index].lower()] > 1:
            names[index] = f"{_humanise(str(alert['domain']))} {names[index]}"
    return names


def _condition(config: dict[str, Any], label: str, report: Report) -> dict[str, Any]:
    """Return the kind and its fields for an alert's condition or trigger."""
    if "threshold" in config:
        t = config["threshold"] or {}
        value = t.get("value")
        result: dict[str, Any] = {"kind": "threshold"}
        if isinstance(value, str) and ENTITY_ID.match(value.strip()):
            result["entity_id"] = value.strip()
        else:
            result["value_template"] = value
        for key in ("minimum", "maximum"):
            if t.get(key) is not None:
                result[key] = t[key]
        if t.get("hysteresis"):
            result["hysteresis"] = t["hysteresis"]
        return result
    if "condition_on" in config or "condition_off" in config or (
        "trigger_on" in config or "trigger_off" in config
    ):
        result = {"kind": "on_off"}
        for side in ("on", "off"):
            if config.get(f"condition_{side}"):
                result[f"{side}_template"] = _rewrite(config[f"condition_{side}"])
            if config.get(f"trigger_{side}"):
                result[f"{side}_triggers"] = as_list(config[f"trigger_{side}"])
        return result
    if "trigger" in config:
        result = {"kind": "trigger", "triggers": as_list(config["trigger"])}
        if config.get("condition"):
            result["condition"] = _rewrite(config["condition"])
        return result
    condition = config.get("condition")
    if condition is None:
        # An event alert, reported by alert2.report: the closest thing is a
        # manual alert that ends by itself.
        report.notes.append(
            f"{label}: an event alert fired by alert2.report becomes a manual alert "
            "that ends by itself; fire it with alert_redux.fire"
        )
        return {"kind": "manual", "ends_by_itself": True}
    if isinstance(condition, str) and ENTITY_ID.match(condition.strip()):
        return {"kind": "state", "entity_id": condition.strip(), "target_state": "on"}
    return {"kind": "template", "template": _rewrite(condition)}


def _supersedes(
    config: dict[str, Any],
    label: str,
    report: Report,
    ids: dict[str, str],
) -> list[dict[str, Any]]:
    result = []
    for item in as_list(config.get("supersedes")):
        if isinstance(item, dict) and "domain" in item and "name" in item:
            old = f"alert2.{item['domain']}_{item['name']}"
        elif isinstance(item, str) and ENTITY_ID.match(item.strip()):
            old = item.strip()
        else:
            report.warn(label, f"supersedes entry {item!r} not understood; dropped")
            continue
        new = ids.get(old)
        if new is None:
            report.warn(
                label,
                f"supersedes {old}, which isn't in this input; left as a reference "
                "to the alert_redux entity of that name",
            )
            # Where it would be, had it been converted: by its name.
            new = "alert_redux." + slugify(
                _display_name(item["domain"], item["name"])
                if isinstance(item, dict)
                else old.split(".", 1)[1]
            )
        result.append({"alert": new})
    return result


GENERATED_KINDS = {"state", "threshold", "template", "on_off"}


def _generator_text(value: Any) -> Any:
    """Return generator-body text with Alert2's genElem as the target."""
    if isinstance(value, str):
        return re.sub(r"\bgenElem\b", "target", value)
    if isinstance(value, list):
        return [_generator_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _generator_text(item) for key, item in value.items()}
    return value


def _suggest_generator(
    config: dict[str, Any], body: dict[str, Any], label: str, report: Report
) -> None:
    """Report a generator alert as not converted, with the settings of an Alert
    Redux generator that would match its body (spec §12.3)."""
    report.skip(
        label,
        "generator alerts aren't converted: Alert Redux's generators choose "
        "targets by criteria (see the suggested settings below)",
    )
    settings = _generator_text(
        {k: v for k, v in body.items() if k not in ("name", "entity_id", "supersedes")}
    )
    if settings["kind"] not in GENERATED_KINDS:
        report.warn(
            label,
            f"a {settings['kind']} alert can't be generated in Alert Redux; "
            "make fixed alerts instead",
        )
        return
    if "supersedes" in body:
        report.warn(label, "supersession in a generator isn't carried over")
    name = config.get("generator_name") or config["name"]
    generator = {
        "name": body["name"] if not config.get("generator_name") else _humanise(str(name)),
        **settings,
        "targets": {"labels": ["<choose the entities this generator covers>"]},
    }
    elements = config.get("generator")
    where = (
        "Alert2 generated it for these values of genElem, which are now the "
        f"target entity (`target`, `target_name`): {elements!r}"
        if isinstance(elements, list)
        else f"Alert2 generated it from the template {elements!r}, whose results are "
        "now the targets Alert Redux chooses by criteria"
    )
    report.suggest(
        label,
        f"as a generator (kind {settings['kind']}). {where}. Choose targets by "
        "label, area, domain, device class, or entity ID pattern; for a fixed list, "
        "give those entities a label and use it:",
        generator,
    )


def convert(
    data: Any, groups: GroupMap
) -> tuple[list[dict[str, Any]], Report]:
    """Return the import definitions for Alert2 configuration, and the report."""
    report = Report()
    defaults, raw = _alerts_from(data)
    config_alerts = [a for a in raw if isinstance(a, dict) and "domain" in a and "name" in a]
    for item in raw:
        if item not in config_alerts:
            report.skip(repr(item)[:40], "not an alert (it needs a domain and a name)")
    names = _names(config_alerts, report)
    # Alert2's entity IDs, to Alert Redux's, for supersession.
    ids = {
        f"alert2.{a['domain']}_{a['name']}": "alert_redux." + slugify(names[i])
        for i, a in enumerate(config_alerts)
    }
    seen_ids: set[str] = set()
    out: list[dict[str, Any]] = []
    for index, alert in enumerate(config_alerts):
        label = f"alert2.{alert['domain']}_{alert['name']}"
        config = {**BUILT_IN_DEFAULTS, **defaults, **alert}
        is_generator = "generator" in config or "generator_name" in config
        if not is_generator:
            if ids[label] in seen_ids:
                report.warn(label, f"its entity ID {ids[label]} clashes with another's")
            seen_ids.add(ids[label])

        definition: dict[str, Any] = {"name": names[index]}
        definition.update(_condition(config, label, report))
        if config["priority"] in PRIORITIES:
            definition["priority"] = PRIORITIES[config["priority"]]
        else:
            report.warn(label, f"unknown priority {config['priority']!r}; left at default")
        if config.get("delay_on_secs"):
            definition["delay_on"] = seconds_duration(config["delay_on_secs"])
        if (s := reminder_schedule(config.get("reminder_frequency_mins"))) is not None:
            definition["reminder_schedule"] = s
        for source, target in (
            ("message", "message"),
            ("done_message", "done_message"),
            ("reminder_message", "reminder_message"),
            ("display_msg", "display_message"),
            ("icon", "icon"),
        ):
            if config.get(source):
                definition[target] = _rewrite(config[source])
        if "notifier" in config:
            definition["notifier_groups"] = groups.groups_for(
                as_list(config["notifier"]), report, label
            )
        if config.get("done_notifier") is False:
            report.warn(label, "done_notifier: false has no equivalent; done messages are sent")
        elif isinstance(config.get("done_notifier"), (str, list)):
            report.warn(label, "done_notifier groups have no equivalent; dropped")
        if throttle := config.get("throttle_fires_per_mins"):
            definition["throttle"] = list(throttle)
        if config.get("ack_required") or config.get("ack_reminders_only"):
            report.warn(
                label,
                "ack_required / ack_reminders_only dropped: Alert Redux's "
                "equivalent, latching alerts (spec §10), isn't built yet",
            )
        if relationships := _supersedes(config, label, report, ids):
            definition["supersedes"] = relationships
        for key, advice in UNSUPPORTED.items():
            if config.get(key):
                report.warn(label, f"{key} dropped: {advice}")
        for key in config.keys() - KNOWN:
            report.warn(label, f"unknown option {key!r} ignored")
        if is_generator:
            _suggest_generator(config, definition, label, report)
            continue
        report.converted.append(label)
        out.append(definition)
    report.notes.append(
        "Alert2's priorities map low→notice, medium→warning, high→critical; "
        "Alert2's default (low) is applied where none was set."
    )
    return out, report


if __name__ == "__main__":
    sys.exit(main(None, __doc__.splitlines()[0], convert))
