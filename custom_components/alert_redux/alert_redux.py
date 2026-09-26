"""The alert_redux entity platform: one alert entity per alert subentry, plus the
generated alerts.

Alert entities live in the integration's own domain (``alert_redux.*``), so they're
added through the integration's EntityComponent, which loads this module as the
platform for the config entry. Adding each entity with its subentry lets Home
Assistant remove it when the subentry is deleted.

Only the initial set is added here; the integration's update listener adds, edits,
and forgets alerts as their subentries change.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DATA_ADD_ENTITIES,
    DATA_ENTITIES,
    DATA_GENERATORS,
    DATA_SETTINGS,
    DATA_STORE,
    DOMAIN,
    SUBENTRY_ALERT,
)
from .definitions import AlertDefinition
from .entity import create_alert_entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an entity for every alert subentry.

    The callback is kept so that alerts added later can be added in place,
    without reloading the entry.
    """
    data = hass.data[DOMAIN]
    data[DATA_ADD_ENTITIES] = async_add_entities
    entities = data[DATA_ENTITIES]
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_ALERT:
            continue
        entity = create_alert_entity(
            AlertDefinition.from_subentry(subentry),
            data[DATA_STORE],
            data[DATA_SETTINGS],
        )
        entities[subentry.subentry_id] = entity
        async_add_entities([entity], config_subentry_id=subentry.subentry_id)
    # Then the generated alerts (spec §12.3).
    data[DATA_GENERATORS].async_start()
