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
    CLEAR_ADVICE,
    CLEAR_NOTIFICATION,
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
    "supersedes_generator", "manual_off",
} | UNSUPPORTED.keys()
# A template that only compares one entity's state with a value, which a state
# alert says directly: {{ states('x') == 'v' }} or {{ is_state('x', 'v') }}.
_Q = r"""(?:'([^']*)'|"([^"]*)")"""
STATE_TEMPLATES = (
    re.compile(
        r"^\{\{\s*states\(\s*" + _Q + r"\s*\)\s*==\s*" + _Q + r"\s*\}\}$"
    ),
    re.compile(r"^\{\{\s*is_state\(\s*" + _Q + r"\s*,\s*" + _Q + r"\s*\)\s*\}\}$"),
)
ENTITY_ID = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def _alert2_id(domain: Any, name: Any) -> str:
    """Return the entity ID Alert2 gives an alert."""
    return f"alert2.{slugify(str(domain))}_{slugify(str(name))}"


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
                _alert2_id(alert["domain"], alert["name"]),
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


class _Skip(Exception):
    """An alert that can't be converted."""


def _template_text(value: Any) -> str:
    """Return a condition as template text: YAML's true and false are booleans."""
    if isinstance(value, bool):
        return "{{ true }}" if value else "{{ false }}"
    return str(value)


def _state_comparison(template: str) -> tuple[str, str] | None:
    """Return the entity and state a template only compares, if it does."""
    for pattern in STATE_TEMPLATES:
        if match := pattern.match(template.strip()):
            groups = match.groups()
            entity, state = (groups[0] or groups[1]), (groups[2] or groups[3] or "")
            if ENTITY_ID.match(entity or ""):
                return entity, state
    return None


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
                result[f"{side}_template"] = _rewrite(
                    _template_text(config[f"condition_{side}"])
                )
            if config.get(f"trigger_{side}"):
                result[f"{side}_triggers"] = as_list(config[f"trigger_{side}"])
        has_on = "on_template" in result or "on_triggers" in result
        has_off = "off_template" in result or "off_triggers" in result
        if has_on and not has_off:
            # Alert2 lets such an alert be turned off by hand; an on/off alert
            # needs both sides, so it follows its condition (or trigger) alone.
            if "on_template" in result:
                report.warn(
                    label,
                    "has no off condition (turned off by hand, manual_off): "
                    "converted to a template alert, which ends when its condition "
                    "does",
                )
                if result.get("on_triggers"):
                    report.warn(label, "its on triggers were dropped")
                return {"kind": "template", "template": result["on_template"]}
            report.warn(
                label,
                "has no off condition (turned off by hand, manual_off): converted "
                "to a trigger alert, which ends after its duration",
            )
            return {"kind": "trigger", "triggers": result["on_triggers"]}
        if not has_on:
            raise _Skip("it has an off criterion but no on criterion")
        return result
    if "trigger" in config:
        result = {"kind": "trigger", "triggers": as_list(config["trigger"])}
        if config.get("condition"):
            result["condition"] = _rewrite(config["condition"])
        return result
    condition = config.get("condition")
    if condition is None or condition == "":
        # An event alert, reported by alert2.report: the closest thing is a
        # manual alert that ends by itself.
        report.notes.append(
            f"{label}: an event alert fired by alert2.report becomes a manual alert "
            "that ends by itself; fire it with alert_redux.fire"
        )
        return {"kind": "manual", "ends_by_itself": True}
    if isinstance(condition, str) and ENTITY_ID.match(condition.strip()):
        return {"kind": "state", "entity_id": condition.strip(), "target_state": "on"}
    text = _template_text(condition)
    if comparison := _state_comparison(text):
        report.notes.append(
            f"{label}: its template only compares {comparison[0]} with "
            f"{comparison[1]!r}, so it's a state alert"
        )
        return {
            "kind": "state",
            "entity_id": comparison[0],
            "target_state": comparison[1],
        }
    return {"kind": "template", "template": _rewrite(text)}


def _supersedes(
    config: dict[str, Any],
    label: str,
    report: Report,
    ids: dict[str, str],
) -> list[dict[str, Any]]:
    result = []
    for item in as_list(config.get("supersedes")):
        if isinstance(item, dict) and "domain" in item and "name" in item:
            old = _alert2_id(item["domain"], item["name"])
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


# Alert2's generator variables, and what stands for them here: the target entity
# (its ID), which `target` is.
GENERATOR_VARIABLES = {"genElem": "target", "genEntityId": "target"}


def _generator_text(value: Any) -> Any:
    """Return generator-body text with Alert2's generator variables as the target."""
    if isinstance(value, str):
        return re.sub(
            r"\b(" + "|".join(GENERATOR_VARIABLES) + r")\b",
            lambda m: GENERATOR_VARIABLES[m.group(1)],
            value,
        )
    if isinstance(value, list):
        return [_generator_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _generator_text(item) for key, item in value.items()}
    return value


def _glob(regex: str) -> str | None:
    """Return a regular expression as an entity ID glob, if it's only literal
    text, `.*` (possibly as a group), and dots."""
    text = regex.replace("(.*)", ".*")
    if re.search(r"[\\^$+?()\[\]{}|*]", text.replace(".*", "")):
        return None
    return text.replace(".*", "*")


def _selection(generator: Any) -> tuple[dict[str, Any], str]:
    """Return the targets that match what a generator selects, as far as they can
    be read from it, and a sentence about it."""
    if isinstance(generator, list):
        return (
            {"labels": ["<a label on the entities>"]},
            f"Alert2 generated it for each of {generator!r}. If these name entities, "
            "give those entities a label and use it; if they're values (limits, "
            "say), make one fixed alert for each instead",
        )
    text = str(generator)
    targets: dict[str, Any] = {}
    if domain := re.search(r"states\.(\w+)", text):
        targets["domains"] = [domain.group(1)]
    regex = re.search(r"(?:'match'|\"match\")\s*,\s*['\"]([^'\"]+)['\"]", text) or re.search(
        r"entity_regex\(\s*['\"]([^'\"]+)['\"]", text
    )
    note = ""
    if regex:
        glob = _glob(regex.group(1))
        if glob:
            targets["pattern"] = glob
        else:
            note = f" Its pattern {regex.group(1)!r} isn't a plain glob; rewrite it as one."
    if not targets:
        targets["labels"] = ["<a label on the entities>"]
    return (
        targets,
        f"Alert2 generated it from the template {text!r}, read here as the targets "
        f"below; check them.{note}",
    )


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
    if config.get("supersedes"):
        report.warn(label, "supersession in a generator isn't carried over")
    generator: dict[str, Any] = {
        "name": _humanise(str(config.get("generator_name") or config["name"])),
    }
    parts = [str(config.get("domain", "")), str(config["name"])]
    if any(is_template(part) for part in parts):
        where_named = (
            f" Its name was the template {' '.join(parts)!r}; Alert Redux names "
            "each alert after its target unless you set a name template."
        )
    else:
        where_named = ""
    targets, where = _selection(config.get("generator"))
    generator |= settings | {"targets": targets}
    report.suggest(
        label,
        f"as a generator (kind {settings['kind']}). {where.rstrip('.')}.{where_named} "
        "Alert Redux chooses targets by label, area, domain, device class, or an "
        "entity ID glob:",
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
        _alert2_id(a["domain"], a["name"]): "alert_redux." + slugify(names[i])
        for i, a in enumerate(config_alerts)
    }
    seen_ids: set[str] = set()
    defaults_warned: set[str] = set()
    if isinstance(data, dict) and (data.get("alert2") or data).get("tracked"):
        report.notes.append(
            "The tracked: section (Alert2's internal alerts and alert2.report "
            "events) isn't converted; Alert Redux logs its own problems instead"
        )
    out: list[dict[str, Any]] = []
    for index, alert in enumerate(config_alerts):
        config = {**BUILT_IN_DEFAULTS, **defaults, **alert}
        is_generator = "generator" in config or "generator_name" in config
        label = (
            f"generator {config.get('generator_name') or alert['name']}"
            if is_generator
            else _alert2_id(alert["domain"], alert["name"])
        )
        if not is_generator:
            if ids[label] in seen_ids:
                report.warn(label, f"its entity ID {ids[label]} clashes with another's")
            seen_ids.add(ids[label])

        definition: dict[str, Any] = {"name": names[index]}
        try:
            definition.update(_condition(config, label, report))
        except _Skip as err:
            report.skip(label, str(err))
            continue
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
            if config.get(source) == CLEAR_NOTIFICATION and source == "done_message":
                report.warn(label, CLEAR_ADVICE)
            elif config.get(source):
                definition[target] = _rewrite(config[source])
        if "notifier" in config:
            group_names = groups.groups_for(
                as_list(config["notifier"]), report, label
            )
            # An explicit null or empty list means nobody. Notifiers that all had
            # to be dropped leave the alert on the default groups instead.
            if group_names or not as_list(config["notifier"]):
                definition["notifier_groups"] = group_names
        if config.get("done_notifier") is False:
            report.warn(label, "done_notifier: false has no equivalent; done messages are sent")
        elif isinstance(config.get("done_notifier"), (str, list)):
            report.warn(label, "done_notifier groups have no equivalent; dropped")
        if throttle := config.get("throttle_fires_per_mins"):
            definition["throttle"] = list(throttle)
        # Reminders until acknowledged, even once it has stopped firing, is a
        # latching alert (spec §10). ack_reminders_only (an acknowledged alert
        # still sends its done message) is what Alert Redux always does (§9.7).
        if config.get("ack_required"):
            definition["latching"] = True
        if relationships := _supersedes(config, label, report, ids):
            definition["supersedes"] = relationships
        for key, advice in UNSUPPORTED.items():
            if not config.get(key):
                continue
            if key in alert:
                report.warn(label, f"{key} dropped: {advice}")
            elif key not in defaults_warned:
                defaults_warned.add(key)
                report.warn("defaults", f"{key} dropped: {advice}")
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
