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

from .const import CONF_ALERT, Priority

if TYPE_CHECKING:
    from .entity import AlertEntity
    from .model import Settings

_LOGGER = logging.getLogger(__name__)


def relationship_targets(relationships: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return the entity IDs of the alerts that relationships supersede."""
    return [target for rel in relationships if (target := rel.get(CONF_ALERT))]


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

    def __init__(self, entities: Mapping[str, AlertEntity], settings: Settings) -> None:
        """Initialize from the alert entities, by subentry ID, and the settings."""
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
        """Bring every alert's superseded_by up to date, e.g. after a config change."""
        for entity in self._by_entity_id().values():
            entity.async_superseders_changed(announce=False)
