"""The Alert Redux integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DATA,
    ATTR_KIND,
    ATTR_NAME,
    ATTR_NEW_STATE,
    ATTR_OLD_STATE,
    ATTR_PRIORITY,
    ATTR_USER_ID,
    DATA_COMPONENT,
    DATA_SETTINGS,
    DATA_STARTUP_UNTIL,
    DATA_STORE,
    DOMAIN,
    EVENT_DELETED,
    SERVICE_ACK,
    SERVICE_DISMISS,
    SERVICE_FIRE,
    SERVICE_UNACK,
    SUBENTRY_ALERT,
)
from .entity import AlertEntity
from .frontend import async_register_frontend
from .model import AlertRuntime, Settings
from .store import AlertStore

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the alert entity component and its actions."""
    component = EntityComponent[AlertEntity](_LOGGER, DOMAIN, hass)
    hass.data.setdefault(DOMAIN, {})[DATA_COMPONENT] = component

    component.async_register_entity_service(
        SERVICE_FIRE, {vol.Optional(ATTR_DATA): dict}, "async_fire"
    )
    component.async_register_entity_service(SERVICE_DISMISS, None, "async_dismiss")
    component.async_register_entity_service(SERVICE_ACK, None, "async_ack")
    component.async_register_entity_service(SERVICE_UNACK, None, "async_unack")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alert Redux from a config entry."""
    await async_register_frontend(hass)

    data = hass.data[DOMAIN]
    if (store := data.get(DATA_STORE)) is None:
        store = data[DATA_STORE] = AlertStore(hass)
        await store.async_load()

    settings = data[DATA_SETTINGS] = Settings.from_options(entry.options)
    # The startup delay holds back condition alerts' first evaluation, but only
    # while Home Assistant is starting, not on later reloads (spec §15.3).
    data[DATA_STARTUP_UNTIL] = (
        dt_util.utcnow() + settings.startup_delay
        if hass.state is not CoreState.running and settings.startup_delay
        else None
    )

    _async_forget_deleted_alerts(hass, entry, store)

    component: EntityComponent[AlertEntity] = data[DATA_COMPONENT]
    if not await component.async_setup_entry(entry):
        return False

    # Adding, changing, or removing a subentry reloads the entry; alert state
    # survives through the store.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Alert Redux config entry."""
    data = hass.data[DOMAIN]
    unloaded = await data[DATA_COMPONENT].async_unload_entry(entry)
    await data[DATA_STORE].async_flush()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    hass.config_entries.async_schedule_reload(entry.entry_id)


def _async_forget_deleted_alerts(
    hass: HomeAssistant, entry: ConfigEntry, store: AlertStore
) -> None:
    """Drop stored alerts whose subentry is gone, announcing each deletion."""
    current = {
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_ALERT
    }
    for unique_id in store.alert_ids() - current:
        record = store.get_alert(unique_id) or {}
        store.remove_alert(unique_id)
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
