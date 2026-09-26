"""Supersession: alerts that take precedence over other alerts (spec §8).

An alert lists the alerts it supersedes, by entity ID. While a superseding alert
is firing, the alerts it supersedes, transitively, don't send on or reminder
notifications; their done notification is dropped if they and a superseding alert
end together (§9.7). Supersession affects notifications only: a superseded alert
keeps its own state, and shows what supersedes it in `superseded_by`.

SupersessionGraph is the relationships alone, free of Home Assistant; Supersession
is the coordinator the alert entities share, which answers questions about the
alerts' current state and passes on changes between them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALERT,
    CONF_PROPAGATION,
    CONF_SNOOZE_DURATION,
    DOMAIN,
    AlertState,
    Priority,
    Propagation,
)
from .model import Settings, to_timedelta

if TYPE_CHECKING:
    from .entity import AlertEntity

_LOGGER = logging.getLogger(__name__)


def relationship_targets(relationships: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return the entity IDs of the alerts that relationships supersede."""
    return [target for rel in relationships if (target := rel.get(CONF_ALERT))]


def propagation_of(relationship: Mapping[str, Any]) -> Propagation:
    """Return a relationship's propagation setting; None unless it's valid."""
    try:
        return Propagation(relationship.get(CONF_PROPAGATION, Propagation.NONE))
    except ValueError:
        return Propagation.NONE


def find_cycle(edges: Mapping[str, Iterable[str]]) -> list[str] | None:
    """Return a supersession cycle as a path (A, B, …, A), or None if there's none.

    edges maps each alert to the alerts it supersedes.
    """
    visiting: list[str] = []
    done: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            return [*visiting[visiting.index(node) :], node]
        if node in done:
            return None
        visiting.append(node)
        for target in edges.get(node, ()):
            if cycle := visit(target):
                return cycle
        visiting.pop()
        done.add(node)
        return None

    for node in edges:
        if cycle := visit(node):
            return cycle
    return None


class SupersessionGraph:
    """Who supersedes whom: each alert's relationships, and their closure."""

    def __init__(self, relationships: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        """Build the graph from each alert's relationships, by entity ID."""
        self._relationships = {
            entity_id: [dict(rel) for rel in rels if rel.get(CONF_ALERT)]
            for entity_id, rels in relationships.items()
        }
        self._superseders: dict[str, set[str]] = {}
        for entity_id, rels in self._relationships.items():
            for target in relationship_targets(rels):
                if target != entity_id:
                    self._superseders.setdefault(target, set()).add(entity_id)
        if cycle := find_cycle(
            {eid: relationship_targets(rels) for eid, rels in self._relationships.items()}
        ):
            # The forms refuse cycles; one that gets in anyway can't loop.
            _LOGGER.warning("Supersession cycle: %s", " > ".join(cycle))

    def relationships(self, entity_id: str) -> list[dict[str, Any]]:
        """Return the relationships of the alerts an alert supersedes directly."""
        return self._relationships.get(entity_id, [])

    def direct_superseders(self, entity_id: str) -> set[str]:
        """Return the alerts that list this one as superseded."""
        return set(self._superseders.get(entity_id, ()))

    def superseders(self, entity_id: str) -> set[str]:
        """Return every alert that supersedes this one, transitively."""
        return self._closure(entity_id, lambda eid: self._superseders.get(eid, ()))

    def superseded(self, entity_id: str) -> set[str]:
        """Return every alert this one supersedes, transitively."""
        return self._closure(
            entity_id,
            lambda eid: relationship_targets(self._relationships.get(eid, ())),
        )

    def has_superseders(self, entity_id: str) -> bool:
        """Return whether any alert supersedes this one."""
        return bool(self._superseders.get(entity_id))

    @staticmethod
    def _closure(start: str, step: Any) -> set[str]:
        found: set[str] = set()
        pending = [start]
        while pending:
            for nxt in step(pending.pop()):
                if nxt not in found and nxt != start:
                    found.add(nxt)
                    pending.append(nxt)
        return found


class DoneDecision(StrEnum):
    """What to do with a superseded alert's done notification (spec §9.7)."""

    SEND = "send"
    # Wait for the done window: a superseding alert is still firing.
    HOLD = "hold"
    # A superseding alert ended within the done window: its done covers both.
    DROP = "drop"


class Supersession:
    """The alerts' shared view of supersession.

    The entities are looked up by their current entity IDs, so renames need no
    bookkeeping here; the graph is rebuilt whenever those, or any alert's
    relationships, change.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entities: Mapping[str, AlertEntity],
        settings: Settings,
    ) -> None:
        """Initialize from the alert entities, by subentry ID, and the settings."""
        self._hass = hass
        self._entities = entities
        self._settings = settings
        self._graph_key: tuple[Any, ...] | None = None
        self._graph = SupersessionGraph({})

    @property
    def graph(self) -> SupersessionGraph:
        """Return the graph of the alerts as they're currently configured."""
        relationships = {
            entity.entity_id: entity.supersedes
            for entity in self._entities.values()
            if entity.entity_id
        }
        key = tuple(sorted((eid, repr(rels)) for eid, rels in relationships.items()))
        if key != self._graph_key:
            self._graph_key = key
            self._graph = SupersessionGraph(relationships)
        return self._graph

    def _by_entity_id(self) -> dict[str, AlertEntity]:
        return {
            entity.entity_id: entity
            for entity in self._entities.values()
            if entity.entity_id and entity.hass is not None
        }

    def has_superseders(self, entity_id: str) -> bool:
        """Return whether any alert supersedes this one."""
        return self.graph.has_superseders(entity_id)

    def superseded_by(self, entity_id: str) -> list[str]:
        """Return the firing alerts that supersede this one, highest priority first."""
        entities = self._by_entity_id()
        firing = [
            entities[eid]
            for eid in self.graph.superseders(entity_id)
            if eid in entities and entities[eid].firing
        ]
        firing.sort(key=lambda e: (Priority(e.priority).rank, e.entity_id))
        return [entity.entity_id for entity in firing]

    def done_decision(self, entity_id: str, now: datetime) -> DoneDecision:
        """Decide on a superseded alert's done notification, as it stops firing.

        It's dropped if a superseding alert ended within the done window before
        it, held while one is still firing (it may end within the window after),
        and otherwise sent.
        """
        entities = self._by_entity_id()
        superseders = [
            entities[eid] for eid in self.graph.superseders(entity_id) if eid in entities
        ]
        window = self._settings.done_window
        if any(
            not entity.firing
            and entity.last_ended is not None
            and now - entity.last_ended <= window
            for entity in superseders
        ):
            return DoneDecision.DROP
        if any(entity.firing for entity in superseders):
            return DoneDecision.HOLD
        return DoneDecision.SEND

    def async_firing_changed(self, entity: AlertEntity, *, started: bool) -> None:
        """Pass on an alert starting or stopping firing to the alerts it supersedes.

        started is true only for a real start, not for a firing restored at
        startup, so that restoring doesn't announce supersession afresh.
        """
        entities = self._by_entity_id()
        for eid in self.graph.superseded(entity.entity_id):
            if (superseded := entities.get(eid)) is None:
                continue
            if not entity.firing:
                superseded.async_superseder_ended()
            superseded.async_superseders_changed(announce=started)

    def async_refresh(self) -> None:
        """Bring every alert's supersession and references up to date.

        For example after a configuration change, or an alert being added,
        removed, or renamed.
        """
        for entity in self._by_entity_id().values():
            entity.async_superseders_changed(announce=False)
        self.async_sweep_pre_acks()

    def acknowledged(self) -> set[str]:
        """Return the unique IDs of the alerts acknowledged now: the pre-ack
        sources that count."""
        return {
            unique_id
            for unique_id, entity in self._entities.items()
            if entity.hass is not None and entity.state == AlertState.ACK
        }

    def entity_ids(self, unique_ids: Iterable[str]) -> list[str]:
        """Return the current entity IDs of alerts, by unique ID, for display."""
        return sorted(
            entity.entity_id
            if (entity := self._entities.get(unique_id)) is not None and entity.entity_id
            else unique_id
            for unique_id in unique_ids
        )

    def async_ack_changed(self, entity: AlertEntity, *, acked: bool) -> None:
        """Propagate an alert becoming acknowledged, or losing it (spec §8.2).

        Becoming acknowledged pre-acknowledges (or pre-snoozes) each alert that
        directly supersedes it with propagation set; losing it, by an unack, a
        snooze running out, or the firing ending, cancels those.
        """
        entities = self._by_entity_id()
        now = dt_util.utcnow()
        for eid in self.graph.direct_superseders(entity.entity_id):
            if (superseder := entities.get(eid)) is None:
                continue
            assert entity.unique_id is not None
            if not acked:
                superseder.async_remove_pre_ack(entity.unique_id)
                continue
            relationship = next(
                (
                    rel
                    for rel in superseder.supersedes
                    if rel.get(CONF_ALERT) == entity.entity_id
                ),
                {},
            )
            propagation = propagation_of(relationship)
            if propagation is Propagation.NONE:
                continue
            until = None
            if propagation is Propagation.SNOOZE:
                if not (duration := to_timedelta(relationship.get(CONF_SNOOZE_DURATION))):
                    continue
                until = now + duration
            superseder.async_add_pre_ack(entity.unique_id, until, entity.context)

    def async_sweep_pre_acks(self) -> None:
        """Drop stale pre-acknowledgements: from an alert that's gone, or one
        that isn't acknowledged, e.g. after a restart.

        Pre-acknowledgements are kept by the source's unique ID, so renames
        don't affect them. An alert that hasn't been added yet (while starting
        up) is left alone.
        """

        def stale(source: str) -> bool:
            if (entity := self._entities.get(source)) is None:
                return True
            return entity.hass is not None and entity.state != AlertState.ACK

        for entity in self._by_entity_id().values():
            entity.async_drop_pre_acks(stale)

    def broken_references(self, entity: AlertEntity) -> list[str]:
        """Return the alerts this one refers to that don't exist (spec §12.4)."""
        registry = er.async_get(self._hass)
        return [
            target
            for target in entity.references
            if (entry := registry.async_get(target)) is None or entry.platform != DOMAIN
        ]
