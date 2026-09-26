"""The summary sensors (spec §11.2), and the generator sensors (§12.3).

Glue such as a signal light can follow a summary sensor instead of every alert.
They read the SummaryCoordinator, which the alerts report to. They have no device
(spec §11.5) and don't get the alerts label: they change constantly, and would
flood an Activity card.

Each generator has a sensor too: the number of alerts it has made, with its
targets, those alerts, and any problems. Like the summary sensors, they have no
device and no label.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import (
    ATTR_ALERTS,
    ATTR_PROBLEMS,
    ATTR_TARGETS,
    DATA_ADD_SENSORS,
    DATA_GENERATORS,
    DATA_SUMMARY,
    DOMAIN,
    Priority,
)
from .definitions import generator_unique_id
from .generators import GeneratorManager
from .summary import Summary, SummaryCoordinator

ATTR_ENTITY_IDS = "entity_ids"
# The highest priority sensors' state when nothing counts.
NO_PRIORITY = "none"


@dataclass(frozen=True, kw_only=True)
class SummarySensorDescription(SensorEntityDescription):
    """A summary sensor: its value, and the attributes it adds."""

    value: Callable[[Summary], Any]
    # The entity IDs counted, for the count sensors.
    entity_ids: Callable[[Summary], tuple[str, ...]] | None = None
    by_priority: Callable[[Summary], dict[Priority, int]] | None = None


def _priority_sensor(
    key: str, value: Callable[[Summary], Priority | None]
) -> SummarySensorDescription:
    return SummarySensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.ENUM,
        options=[*Priority, NO_PRIORITY],
        value=lambda summary: value(summary) or NO_PRIORITY,
    )


def _count_sensor(
    key: str,
    entity_ids: Callable[[Summary], tuple[str, ...]],
    by_priority: Callable[[Summary], dict[Priority, int]] | None = None,
    entity_category: EntityCategory | None = None,
) -> SummarySensorDescription:
    return SummarySensorDescription(
        key=key,
        translation_key=key,
        # A state class keeps the counts out of the logbook, and gives statistics.
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=entity_category,
        value=lambda summary: len(entity_ids(summary)),
        entity_ids=entity_ids,
        by_priority=by_priority,
    )


SENSORS: tuple[SummarySensorDescription, ...] = (
    _priority_sensor("highest_priority", lambda s: s.highest_priority),
    _priority_sensor("highest_unacked_priority", lambda s: s.highest_unacked_priority),
    _count_sensor("firing", lambda s: s.firing, lambda s: s.firing_by_priority),
    _count_sensor("active", lambda s: s.active, lambda s: s.active_by_priority),
    _count_sensor("acknowledged", lambda s: s.acknowledged),
    _count_sensor("no_data", lambda s: s.no_data),
    _count_sensor(
        "disabled", lambda s: s.disabled, entity_category=EntityCategory.DIAGNOSTIC
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the summary sensors, and a sensor for each generator.

    The callback is kept so that generators added later get theirs in place.
    """
    data = hass.data[DOMAIN]
    coordinator: SummaryCoordinator = data[DATA_SUMMARY]
    async_add_entities(
        SummarySensor(coordinator, description) for description in SENSORS
    )
    data[DATA_ADD_SENSORS] = async_add_entities
    data[DATA_GENERATORS].async_add_sensors()


class SummarySensor(SensorEntity):
    """One summary of all the alerts."""

    entity_description: SummarySensorDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    # The lists can grow long; the counts are what's worth keeping.
    _unrecorded_attributes = frozenset({ATTR_ENTITY_IDS})

    def __init__(
        self, coordinator: SummaryCoordinator, description: SummarySensorDescription
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"summary_{description.key}"
        # The spec's entity IDs (§11.2), whatever the translated name.
        self.entity_id = f"sensor.{DOMAIN}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Follow the summary."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> Any:
        """Return the summary's value."""
        return self.entity_description.value(self._coordinator.summary)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the per-priority counts and the entity IDs counted."""
        description = self.entity_description
        summary = self._coordinator.summary
        if description.entity_ids is None:
            return None
        attributes: dict[str, Any] = {}
        if description.by_priority is not None:
            attributes.update(
                {str(p): n for p, n in description.by_priority(summary).items()}
            )
        attributes[ATTR_ENTITY_IDS] = list(description.entity_ids(summary))
        return attributes


class GeneratorSensor(SensorEntity):
    """A generator: how many alerts it has made, and for which targets."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:creation"
    # The lists can grow long.
    _unrecorded_attributes = frozenset({ATTR_TARGETS, ATTR_ALERTS})

    def __init__(self, manager: GeneratorManager, subentry_id: str) -> None:
        """Initialize the sensor."""
        self._manager = manager
        self._subentry_id = subentry_id
        generator = manager.generators[subentry_id]
        self._attr_unique_id = generator_unique_id(subentry_id)
        # The spec's entity ID (§12.3), whatever the translated name; the
        # registry keeps it if the generator is renamed.
        self.entity_id = f"sensor.{DOMAIN}_generator_{slugify(generator.name)}"
        # Named directly, not translated: it follows the generator's name.
        self._attr_name = _generator_sensor_name(generator.name)

    async def async_added_to_hass(self) -> None:
        """Follow the generator, and let its alerts show this sensor as their
        generator (they were added first)."""
        self.async_on_remove(
            self._manager.async_add_listener(self._subentry_id, self._async_changed)
        )
        if (generator := self._manager.generators.get(self._subentry_id)) is not None:
            for entity in generator.entities.values():
                if entity.hass is not None:
                    entity.async_write_ha_state()

    @callback
    def _async_changed(self) -> None:
        if (generator := self._manager.generators.get(self._subentry_id)) is not None:
            self._attr_name = _generator_sensor_name(generator.name)
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        """Return the number of alerts the generator has made."""
        if (generator := self._manager.generators.get(self._subentry_id)) is None:
            return None
        return len(generator.definitions)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the targets, the alerts, and any problems."""
        if (generator := self._manager.generators.get(self._subentry_id)) is None:
            return None
        return {
            ATTR_TARGETS: generator.targets,
            ATTR_ALERTS: sorted(
                entity.entity_id
                for entity in generator.entities.values()
                if entity.entity_id is not None
            ),
            ATTR_PROBLEMS: list(generator.problems),
        }


def _generator_sensor_name(name: str) -> str:
    return f"Alert Redux generator {name}"
