"""Generators: one alert per matching target entity (spec §12.3).

A generator is a subentry holding a condition alert's configuration, a name
template, and target criteria. The criteria combine AND across (labels, areas,
domains, device classes, an entity ID pattern) and OR within each; labels and
areas count through the entity's device too. Each matching entity gets its own
alert, whose definition is the generator's with the target filled in: the
kind's entity, the subject entity, and the `target` and `target_name` template
variables.

Generators follow the registries and the state machine, adding alerts as
entities start matching and removing them as they stop. Removals are held back
until Home Assistant has started and a grace period has passed, so that slow
integrations don't make alerts flap.

A generated alert's unique ID is the generator's subentry ID and the target's
key: its entity registry ID, so the alert survives the target being renamed, or
its entity ID if it has no registry entry. Generated alerts are never targets
themselves, and neither are Alert Redux's other entities.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatchcase
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    EVENT_STATE_CHANGED,
    EntityCategory,
    Platform,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.template import Template
from homeassistant.util import slugify

from .const import (
    ATTR_KIND,
    ATTR_NAME,
    ATTR_NEW_STATE,
    ATTR_OLD_STATE,
    ATTR_PRIORITY,
    ATTR_USER_ID,
    CONF_ALERT,
    CONF_AREAS,
    CONF_DEVICE_CLASSES,
    CONF_DOMAINS,
    CONF_ENTITY_ID,
    CONF_GENERATOR,
    CONF_EXCLUDE,
    CONF_KIND,
    CONF_LABELS,
    CONF_NAME_TEMPLATE,
    CONF_PATTERN,
    CONF_SUBJECT_ENTITY,
    CONF_SUPERSEDES,
    CONF_TARGETS,
    CONF_VALUE_TEMPLATE,
    DATA_ADD_ENTITIES,
    DATA_ADD_SENSORS,
    DOMAIN,
    EVENT_DELETED,
    SUBENTRY_ALERT,
    SUBENTRY_GENERATOR,
    VAR_TARGET,
    VAR_TARGET_NAME,
    AlertKind,
)
from .definitions import AlertDefinition, generator_unique_id
from .model import AlertRuntime, Settings
from .notifications import async_clear_notifications
from .store import AlertStore

if TYPE_CHECKING:
    from .entity import AlertEntity

_LOGGER = logging.getLogger(__name__)

# How long generators wait for a burst of registry or state changes to settle.
REFRESH_COOLDOWN = 1.0


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidate:
    """An entity a generator might target, as far as matching needs to know."""

    entity_id: str
    # The entity registry ID, or the entity ID for an entity with no entry.
    key: str
    name: str
    labels: frozenset[str] = frozenset()
    area: str | None = None
    device_class: str | None = None


@dataclass(frozen=True, slots=True)
class TargetCriteria:
    """What a generator's targets must match: AND across, OR within."""

    labels: frozenset[str] = frozenset()
    areas: frozenset[str] = frozenset()
    domains: frozenset[str] = frozenset()
    device_classes: frozenset[str] = frozenset()
    pattern: str | None = None
    exclude: frozenset[str] = frozenset()

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> TargetCriteria:
        """Read the criteria from a generator's stored targets."""
        return cls(
            labels=frozenset(config.get(CONF_LABELS) or ()),
            areas=frozenset(config.get(CONF_AREAS) or ()),
            domains=frozenset(config.get(CONF_DOMAINS) or ()),
            device_classes=frozenset(config.get(CONF_DEVICE_CLASSES) or ()),
            pattern=config.get(CONF_PATTERN) or None,
            exclude=frozenset(config.get(CONF_EXCLUDE) or ()),
        )

    @property
    def any(self) -> bool:
        """Return whether any criterion is set; with none, nothing matches."""
        return bool(
            self.labels
            or self.areas
            or self.domains
            or self.device_classes
            or self.pattern
        )

    def matches(self, candidate: Candidate) -> bool:
        """Return whether an entity matches every criterion that's set."""
        entity_id = candidate.entity_id
        if not self.any or entity_id in self.exclude:
            return False
        if self.labels and self.labels.isdisjoint(candidate.labels):
            return False
        if self.areas and candidate.area not in self.areas:
            return False
        if self.domains and entity_id.split(".", 1)[0] not in self.domains:
            return False
        if self.device_classes and candidate.device_class not in self.device_classes:
            return False
        return self.pattern is None or fnmatchcase(entity_id, self.pattern)


@callback
def async_candidates(hass: HomeAssistant, fixed_alerts: set[str]) -> list[Candidate]:
    """Return every entity a generator may target.

    That's every enabled registry entry, except configuration entities, plus
    every entity with no registry entry. Alert Redux's own entities are left out,
    except its fixed alerts (given by unique ID), which alert state generators
    watch.
    """
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    candidates: list[Candidate] = []
    for entry in entities.entities.values():
        if (
            entry.disabled_by is not None
            or entry.entity_category is EntityCategory.CONFIG
        ):
            continue
        if entry.platform == DOMAIN and not (
            entry.domain == DOMAIN and entry.unique_id in fixed_alerts
        ):
            continue
        device = devices.async_get(entry.device_id) if entry.device_id else None
        state = hass.states.get(entry.entity_id)
        candidates.append(
            Candidate(
                entity_id=entry.entity_id,
                key=entry.id,
                name=(
                    state.name
                    if state is not None
                    else entry.name or entry.original_name or entry.entity_id
                ),
                labels=frozenset(entry.labels | (device.labels if device else set())),
                area=entry.area_id or (device.area_id if device else None),
                device_class=(
                    entry.device_class
                    or entry.original_device_class
                    or (state.attributes.get(ATTR_DEVICE_CLASS) if state else None)
                ),
            )
        )
    for state in hass.states.async_all():
        if state.domain == DOMAIN or entities.async_get(state.entity_id) is not None:
            continue
        candidates.append(
            Candidate(
                entity_id=state.entity_id,
                key=state.entity_id,
                name=state.name,
                device_class=state.attributes.get(ATTR_DEVICE_CLASS),
            )
        )
    return candidates


def generated_unique_id(generator: str, key: str) -> str:
    """Return a generated alert's unique ID."""
    return f"{generator}_{key}"


@dataclass(slots=True)
class Generator:
    """One generator: its configuration, and the alerts it has made."""

    subentry_id: str
    name: str
    kind: AlertKind
    criteria: TargetCriteria
    name_template: str | None
    # The alert configuration every generated alert shares.
    alert_data: dict[str, Any]
    # By target key: what each alert was built from, and the entity.
    definitions: dict[str, AlertDefinition] = field(default_factory=dict)
    entities: dict[str, AlertEntity] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @classmethod
    def from_subentry(cls, subentry: ConfigSubentry) -> Generator:
        """Read a generator from its subentry."""
        generator = cls(
            subentry_id=subentry.subentry_id,
            name=subentry.title,
            kind=AlertKind.STATE,
            criteria=TargetCriteria(),
            name_template=None,
            alert_data={},
        )
        generator.configure(subentry)
        return generator

    def configure(self, subentry: ConfigSubentry) -> None:
        """Take the generator's configuration from its subentry."""
        data = subentry.data
        self.name = subentry.title
        self.kind = AlertKind(data[CONF_KIND])
        self.criteria = TargetCriteria.from_config(data.get(CONF_TARGETS) or {})
        self.name_template = data.get(CONF_NAME_TEMPLATE) or None
        self.alert_data = {
            key: value
            for key, value in data.items()
            if key not in (CONF_TARGETS, CONF_NAME_TEMPLATE)
        }

    @property
    def targets(self) -> list[str]:
        """Return the target entity IDs."""
        return sorted(
            definition.target
            for definition in self.definitions.values()
            if definition.target is not None
        )

    def definition(
        self, hass: HomeAssistant, candidate: Candidate, problems: list[str]
    ) -> AlertDefinition:
        """Return the alert definition for one target."""
        variables = {VAR_TARGET: candidate.entity_id, VAR_TARGET_NAME: candidate.name}
        data = dict(self.alert_data)
        data[CONF_SUBJECT_ENTITY] = candidate.entity_id
        if self.kind is AlertKind.STATE or (
            # A threshold's value is the target's, unless a template gives it.
            self.kind is AlertKind.THRESHOLD and CONF_VALUE_TEMPLATE not in data
        ):
            data[CONF_ENTITY_ID] = candidate.entity_id
        elif self.kind is AlertKind.ALERT_STATE:
            data[CONF_ALERT] = candidate.entity_id
        return AlertDefinition(
            unique_id=generated_unique_id(self.subentry_id, candidate.key),
            name=self._name(hass, candidate, variables, problems),
            data=data,
            generator=self.subentry_id,
            target=candidate.entity_id,
            variables=variables,
        )

    def _name(
        self,
        hass: HomeAssistant,
        candidate: Candidate,
        variables: dict[str, Any],
        problems: list[str],
    ) -> str:
        """Render the alert's name; the default is the target's and the
        generator's names."""
        default = f"{candidate.name} {self.name}"
        if self.name_template is None:
            return default
        try:
            name = str(
                Template(self.name_template, hass).async_render(
                    variables, parse_result=False
                )
            ).strip()
        except TemplateError as err:
            problems.append(
                f"{candidate.entity_id}: the name template failed ({err}); "
                "using the default name"
            )
            return default
        return name or default


class GeneratorManager:
    """Keeps every generator's alerts in step with its targets.

    Generated alerts are added through the alert platform with their generator's
    subentry ID, so Home Assistant removes them with it, and kept in the shared
    entities mapping with the fixed alerts, by unique ID.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: AlertStore,
        settings: Settings,
        entities: dict[str, AlertEntity],
        on_changed: Callable[[], None],
    ) -> None:
        """Initialize the manager; on_changed is called after alerts change."""
        self.hass = hass
        self._entry = entry
        self._store = store
        self._settings = settings
        self._entities = entities
        self._on_changed = on_changed
        self.generators: dict[str, Generator] = {}
        self._listeners: dict[str, list[CALLBACK_TYPE]] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        self._started = False
        # Removals wait for Home Assistant to have started, and the grace
        # period after that.
        self._removals_allowed = False
        self._debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=REFRESH_COOLDOWN,
            immediate=False,
            function=self._async_refresh_all,
        )

    @property
    def removals_allowed(self) -> bool:
        """Return whether alerts whose targets are gone may be removed yet."""
        return self._removals_allowed

    @callback
    def async_load(self) -> None:
        """Read the generators, and work out their alerts, before any is added.

        Alerts whose targets haven't appeared yet are kept, from their stored
        records, while removals are held back.
        """
        candidates = self._candidates()
        for subentry in self._generator_subentries():
            generator = self.generators[subentry.subentry_id] = Generator.from_subentry(
                subentry
            )
            generator.definitions = self._restored(generator)
            generator.definitions.update(self._wanted(generator, candidates))

    def generated_ids(self) -> set[str]:
        """Return the unique IDs of every generated alert."""
        return {
            definition.unique_id
            for generator in self.generators.values()
            for definition in generator.definitions.values()
        }

    @callback
    def async_start(self) -> None:
        """Add the generated alerts worked out at load, and start following
        the registries and the state machine."""
        for generator in self.generators.values():
            for key, definition in generator.definitions.items():
                self._async_add_alert(generator, key, definition)
        self._unsubs = [
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._async_schedule
            ),
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, self._async_schedule
            ),
            # Entities coming and going: those with no registry entry, and
            # registered entities' names, which come from their states.
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                self._async_schedule,
                event_filter=_is_added_or_removed,
            ),
        ]
        self._started = True
        if self.hass.state is CoreState.running:
            # Set up after startup (a reload, or a first install): the targets
            # are all there already.
            self._removals_allowed = True
        else:
            self._unsubs.append(async_at_started(self.hass, self._async_started))

    @callback
    def async_stop(self) -> None:
        """Stop following changes."""
        self._started = False
        self._debouncer.async_cancel()
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    async def _async_started(self, _hass: HomeAssistant) -> None:
        """Allow removals once the grace period after startup has passed."""
        grace = self._settings.generator_grace.total_seconds()
        if grace <= 0:
            self._async_allow_removals(None)
            return
        self._unsubs.append(
            async_call_later(self.hass, grace, self._async_allow_removals)
        )

    @callback
    def _async_allow_removals(self, _now: datetime | None) -> None:
        self._removals_allowed = True
        self._async_refresh_all_now()

    @callback
    def _async_schedule(self, _event: Event[Any]) -> None:
        self._debouncer.async_schedule_call()

    async def _async_refresh_all(self) -> None:
        self._async_refresh_all_now()

    @callback
    def _async_refresh_all_now(self) -> None:
        """Bring every generator's alerts up to date with its targets."""
        if not self._started:
            return
        candidates = self._candidates()
        for generator in self.generators.values():
            self._async_apply(generator, candidates)

    @callback
    def async_refresh(self, subentry_id: str) -> None:
        """Re-evaluate one generator's targets now (the refresh action)."""
        self._async_apply(self.generators[subentry_id], self._candidates())

    @callback
    def async_add_generator(self, subentry: ConfigSubentry) -> None:
        """Start a new generator, adding its alerts and its sensor."""
        generator = self.generators[subentry.subentry_id] = Generator.from_subentry(
            subentry
        )
        self._async_add_sensor(generator)
        self._async_apply(generator, self._candidates())

    @callback
    def async_update_generator(self, subentry: ConfigSubentry) -> None:
        """Apply an edited generator: every alert's definition is rebuilt."""
        generator = self.generators[subentry.subentry_id]
        generator.configure(subentry)
        self._async_apply(generator, self._candidates())

    @callback
    def async_remove_generator(self, subentry_id: str) -> None:
        """Forget a deleted generator; Home Assistant removes its entities."""
        generator = self.generators.pop(subentry_id, None)
        if generator is None:
            return
        for definition in generator.definitions.values():
            self._entities.pop(definition.unique_id, None)
        self._listeners.pop(subentry_id, None)
        self._on_changed()

    def resolve_relationships(
        self, definition: AlertDefinition, relationships: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return a generated alert's relationships by entity ID.

        One to another generator becomes one to that generator's alert for the
        same target, and is left out if it has none (spec §12.3).
        """
        resolved: list[dict[str, Any]] = []
        for rel in relationships:
            if (other := rel.get(CONF_GENERATOR)) is None:
                resolved.append(rel)
                continue
            generator = self.generators.get(other)
            entity = (
                generator.entities.get(definition.target_key or "")
                if generator is not None
                else None
            )
            if entity is not None and entity.entity_id:
                resolved.append(
                    {
                        **{k: v for k, v in rel.items() if k != CONF_GENERATOR},
                        CONF_ALERT: entity.entity_id,
                    }
                )
        return resolved

    def supersedes(self, subentry_id: str) -> list[str]:
        """Return what a generator's alerts supersede, for its sensor: other
        generators' sensors, and fixed alerts."""
        generator = self.generators[subentry_id]
        registry = er.async_get(self.hass)
        links: list[str] = []
        for rel in generator.alert_data.get(CONF_SUPERSEDES) or []:
            if (other := rel.get(CONF_GENERATOR)) is not None:
                links.append(
                    registry.async_get_entity_id(
                        Platform.SENSOR, DOMAIN, generator_unique_id(other)
                    )
                    or other
                )
            elif alert := rel.get(CONF_ALERT):
                links.append(alert)
        return links

    @callback
    def async_add_listener(
        self, subentry_id: str, listener: Callable[[], None]
    ) -> CALLBACK_TYPE:
        """Call listener whenever a generator's alerts or problems change."""
        listeners = self._listeners.setdefault(subentry_id, [])
        listeners.append(listener)

        @callback
        def _remove() -> None:
            if listener in (current := self._listeners.get(subentry_id, [])):
                current.remove(listener)

        return _remove

    @callback
    def async_add_sensors(self) -> None:
        """Add a sensor for every generator (the sensor platform's setup)."""
        for generator in self.generators.values():
            self._async_add_sensor(generator)

    def _async_add_sensor(self, generator: Generator) -> None:
        add_sensors = self.hass.data[DOMAIN].get(DATA_ADD_SENSORS)
        if add_sensors is None:
            # The sensor platform adds it when it's set up.
            return
        from .sensor import GeneratorSensor  # noqa: PLC0415 (a platform module)

        add_sensors(
            [GeneratorSensor(self, generator.subentry_id)],
            config_subentry_id=generator.subentry_id,
        )

    def _candidates(self) -> list[Candidate]:
        fixed = {
            subentry_id
            for subentry_id, subentry in self._entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_ALERT
        }
        return async_candidates(self.hass, fixed)

    def _generator_subentries(self) -> Iterable[ConfigSubentry]:
        return (
            subentry
            for subentry in self._entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_GENERATOR
        )

    def _wanted(
        self, generator: Generator, candidates: list[Candidate]
    ) -> dict[str, AlertDefinition]:
        """Return the definitions of the alerts a generator should have now."""
        problems: list[str] = []
        wanted = {
            candidate.key: generator.definition(self.hass, candidate, problems)
            for candidate in candidates
            if generator.criteria.matches(candidate)
        }
        generator.problems = problems
        return wanted

    def _restored(self, generator: Generator) -> dict[str, AlertDefinition]:
        """Return the definitions of a generator's stored alerts, as they were.

        Used at startup, so that alerts whose targets haven't appeared yet are
        kept until removals are allowed.
        """
        prefix = f"{generator.subentry_id}_"
        restored: dict[str, AlertDefinition] = {}
        for unique_id in self._store.alert_ids():
            record = self._store.get_alert(unique_id) or {}
            target = record.get("target")
            if record.get("generator") != generator.subentry_id or not target:
                continue
            key = unique_id.removeprefix(prefix)
            candidate = Candidate(
                entity_id=target, key=key, name=target.split(".", 1)[-1]
            )
            definition = generator.definition(self.hass, candidate, [])
            # Keep the stored name, rather than one made from the entity ID.
            restored[key] = AlertDefinition(
                unique_id=definition.unique_id,
                name=record.get(ATTR_NAME) or definition.name,
                data=definition.data,
                generator=definition.generator,
                target=definition.target,
                variables=definition.variables,
            )
        return restored

    @callback
    def _async_apply(self, generator: Generator, candidates: list[Candidate]) -> None:
        """Add, update, and remove a generator's alerts to match its targets."""
        wanted = self._wanted(generator, candidates)
        current = generator.definitions
        if not self._removals_allowed:
            for key, definition in current.items():
                wanted.setdefault(key, definition)
        changed = False
        for key in current.keys() - wanted.keys():
            self._async_remove_alert(generator, key)
            changed = True
        for key, definition in wanted.items():
            if key not in current:
                self._async_add_alert(generator, key, definition)
                changed = True
            elif definition != current[key]:
                if (entity := generator.entities.get(key)) is not None:
                    entity.async_update_config(definition)
                changed = True
        generator.definitions = wanted
        if changed:
            self._on_changed()
        for listener in list(self._listeners.get(generator.subentry_id, [])):
            listener()

    @callback
    def _async_add_alert(
        self, generator: Generator, key: str, definition: AlertDefinition
    ) -> None:
        from .entity import create_alert_entity  # noqa: PLC0415 (circular)

        entity = create_alert_entity(definition, self._store, self._settings)
        entity.relationship_resolver = self.resolve_relationships
        # The entity ID a new alert gets: the target's, then the generator's name
        # (spec §12.3). The registry keeps it from then on.
        object_id = (definition.target or key).split(".", 1)[-1]
        entity.entity_id = f"{DOMAIN}.{slugify(f'{object_id} {generator.name}')}"
        generator.entities[key] = entity
        self._entities[definition.unique_id] = entity
        self.hass.data[DOMAIN][DATA_ADD_ENTITIES](
            [entity], config_subentry_id=generator.subentry_id
        )

    @callback
    def _async_remove_alert(self, generator: Generator, key: str) -> None:
        """Remove an alert whose target no longer matches, announcing it."""
        definition = generator.definitions[key]
        entity = generator.entities.pop(key, None)
        self._entities.pop(definition.unique_id, None)
        if entity is not None and entity.hass is not None:
            self.hass.async_create_task(
                self._async_remove_entity(entity, definition.unique_id),
                eager_start=True,
            )
        else:
            async_forget_alert(self.hass, self._store, definition.unique_id)

    async def _async_remove_entity(self, entity: AlertEntity, unique_id: str) -> None:
        entity_id = entity.entity_id
        await entity.async_remove(force_remove=True)
        registry = er.async_get(self.hass)
        if registry.async_get(entity_id) is not None:
            registry.async_remove(entity_id)
        async_forget_alert(self.hass, self._store, unique_id)


@callback
def _is_added_or_removed(data: EventStateChangedData) -> bool:
    return data["old_state"] is None or data["new_state"] is None


@callback
def async_forget_alert(hass: HomeAssistant, store: AlertStore, unique_id: str) -> None:
    """Drop a deleted alert's stored record, announcing its deletion and
    clearing its notifications."""
    record = store.get_alert(unique_id) or {}
    store.remove_alert(unique_id)
    if entity_id := record.get("entity_id"):
        async_clear_notifications(hass, entity_id)
    hass.bus.async_fire(
        EVENT_DELETED,
        {
            "entity_id": record.get("entity_id"),
            ATTR_NAME: record.get(ATTR_NAME),
            ATTR_PRIORITY: record.get(ATTR_PRIORITY),
            ATTR_KIND: record.get(ATTR_KIND),
            ATTR_OLD_STATE: _stored_state(record),
            ATTR_NEW_STATE: None,
            ATTR_USER_ID: None,
        },
    )


def _stored_state(record: dict) -> str | None:
    if "runtime" not in record:
        return None
    return AlertRuntime.from_dict(record["runtime"]).state
