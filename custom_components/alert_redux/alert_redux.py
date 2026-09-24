"""The alert_redux entity platform: one alert entity per alert subentry.

Alert entities live in the integration's own domain (``alert_redux.*``), so they're
added through the integration's EntityComponent, which loads this module as the
platform for the config entry. Adding each entity with its subentry lets Home
Assistant remove it when the subentry is deleted.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_ENTITIES, DATA_SETTINGS, DATA_STORE, DOMAIN, SUBENTRY_ALERT
from .entity import create_alert_entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an entity for every alert subentry."""
    data = hass.data[DOMAIN]
    entities = data[DATA_ENTITIES] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_ALERT:
            continue
        entity = create_alert_entity(subentry, data[DATA_STORE], data[DATA_SETTINGS])
        entities[subentry.subentry_id] = entity
        async_add_entities([entity], config_subentry_id=subentry.subentry_id)
