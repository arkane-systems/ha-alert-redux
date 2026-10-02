"""Checks of an alert's or generator's stored data, shared by the config flows
and by import (spec §16), so there is one validation path.

Each check returns an error key (a key under the flows' `error` translations), or
None. The checks that look at other alerts' relationships work on `Definitions`,
the alerts and generators as they are or as an import would leave them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.script import async_validate_actions_config

from .const import (
    CONF_ACKNOWLEDGEABLE,
    CONF_ACTION,
    CONF_ALERT,
    CONF_ALERT_STATES,
    CONF_ATTRIBUTE,
    CONF_DELAY_OFF,
    CONF_DELAY_ON,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_EVENT_TYPE,
    CONF_GENERATOR,
    CONF_LABEL,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_OFF_TEMPLATE,
    CONF_OFF_TRIGGERS,
    CONF_ON_TEMPLATE,
    CONF_ON_TRIGGERS,
    CONF_SNOOZE_DURATION,
    CONF_SUPERSEDES,
    CONF_TARGETS,
    CONF_TRIGGERS,
    CONF_VALUE_TEMPLATE,
    CONF_BUTTONS,
    DOMAIN,
    SUBENTRY_ALERT,
    SUBENTRY_GENERATOR,
    AlertKind,
    Propagation,
)
from .generators import TargetCriteria
from .model import to_timedelta
from .supersession import find_cycle, propagation_of, relationship_targets
from .triggers import async_validate_triggers, is_storable

# Stands in for the target when a generator's alert configuration is checked
# like an alert's.
PLACEHOLDER_TARGET = "sensor.alert_redux_generator_target"


@dataclass(frozen=True)
class Member:
    """One alert or generator among the Definitions."""

    subentry_type: str
    data: Mapping[str, Any]
    # An alert's entity ID: its registry entry's, or the one it will get.
    entity_id: str | None = None


@dataclass
class Definitions:
    """The fixed alerts and generators, by subentry ID: what supersession cycles
    are checked over. Generated alerts count as their generator."""

    hass: HomeAssistant
    members: dict[str, Member] = field(default_factory=dict)

    @classmethod
    def from_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> Definitions:
        """Return the entry's alerts and generators as they are."""
        members: dict[str, Member] = {}
        for subentry_id, subentry in entry.subentries.items():
            if subentry.subentry_type == SUBENTRY_ALERT:
                members[subentry_id] = Member(
                    SUBENTRY_ALERT,
                    subentry.data,
                    alert_entity_id(hass, subentry_id),
                )
            elif subentry.subentry_type == SUBENTRY_GENERATOR:
                members[subentry_id] = Member(SUBENTRY_GENERATOR, subentry.data)
        return cls(hass, members)

    def with_member(self, subentry_id: str, member: Member) -> Definitions:
        """Return a copy with one member added or replaced."""
        return Definitions(self.hass, {**self.members, subentry_id: member})

    def node(self, target: str) -> str:
        """Return an alert's node in the graph checked for cycles: a generated
        alert counts as its generator."""
        if target.startswith(f"{SUBENTRY_GENERATOR}:"):
            return target
        registry_entry = er.async_get(self.hass).async_get(target)
        if (
            registry_entry is not None
            and (subentry_id := registry_entry.config_subentry_id) is not None
            and (member := self.members.get(subentry_id)) is not None
            and member.subentry_type == SUBENTRY_GENERATOR
        ):
            return generator_node(subentry_id)
        return target

    def edges(self, exclude: str | None = None) -> dict[str, list[str]]:
        """Return who supersedes whom among the alerts and generators, leaving
        out one member (the one being edited).

        Generators stand for all their alerts, so a cycle through them is refused
        even if no target is shared yet: it would be one as soon as one is.
        """
        edges: dict[str, list[str]] = {}
        for subentry_id, member in self.members.items():
            if subentry_id == exclude:
                continue
            relationships = member.data.get(CONF_SUPERSEDES, [])
            if member.subentry_type == SUBENTRY_ALERT:
                if member.entity_id:
                    edges[member.entity_id] = [
                        self.node(target)
                        for target in relationship_targets(relationships)
                    ]
            elif member.subentry_type == SUBENTRY_GENERATOR:
                edges[generator_node(subentry_id)] = [
                    generator_node(rel[CONF_GENERATOR])
                    if CONF_GENERATOR in rel
                    else self.node(rel[CONF_ALERT])
                    for rel in relationships
                    if rel.get(CONF_GENERATOR) or rel.get(CONF_ALERT)
                ]
        return edges


def name_in_use(
    entry: ConfigEntry, subentry_type: str, name: str, exclude: str | None = None
) -> bool:
    """Return whether another subentry of the type already has this name."""
    folded = name.casefold()
    return any(
        subentry.title.casefold() == folded
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == subentry_type and subentry_id != exclude
    )


def alert_entity_id(hass: HomeAssistant, subentry_id: str) -> str | None:
    """Return the entity ID of an alert subentry's entity, if it has one."""
    return er.async_get(hass).async_get_entity_id(DOMAIN, DOMAIN, subentry_id)


def generator_node(subentry_id: str) -> str:
    """Return a generator's node in the supersession graph checked for cycles."""
    return f"{SUBENTRY_GENERATOR}:{subentry_id}"


async def async_check_buttons(
    hass: HomeAssistant, buttons: list[dict[str, Any]]
) -> str | None:
    """Return an error key for notification buttons that aren't complete and valid."""
    for button in buttons:
        if not button[CONF_LABEL] or not button[CONF_ACTION]:
            return "button_incomplete"
        try:
            await async_validate_actions_config(
                hass, cv.SCRIPT_SCHEMA(button[CONF_ACTION])
            )
        except (vol.Invalid, HomeAssistantError):
            return "invalid_button_action"
    return None


async def async_check_alert(
    hass: HomeAssistant, kind: AlertKind, data: dict[str, Any]
) -> str | None:
    """Return an error key for a kind's own fields, if they don't make sense."""
    if error := await async_check_buttons(hass, data.get(CONF_BUTTONS, [])):
        return error
    if kind is AlertKind.EVENT:
        if not data[CONF_EVENT_TYPE]:
            return "event_type_missing"
        if not isinstance(data.get(CONF_EVENT_DATA, {}), dict):
            return "invalid_event_data"
    elif kind is AlertKind.THRESHOLD:
        return check_threshold(data)
    elif kind is AlertKind.ON_OFF:
        if error := check_on_off(data):
            return error
        for key in (CONF_ON_TRIGGERS, CONF_OFF_TRIGGERS):
            if key in data and not await async_triggers_valid(hass, data[key]):
                return "invalid_trigger"
    elif kind is AlertKind.TRIGGER:
        if not await async_triggers_valid(hass, data[CONF_TRIGGERS]):
            return "invalid_trigger"
    return None


def check_references(
    defs: Definitions,
    own: str,
    subentry_id: str | None,
    data: dict[str, Any],
) -> str | None:
    """Return an error key for references to other alerts that don't make sense.

    own is the alert's entity ID, or the one it will get if it's new.
    """
    if data.get(CONF_ALERT) == own:
        return "alert_state_self"
    if CONF_ALERT_STATES in data and not data[CONF_ALERT_STATES]:
        return "alert_states_missing"
    relationships = data.get(CONF_SUPERSEDES, [])
    targets = relationship_targets(relationships)
    if own in targets:
        return "supersedes_self"
    if len(set(targets)) != len(targets):
        return "supersedes_duplicate"
    if error := check_propagation(relationships, data):
        return error
    edges = defs.edges(exclude=subentry_id)
    edges[own] = [defs.node(target) for target in targets]
    if find_cycle(edges):
        return "supersedes_cycle"
    return None


async def async_triggers_valid(hass: HomeAssistant, triggers: Any) -> bool:
    """Return whether triggers are valid, and can be stored."""
    if not triggers or not is_storable(triggers):
        return False
    try:
        await async_validate_triggers(hass, triggers)
    except (vol.Invalid, HomeAssistantError):
        return False
    return True


def check_threshold(data: dict[str, Any]) -> str | None:
    """Check a threshold alert: one value source, and at least one limit."""
    has_entity = CONF_ENTITY_ID in data
    if has_entity == (CONF_VALUE_TEMPLATE in data) or (
        CONF_ATTRIBUTE in data and not has_entity
    ):
        return "value_source"
    if CONF_MINIMUM not in data and CONF_MAXIMUM not in data:
        return "limit_required"
    try:
        low, high = float(data[CONF_MINIMUM]), float(data[CONF_MAXIMUM])
    except (KeyError, ValueError):
        # A limit that's missing, or a template: only known when it renders.
        return None
    return "invalid_limits" if low >= high else None


def check_on_off(data: dict[str, Any]) -> str | None:
    """Check an on/off alert: each side needs a criterion, and delays a template.

    A delay needs its side to hold, which a trigger on its own can't (§4.1).
    """
    for template, triggers in (
        (CONF_ON_TEMPLATE, CONF_ON_TRIGGERS),
        (CONF_OFF_TEMPLATE, CONF_OFF_TRIGGERS),
    ):
        if template not in data and triggers not in data:
            return "criterion_required"
    for delay, template in (
        (CONF_DELAY_ON, CONF_ON_TEMPLATE),
        (CONF_DELAY_OFF, CONF_OFF_TEMPLATE),
    ):
        if (to_timedelta(data.get(delay)) or timedelta(0)) > timedelta(0) and (
            template not in data
        ):
            return "delay_needs_template"
    return None


async def async_check_generator(
    hass: HomeAssistant, kind: AlertKind, data: dict[str, Any]
) -> str | None:
    """Return an error key for a generator that doesn't make sense."""
    if not TargetCriteria.from_config(data[CONF_TARGETS]).any:
        return "targets_required"
    if kind is AlertKind.ALERT_STATE and not data[CONF_ALERT_STATES]:
        return "alert_states_missing"
    alert = dict(data)
    if kind is AlertKind.THRESHOLD and CONF_VALUE_TEMPLATE not in alert:
        # The value is the target's, as the generated alerts have it.
        alert[CONF_ENTITY_ID] = PLACEHOLDER_TARGET
    return await async_check_alert(hass, kind, alert)


def check_generator_references(
    defs: Definitions,
    subentry_id: str | None,
    data: dict[str, Any],
) -> str | None:
    """Return an error key for a generator's relationships that don't make
    sense (spec §12.3), as check_references does for an alert's."""
    relationships = data.get(CONF_SUPERSEDES, [])
    own = generator_node(subentry_id or "new")
    targets = [
        generator_node(rel[CONF_GENERATOR])
        if CONF_GENERATOR in rel
        else rel[CONF_ALERT]
        for rel in relationships
    ]
    if subentry_id is not None and own in targets:
        return "supersedes_self"
    if len(set(targets)) != len(targets):
        return "supersedes_duplicate"
    if error := check_propagation(relationships, data):
        return error
    edges = defs.edges()
    edges[own] = [defs.node(target) for target in targets]
    if find_cycle(edges):
        return "supersedes_cycle"
    return None


def check_propagation(
    relationships: list[dict[str, Any]], data: dict[str, Any]
) -> str | None:
    """Check relationships' propagation against the alert's own settings."""
    for rel in relationships:
        propagation = propagation_of(rel)
        # Propagating to an alert that can't be acknowledged is an error (§8.3).
        if propagation is not Propagation.NONE and not data[CONF_ACKNOWLEDGEABLE]:
            return "propagation_unacknowledgeable"
        if propagation is Propagation.SNOOZE and not to_timedelta(
            rel.get(CONF_SNOOZE_DURATION)
        ):
            return "snooze_duration_missing"
    return None
