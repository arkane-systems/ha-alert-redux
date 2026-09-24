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

from .const import DATA_STORE, DOMAIN, SUBENTRY_ALERT
from .entity import AlertEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an entity for every alert subentry."""
    store = hass.data[DOMAIN][DATA_STORE]
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_ALERT:
            continue
        async_add_entities(
            [AlertEntity(subentry, store)], config_subentry_id=subentry.subentry_id
        )
