"""Exporting and importing alert and generator definitions (spec §16).

A file is the definitions' stored configuration in a form that moves between
instances: each definition has its subentry ID (`id`) and its `name`, and
references that are instance-specific subentry IDs, notifier groups and other
generators, are written as names. Import validates everything first, with the
config flows' own checks (`validation.py`), and changes nothing unless every
definition passes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
import re

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from homeassistant.util.ulid import ulid_now

from .const import (
    CONDITION_KINDS,
    CONF_ACKNOWLEDGEABLE,
    CONF_AREA_FROM_TARGET,
    CONF_AREA_ID,
    CONF_PLACEMENT,
    CONF_ACTION,
    CONF_ALERT,
    CONF_ALERT_STATES,
    CONF_AREAS,
    CONF_ATTRIBUTE,
    CONF_BUTTON_SNOOZE_DURATION,
    CONF_BUTTONS,
    CONF_CONDITION,
    CONF_DELAY_OFF,
    CONF_DELAY_ON,
    CONF_DEVICE_CLASSES,
    CONF_DISPLAY_MESSAGE,
    CONF_DOMAINS,
    CONF_DONE_MESSAGE,
    CONF_DURATION,
    CONF_ENDS_BY_ITSELF,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_EVENT_TYPE,
    CONF_EXCLUDE,
    CONF_GENERATOR,
    CONF_HYSTERESIS,
    CONF_ICON,
    CONF_KIND,
    CONF_LABEL,
    CONF_LABELS,
    CONF_MAXIMUM,
    CONF_MESSAGE,
    CONF_MINIMUM,
    CONF_NAME_TEMPLATE,
    CONF_NO_DATA_GRACE,
    CONF_NOTIFIER_GROUPS,
    CONF_OFF_TEMPLATE,
    CONF_OFF_TRIGGERS,
    CONF_ON_TEMPLATE,
    CONF_ON_TRIGGERS,
    CONF_PATTERN,
    CONF_PRIORITY,
    CONF_PROPAGATION,
    CONF_PROXY_SNOOZE_BUTTON,
    CONF_PROXY_SWITCH,
    CONF_REMINDER_MESSAGE,
    CONF_REMINDER_SCHEDULE,
    CONF_REQUIRE_UNLOCK,
    CONF_SNOOZE_DURATION,
    CONF_SUBJECT_ENTITY,
    CONF_SUPERSEDES,
    CONF_TARGET_STATE,
    CONF_TARGETS,
    CONF_TEMPLATE,
    CONF_THROTTLE,
    CONF_TRIGGERS,
    CONF_USER_DISMISSABLE,
    CONF_VALUE_TEMPLATE,
    DOMAIN,
    EVENT_KINDS,
    GENERATOR_KINDS,
    SUBENTRY_ALERT,
    SUBENTRY_GENERATOR,
    SUBENTRY_NOTIFIER_GROUP,
    AlertKind,
    AlertState,
    Priority,
    Propagation,
)
from .validation import (
    Definitions,
    Member,
    async_check_alert,
    async_check_generator,
    check_generator_references,
    check_references,
)

FILE_FORMAT = "alert_redux"
FILE_VERSION = 1

KEY_FORMAT = "format"
KEY_VERSION = "version"
KEY_ALERTS = "alerts"
KEY_GENERATORS = "generators"
KEY_ID = "id"
KEY_NAME = "name"

# Import's problem codes, beyond the config flows' error keys.
PROBLEM_FILE = "invalid_file"
PROBLEM_INVALID = "invalid_definition"
PROBLEM_DUPLICATE = "duplicate_in_file"
PROBLEM_EXISTS = "exists"
PROBLEM_ID_IN_USE = "id_in_use"
PROBLEM_NAME_EXISTS = "name_exists"
PROBLEM_KIND_CHANGED = "kind_changed"
PROBLEM_ENTITY_ID_CLASH = "entity_id_clash"
PROBLEM_UNKNOWN_GROUP = "unknown_group"
PROBLEM_UNKNOWN_GENERATOR = "unknown_generator"
PROBLEM_RELATIONSHIP = "relationship_target"

ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_UNCHANGED = "unchanged"

_TYPE_NAMES = {SUBENTRY_ALERT: "alert", SUBENTRY_GENERATOR: "generator"}


# ---------------------------------------------------------------- export


def export_definitions(
    entry: ConfigEntry, subentry_ids: Iterable[str] | None = None
) -> dict[str, Any]:
    """Return the entry's alerts and generators (or the given subentries) as a file.

    Notifier groups, and generators that other generators supersede, are
    written by name.
    """
    wanted = None if subentry_ids is None else set(subentry_ids)
    groups = _titles(entry, SUBENTRY_NOTIFIER_GROUP)
    generators = _titles(entry, SUBENTRY_GENERATOR)
    alerts: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type not in _TYPE_NAMES:
            continue
        if wanted is not None and subentry_id not in wanted:
            continue
        data = _export_data(dict(subentry.data), groups, generators)
        if subentry.subentry_type == SUBENTRY_ALERT:
            # An alert's is the registry's, applied once when it was added.
            data.pop(CONF_PLACEMENT, None)
        definition = {KEY_ID: subentry_id, KEY_NAME: subentry.title, **data}
        if subentry.subentry_type == SUBENTRY_ALERT:
            alerts.append(definition)
        else:
            generated.append(definition)
    return {
        KEY_FORMAT: FILE_FORMAT,
        KEY_VERSION: FILE_VERSION,
        KEY_ALERTS: alerts,
        KEY_GENERATORS: generated,
    }


def _titles(entry: ConfigEntry, subentry_type: str) -> dict[str, str]:
    """Return the titles of the subentries of a type, by subentry ID."""
    return {
        subentry_id: subentry.title
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == subentry_type
    }


def _export_data(
    data: dict[str, Any], groups: Mapping[str, str], generators: Mapping[str, str]
) -> dict[str, Any]:
    """Return stored data with its instance-specific references as names."""
    data[CONF_KIND] = str(data[CONF_KIND])
    if CONF_NOTIFIER_GROUPS in data:
        data[CONF_NOTIFIER_GROUPS] = [
            groups[group] for group in data[CONF_NOTIFIER_GROUPS] if group in groups
        ]
    if CONF_SUPERSEDES in data:
        data[CONF_SUPERSEDES] = [
            {
                **rel,
                CONF_GENERATOR: generators.get(
                    rel[CONF_GENERATOR], rel[CONF_GENERATOR]
                ),
            }
            if CONF_GENERATOR in rel
            else dict(rel)
            for rel in data[CONF_SUPERSEDES]
        ]
    return data


# ---------------------------------------------------------------- schemas


_DURATION_UNITS = frozenset({"days", "hours", "minutes", "seconds", "milliseconds"})


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise vol.Invalid("expected a number")
    return value


def _non_negative(value: Any) -> float:
    if _number(value) < 0:
        raise vol.Invalid("must not be negative")
    return value


def _duration(value: Any) -> dict[str, Any]:
    """Return a duration as the duration selector stores it. A mapping of units is
    kept as it is; a number of seconds or an "HH:MM:SS" string is converted."""
    if isinstance(value, dict):
        if not value or not set(value) <= _DURATION_UNITS:
            raise vol.Invalid(
                f"a duration's units are {', '.join(sorted(_DURATION_UNITS))}"
            )
        return {unit: _non_negative(amount) for unit, amount in value.items()}
    try:
        total = cv.time_period(value).total_seconds()
    except vol.Invalid as err:
        raise vol.Invalid("expected a duration") from err
    if total < 0:
        raise vol.Invalid("must not be negative")
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    return {
        "hours": int(hours),
        "minutes": int(minutes),
        "seconds": int(seconds) if float(seconds).is_integer() else seconds,
    }


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise vol.Invalid("expected text")
    return value.strip()


def _limit(value: Any) -> str:
    """A threshold limit: a template, as the form stores it; a number is one."""
    if isinstance(value, str):
        return value.strip()
    return str(_number(value))


def _entity_list(value: Any) -> list[str]:
    return [cv.entity_id(item) for item in _list(value)]


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise vol.Invalid("expected a list")
    return value


def _trigger_list(value: Any) -> list[dict[str, Any]]:
    if not all(isinstance(item, dict) for item in _list(value)):
        raise vol.Invalid("expected a list of triggers")
    return value


def _schedule(value: Any) -> list[float]:
    minutes = [_number(item) for item in _list(value)]
    if any(item <= 0 for item in minutes):
        raise vol.Invalid("reminder intervals must be positive")
    return minutes


def _throttle(value: Any) -> list[float]:
    """A throttle: [count, minutes], or an empty list for none."""
    items = _list(value)
    if not items:
        return []
    if len(items) != 2:
        raise vol.Invalid("a throttle is [count, minutes]")
    count, minutes = _number(items[0]), _number(items[1])
    if count < 1 or int(count) != count or minutes <= 0:
        raise vol.Invalid(
            "a throttle needs a whole count of at least 1 and positive minutes"
        )
    return [int(count), minutes]


def _pattern(value: Any) -> str:
    pattern = _text(value)
    try:
        re.compile(pattern)
    except re.error as err:
        raise vol.Invalid(f"not a regular expression: {err}") from err
    return pattern


_BUTTON = vol.Schema(
    {
        vol.Required(CONF_LABEL): _text,
        vol.Required(CONF_ACTION): vol.Any(list, dict),
        vol.Optional(CONF_REQUIRE_UNLOCK): bool,
    }
)

# A generator's area and labels for its alerts (spec §11.6); the IDs are the
# registry's, which aren't checked, as for the targets'.
_PLACEMENT = vol.Schema(
    {
        vol.Optional(CONF_AREA_FROM_TARGET): bool,
        vol.Optional(CONF_AREA_ID): _text,
        vol.Optional(CONF_LABELS): [str],
    }
)

_ALERT_RELATIONSHIP = vol.Schema(
    {
        vol.Required(CONF_ALERT): cv.entity_id,
        vol.Optional(CONF_PROPAGATION): vol.In([p.value for p in Propagation]),
        vol.Optional(CONF_SNOOZE_DURATION): _duration,
    }
)
_GENERATOR_RELATIONSHIP = vol.Schema(
    {
        vol.Optional(CONF_ALERT): cv.entity_id,
        vol.Optional(CONF_GENERATOR): str,
        vol.Optional(CONF_PROPAGATION): vol.In([p.value for p in Propagation]),
        vol.Optional(CONF_SNOOZE_DURATION): _duration,
    }
)

_TARGETS = vol.Schema(
    {
        vol.Optional(CONF_LABELS): [str],
        vol.Optional(CONF_AREAS): [str],
        vol.Optional(CONF_DOMAINS): [str],
        vol.Optional(CONF_DEVICE_CLASSES): [str],
        vol.Optional(CONF_PATTERN): _pattern,
        vol.Optional(CONF_EXCLUDE): _entity_list,
    }
)

# Fields every alert and generator has. An alert's and generator's priority and
# acknowledgeability have the forms' defaults.
_COMMON: dict[Any, Any] = {
    vol.Optional(CONF_PRIORITY, default=Priority.WARNING.value): vol.In(
        [priority.value for priority in Priority]
    ),
    vol.Optional(CONF_ACKNOWLEDGEABLE, default=True): bool,
    vol.Optional(CONF_ICON): _text,
    vol.Optional(CONF_MESSAGE): _text,
    vol.Optional(CONF_DISPLAY_MESSAGE): _text,
    vol.Optional(CONF_REMINDER_MESSAGE): _text,
    vol.Optional(CONF_DONE_MESSAGE): _text,
    vol.Optional(CONF_BUTTONS): [_BUTTON],
    vol.Optional(CONF_BUTTON_SNOOZE_DURATION): _duration,
    vol.Optional(CONF_PROXY_SWITCH): bool,
    vol.Optional(CONF_PROXY_SNOOZE_BUTTON): bool,
    vol.Optional(CONF_NOTIFIER_GROUPS): [str],
    vol.Optional(CONF_REMINDER_SCHEDULE): _schedule,
    vol.Optional(CONF_THROTTLE): _throttle,
}

_CONDITION: dict[Any, Any] = {
    vol.Optional(CONF_CONDITION): _text,
    vol.Optional(CONF_DELAY_ON): _duration,
    vol.Optional(CONF_DELAY_OFF): _duration,
    vol.Optional(CONF_NO_DATA_GRACE): _duration,
}

_STATE_ENTITY = {vol.Required(CONF_ENTITY_ID): cv.entity_id}


def _kind_fields(kind: AlertKind, generator: bool) -> dict[Any, Any]:
    """Return the fields particular to an alert kind."""
    if kind is AlertKind.MANUAL:
        return {
            vol.Optional(CONF_USER_DISMISSABLE, default=False): bool,
            vol.Optional(CONF_ENDS_BY_ITSELF, default=False): bool,
            vol.Optional(CONF_DURATION): _duration,
        }
    if kind is AlertKind.STATE:
        return {
            **({} if generator else _STATE_ENTITY),
            vol.Required(CONF_TARGET_STATE): _text,
        }
    if kind is AlertKind.TEMPLATE:
        return {vol.Required(CONF_TEMPLATE): _text}
    if kind is AlertKind.ALERT_STATE:
        return {
            **({} if generator else {vol.Required(CONF_ALERT): cv.entity_id}),
            vol.Optional(CONF_ALERT_STATES, default=[AlertState.ACTIVE.value]): [
                vol.In([state.value for state in AlertState])
            ],
        }
    if kind is AlertKind.THRESHOLD:
        return {
            **({} if generator else {vol.Optional(CONF_ENTITY_ID): cv.entity_id}),
            vol.Optional(CONF_ATTRIBUTE): _text,
            vol.Optional(CONF_VALUE_TEMPLATE): _text,
            vol.Optional(CONF_MINIMUM): _limit,
            vol.Optional(CONF_MAXIMUM): _limit,
            vol.Optional(CONF_HYSTERESIS, default=0): _non_negative,
        }
    if kind is AlertKind.ON_OFF:
        return {
            vol.Optional(CONF_ON_TEMPLATE): _text,
            vol.Optional(CONF_ON_TRIGGERS): _trigger_list,
            vol.Optional(CONF_OFF_TEMPLATE): _text,
            vol.Optional(CONF_OFF_TRIGGERS): _trigger_list,
        }
    if kind is AlertKind.TRIGGER:
        return {vol.Required(CONF_TRIGGERS): _trigger_list}
    return {
        vol.Required(CONF_EVENT_TYPE): _text,
        vol.Optional(CONF_EVENT_DATA): dict,
    }


def _schema(kind: AlertKind, generator: bool) -> vol.Schema:
    """Return the schema for a definition's stored data (without its id and name)."""
    fields: dict[Any, Any] = {vol.Required(CONF_KIND): kind.value, **_COMMON}
    fields |= _kind_fields(kind, generator)
    if kind in CONDITION_KINDS:
        fields |= _CONDITION
    elif kind in EVENT_KINDS:
        fields |= {
            vol.Optional(CONF_CONDITION): _text,
            vol.Optional(CONF_DURATION): _duration,
        }
    if generator:
        fields |= {
            vol.Optional(CONF_NAME_TEMPLATE): _text,
            vol.Required(CONF_TARGETS): _TARGETS,
            vol.Optional(CONF_PLACEMENT): _PLACEMENT,
            vol.Optional(CONF_SUPERSEDES): [_GENERATOR_RELATIONSHIP],
        }
    else:
        fields |= {
            vol.Optional(CONF_SUBJECT_ENTITY): cv.entity_id,
            vol.Optional(CONF_SUPERSEDES): [_ALERT_RELATIONSHIP],
        }
    return vol.Schema(fields)


# Fields an empty list is meaningful for; elsewhere it, like None, "" and {},
# means the field isn't set.
_KEEP_EMPTY = frozenset(
    {CONF_NOTIFIER_GROUPS, CONF_REMINDER_SCHEDULE, CONF_THROTTLE, CONF_ALERT_STATES}
)


def _without_alert_placement(existing: ConfigSubentry, item: Item) -> dict[str, Any]:
    """Return an existing definition's data. An alert's placement isn't part of
    a definition (it was applied once, and lives in the registry)."""
    data = dict(existing.data)
    if item.subentry_type == SUBENTRY_ALERT:
        data.pop(CONF_PLACEMENT, None)
    return data


def _defaults(kind: AlertKind) -> dict[str, Any]:
    """Return the values a definition has when it leaves them out."""
    defaults: dict[str, Any] = {
        CONF_PRIORITY: Priority.WARNING.value,
        CONF_ACKNOWLEDGEABLE: True,
    }
    if kind is AlertKind.MANUAL:
        defaults |= {CONF_USER_DISMISSABLE: False, CONF_ENDS_BY_ITSELF: False}
    elif kind is AlertKind.THRESHOLD:
        defaults[CONF_HYSTERESIS] = 0
    elif kind is AlertKind.ALERT_STATE:
        defaults[CONF_ALERT_STATES] = [AlertState.ACTIVE.value]
    return defaults


def _plain(value: Any) -> Any:
    """Return a copy of service data as plain dicts and lists, to change freely."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _without_blanks(definition: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in definition.items()
        if value is not None
        and value != ""
        and not (value in ({}, []) and key not in _KEEP_EMPTY)
    }


def _stored(data: dict[str, Any]) -> dict[str, Any]:
    """Return validated data as the config flows store it: what's off or zero,
    where that is the default, is left out."""
    for key in (CONF_PROXY_SWITCH, CONF_PROXY_SNOOZE_BUTTON):
        if not data.get(key):
            data.pop(key, None)
    if CONF_BUTTON_SNOOZE_DURATION in data and not any(
        data[CONF_BUTTON_SNOOZE_DURATION].values()
    ):
        del data[CONF_BUTTON_SNOOZE_DURATION]
    if CONF_PLACEMENT in data:
        placement = data[CONF_PLACEMENT]
        # As the form stores it: the target's area, or a fixed one, and labels.
        if placement.get(CONF_AREA_FROM_TARGET):
            placement.pop(CONF_AREA_ID, None)
        else:
            placement.pop(CONF_AREA_FROM_TARGET, None)
        for key in (CONF_AREA_ID, CONF_LABELS):
            if not placement.get(key):
                placement.pop(key, None)
        if not placement:
            del data[CONF_PLACEMENT]
    relationships = []
    for rel in data.get(CONF_SUPERSEDES, []):
        rel = dict(rel)
        propagation = rel.get(CONF_PROPAGATION) or Propagation.NONE.value
        if propagation == Propagation.NONE.value:
            rel.pop(CONF_PROPAGATION, None)
        if propagation != Propagation.SNOOZE.value:
            rel.pop(CONF_SNOOZE_DURATION, None)
        relationships.append(rel)
    if relationships:
        data[CONF_SUPERSEDES] = relationships
    return data


# ---------------------------------------------------------------- import


@dataclass(frozen=True)
class Problem:
    """Something that stops an import."""

    code: str
    # "alert", "generator", or "file".
    kind: str
    name: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, str]:
        """Return the problem for a response."""
        problem = {"code": self.code, "type": self.kind}
        if self.name:
            problem["name"] = self.name
        if self.detail:
            problem["detail"] = self.detail
        return problem

    def __str__(self) -> str:
        subject = f"{self.kind} '{self.name}'" if self.name else self.kind
        return f"{subject}: {self.code}" + (f" ({self.detail})" if self.detail else "")


@dataclass
class Item:
    """One definition an import would create or update."""

    subentry_type: str
    subentry_id: str
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    action: str = ACTION_CREATE
    # Set when the definition is invalid, so that checks that rely on its data skip it.
    invalid: bool = False

    def as_dict(self) -> dict[str, str]:
        """Return the item for a response."""
        return {
            "type": _TYPE_NAMES[self.subentry_type],
            "id": self.subentry_id,
            "name": self.name,
        }


@dataclass
class ImportPlan:
    """What an import would do, and what stops it."""

    items: list[Item] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    def result(self, *, dry_run: bool = False) -> dict[str, Any]:
        """Return the plan for an action's response."""
        result: dict[str, Any] = {
            "created": [i.as_dict() for i in self.items if i.action == ACTION_CREATE],
            "updated": [i.as_dict() for i in self.items if i.action == ACTION_UPDATE],
            "unchanged": [
                i.as_dict() for i in self.items if i.action == ACTION_UNCHANGED
            ],
        }
        if dry_run:
            result["dry_run"] = True
        return result


_FILE_SCHEMA = vol.Schema(
    {
        vol.Required(KEY_FORMAT): FILE_FORMAT,
        vol.Required(KEY_VERSION): FILE_VERSION,
        vol.Optional(KEY_ALERTS, default=list): [dict],
        vol.Optional(KEY_GENERATORS, default=list): [dict],
    }
)


async def async_plan_import(
    hass: HomeAssistant,
    entry: ConfigEntry,
    payload: Any,
    *,
    overwrite: bool = False,
) -> ImportPlan:
    """Check an import file against the entry, and return what it would do.

    Every problem is collected, so that one refusal says everything that's wrong.
    """
    plan = ImportPlan()
    try:
        file = _FILE_SCHEMA(payload)
    except vol.Invalid as err:
        plan.problems.append(Problem(PROBLEM_FILE, "file", detail=str(err)))
        return plan

    # First pass: who each definition is, and whether it exists already.
    groups = {
        title.casefold(): sid
        for sid, title in _titles(entry, SUBENTRY_NOTIFIER_GROUP).items()
    }
    raw: list[tuple[Item, dict[str, Any], ConfigSubentry | None]] = []
    seen_ids: set[str] = set()
    seen_names: set[tuple[str, str]] = set()
    for subentry_type, key in (
        (SUBENTRY_ALERT, KEY_ALERTS),
        (SUBENTRY_GENERATOR, KEY_GENERATORS),
    ):
        for index, definition in enumerate(file[key]):
            found = _identify(
                plan, entry, subentry_type, index, definition, seen_ids, seen_names
            )
            if found is not None:
                raw.append(found)

    # Generators are named in other generators' relationships, and the names of
    # new ones are known only now.
    generator_ids = {
        title.casefold(): sid
        for sid, title in _titles(entry, SUBENTRY_GENERATOR).items()
    }
    for item, _, _ in raw:
        if item.subentry_type == SUBENTRY_GENERATOR:
            generator_ids[item.name.casefold()] = item.subentry_id

    # Second pass: each definition's data.
    for item, definition, existing in raw:
        _normalise(plan, item, definition, groups, generator_ids)
        if item.invalid:
            continue
        if existing is not None:
            if existing.data.get(CONF_KIND) != item.data[CONF_KIND]:
                plan.problems.append(
                    Problem(
                        PROBLEM_KIND_CHANGED, _TYPE_NAMES[item.subentry_type], item.name
                    )
                )
                item.invalid = True
            elif {
                **_defaults(AlertKind(item.data[CONF_KIND])),
                **_without_alert_placement(existing, item),
            } == item.data and existing.title == item.name:
                item.action = ACTION_UNCHANGED
            elif not overwrite:
                plan.problems.append(
                    Problem(
                        PROBLEM_EXISTS,
                        _TYPE_NAMES[item.subentry_type],
                        item.name,
                        "use overwrite to replace it",
                    )
                )
                item.invalid = True
            else:
                item.action = ACTION_UPDATE

    plan.items = [item for item, _, _ in raw]
    await _async_check_items(hass, entry, plan)
    return plan


def _identify(
    plan: ImportPlan,
    entry: ConfigEntry,
    subentry_type: str,
    index: int,
    definition: dict[str, Any],
    seen_ids: set[str],
    seen_names: set[tuple[str, str]],
) -> tuple[Item, dict[str, Any], ConfigSubentry | None] | None:
    """Return a definition's item and the existing subentry it stands for, if any.

    A definition with an id is the subentry with that id. Without one it is the
    subentry of that type with the same name.
    """
    type_name = _TYPE_NAMES[subentry_type]
    name = definition.get(KEY_NAME)
    if not isinstance(name, str) or not name.strip():
        plan.problems.append(
            Problem(PROBLEM_INVALID, type_name, f"#{index + 1}", "a name is required")
        )
        return None
    name = name.strip()
    key = (subentry_type, name.casefold())
    if key in seen_names:
        plan.problems.append(Problem(PROBLEM_DUPLICATE, type_name, name))
        return None
    seen_names.add(key)

    subentry_id = definition.get(KEY_ID)
    existing: ConfigSubentry | None = None
    if subentry_id is not None:
        if not isinstance(subentry_id, str) or not subentry_id:
            plan.problems.append(
                Problem(PROBLEM_INVALID, type_name, name, "the id must be text")
            )
            return None
        if subentry_id in seen_ids:
            plan.problems.append(Problem(PROBLEM_DUPLICATE, type_name, name, "id"))
            return None
        existing = entry.subentries.get(subentry_id)
        if existing is not None and existing.subentry_type != subentry_type:
            plan.problems.append(Problem(PROBLEM_ID_IN_USE, type_name, name))
            return None
    else:
        existing = next(
            (
                subentry
                for subentry in entry.subentries.values()
                if subentry.subentry_type == subentry_type
                and subentry.title.casefold() == name.casefold()
            ),
            None,
        )
        subentry_id = existing.subentry_id if existing else ulid_now()
    seen_ids.add(subentry_id)

    if _titled(entry, subentry_type, name, exclude=subentry_id):
        # A new definition with an existing one's name, or one renamed to it.
        plan.problems.append(Problem(PROBLEM_NAME_EXISTS, type_name, name))
        return None
    item = Item(subentry_type, subentry_id, name)
    return item, definition, existing


def _titled(entry: ConfigEntry, subentry_type: str, name: str, exclude: str) -> bool:
    """Return whether another subentry of the type has the name."""
    return any(
        subentry.subentry_type == subentry_type
        and subentry_id != exclude
        and subentry.title.casefold() == name.casefold()
        for subentry_id, subentry in entry.subentries.items()
    )


def _normalise(
    plan: ImportPlan,
    item: Item,
    definition: dict[str, Any],
    groups: Mapping[str, str],
    generators: Mapping[str, str],
) -> None:
    """Validate a definition's fields, and set the item's data: stored as the
    config flows store it, with names turned back into subentry IDs."""
    type_name = _TYPE_NAMES[item.subentry_type]
    fields = _without_blanks(
        _plain({k: v for k, v in definition.items() if k not in (KEY_ID, KEY_NAME)})
    )
    generator = item.subentry_type == SUBENTRY_GENERATOR
    kinds = GENERATOR_KINDS if generator else set(AlertKind)
    try:
        kind = AlertKind(fields.get(CONF_KIND))
        if kind not in kinds:
            raise ValueError
    except ValueError:
        plan.problems.append(
            Problem(
                PROBLEM_INVALID,
                type_name,
                item.name,
                f"kind must be one of {', '.join(sorted(k.value for k in kinds))}",
            )
        )
        item.invalid = True
        return

    # Names in; subentry IDs out.
    problems: list[Problem] = []
    if CONF_NOTIFIER_GROUPS in fields and isinstance(
        fields[CONF_NOTIFIER_GROUPS], list
    ):
        mapped = []
        for name in fields[CONF_NOTIFIER_GROUPS]:
            group = groups.get(name.casefold()) if isinstance(name, str) else None
            if group is None:
                problems.append(
                    Problem(PROBLEM_UNKNOWN_GROUP, type_name, item.name, str(name))
                )
            else:
                mapped.append(group)
        fields[CONF_NOTIFIER_GROUPS] = mapped
    if generator and isinstance(fields.get(CONF_SUPERSEDES), list):
        for rel in fields[CONF_SUPERSEDES]:
            if not isinstance(rel, dict):
                continue
            if (CONF_GENERATOR in rel) == (CONF_ALERT in rel):
                problems.append(Problem(PROBLEM_RELATIONSHIP, type_name, item.name))
            elif CONF_GENERATOR in rel:
                name = rel[CONF_GENERATOR]
                other = (
                    generators.get(name.casefold()) if isinstance(name, str) else None
                )
                if other is None:
                    problems.append(
                        Problem(
                            PROBLEM_UNKNOWN_GENERATOR, type_name, item.name, str(name)
                        )
                    )
                else:
                    rel[CONF_GENERATOR] = other
    if problems:
        plan.problems.extend(problems)
        item.invalid = True
        return

    try:
        item.data = _stored(_schema(kind, generator)(fields))
    except vol.Invalid as err:
        plan.problems.append(Problem(PROBLEM_INVALID, type_name, item.name, str(err)))
        item.invalid = True
        return
    # Targets are required for a generator, and have no blanks.
    if generator:
        item.data[CONF_TARGETS] = _without_blanks(item.data[CONF_TARGETS])


async def _async_check_items(
    hass: HomeAssistant, entry: ConfigEntry, plan: ImportPlan
) -> None:
    """Run the config flows' checks on every valid definition, with all of the
    import's definitions in place."""
    registry = er.async_get(hass)
    valid = [item for item in plan.items if not item.invalid]
    defs = Definitions.from_entry(hass, entry)
    new_entity_ids: dict[str, Item] = {}
    entity_ids: dict[str, str] = {}
    for item in valid:
        if item.subentry_type == SUBENTRY_ALERT:
            member = defs.members.get(item.subentry_id)
            entity_id = member.entity_id if member else None
            if entity_id is None:
                entity_id = f"{DOMAIN}.{slugify(item.name)}"
                other = new_entity_ids.get(entity_id)
                taken = registry.async_get(entity_id)
                if (
                    other is not None
                    or taken is not None
                    and taken.config_subentry_id != item.subentry_id
                ):
                    plan.problems.append(
                        Problem(PROBLEM_ENTITY_ID_CLASH, "alert", item.name, entity_id)
                    )
                    item.invalid = True
                    continue
                new_entity_ids[entity_id] = item
            entity_ids[item.subentry_id] = entity_id
            defs = defs.with_member(
                item.subentry_id, Member(SUBENTRY_ALERT, item.data, entity_id)
            )
        else:
            defs = defs.with_member(
                item.subentry_id, Member(SUBENTRY_GENERATOR, item.data)
            )

    for item in valid:
        if item.invalid or item.action == ACTION_UNCHANGED:
            continue
        type_name = _TYPE_NAMES[item.subentry_type]
        kind = AlertKind(item.data[CONF_KIND])
        if item.subentry_type == SUBENTRY_ALERT:
            error = await async_check_alert(hass, kind, item.data) or check_references(
                defs, entity_ids[item.subentry_id], item.subentry_id, item.data
            )
        else:
            error = await async_check_generator(
                hass, kind, item.data
            ) or check_generator_references(defs, item.subentry_id, item.data)
        if error:
            plan.problems.append(Problem(error, type_name, item.name))


def async_apply_import(
    hass: HomeAssistant, entry: ConfigEntry, plan: ImportPlan
) -> None:
    """Make an import's changes. The plan has no problems."""
    for item in plan.items:
        if item.action == ACTION_UNCHANGED:
            continue
        if item.action == ACTION_UPDATE:
            hass.config_entries.async_update_subentry(
                entry,
                entry.subentries[item.subentry_id],
                data=item.data,
                title=item.name,
            )
        else:
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(item.data),
                    subentry_id=item.subentry_id,
                    subentry_type=item.subentry_type,
                    title=item.name,
                    unique_id=None,
                ),
            )


def describe_problems(problems: Iterable[Problem]) -> str:
    """Return problems as lines of text, for an error message."""
    return "\n".join(f"- {problem}" for problem in problems)
