"""The Alert Redux integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import (
    ALERTS_DEVICE_ID,
    ALERTS_DEVICE_NAME,
    ATTR_DATA,
    ATTR_KIND,
    ATTR_NAME,
    ATTR_NEW_STATE,
    ATTR_OLD_STATE,
    ATTR_PRIORITY,
    ATTR_USER_ID,
    DATA_ADD_ENTITIES,
    DATA_COMPONENT,
    DATA_ENTITIES,
    DATA_OPTIONS,
    DATA_SETTINGS,
    DATA_STARTUP_UNTIL,
    DATA_STORE,
    DATA_SUBENTRIES,
    DOMAIN,
    EVENT_DELETED,
    SERVICE_ACK,
    SERVICE_DISMISS,
    SERVICE_FIRE,
    SERVICE_UNACK,
    SUBENTRY_ALERT,
)
from .entity import AlertEntity, create_alert_entity
from .frontend import async_register_frontend, async_setup_websocket
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
    async_setup_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alert Redux from a config entry."""
    data = hass.data[DOMAIN]
    if (store := data.get(DATA_STORE)) is None:
        store = data[DATA_STORE] = AlertStore(hass)
        await store.async_load()

    await async_register_frontend(hass, store)

    settings = data[DATA_SETTINGS] = Settings.from_options(entry.options)
    # The startup delay holds back condition alerts' first evaluation, but only
    # while Home Assistant is starting, not on later reloads (spec §15.3).
    data[DATA_STARTUP_UNTIL] = (
        dt_util.utcnow() + settings.startup_delay
        if hass.state is not CoreState.running and settings.startup_delay
        else None
    )

    _async_forget_deleted_alerts(hass, entry, store)
    await _async_create_alerts_device(hass, entry)

    component: EntityComponent[AlertEntity] = data[DATA_COMPONENT]
    if not await component.async_setup_entry(entry):
        return False

    # Subentry and option changes are applied in place, not by reloading the
    # entry, so that other alerts don't go through unavailable and no_data.
    data[DATA_SUBENTRIES] = _alert_subentries(entry)
    data[DATA_OPTIONS] = dict(entry.options)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Alert Redux config entry."""
    data = hass.data[DOMAIN]
    unloaded = await data[DATA_COMPONENT].async_unload_entry(entry)
    await data[DATA_STORE].async_flush()
    return unloaded


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Add, edit, and forget alerts, and apply new defaults, without a reload."""
    data = hass.data[DOMAIN]
    entities: dict[str, AlertEntity] = data[DATA_ENTITIES]
    old: dict[str, tuple[str, dict[str, Any]]] = data[DATA_SUBENTRIES]
    new = data[DATA_SUBENTRIES] = _alert_subentries(entry)

    # Home Assistant removes a deleted subentry's entity itself, through the
    # entity registry; what's left is its stored record and the deleted event.
    if removed := old.keys() - new.keys():
        for subentry_id in removed:
            entities.pop(subentry_id, None)
        _async_forget_deleted_alerts(hass, entry, data[DATA_STORE])

    for subentry_id in new.keys() - old.keys():
        entity = create_alert_entity(
            entry.subentries[subentry_id], data[DATA_STORE], data[DATA_SETTINGS]
        )
        entities[subentry_id] = entity
        data[DATA_ADD_ENTITIES]([entity], config_subentry_id=subentry_id)

    for subentry_id in new.keys() & old.keys():
        if new[subentry_id] != old[subentry_id] and subentry_id in entities:
            entities[subentry_id].async_update_config(entry.subentries[subentry_id])

    if dict(entry.options) != data[DATA_OPTIONS]:
        data[DATA_OPTIONS] = dict(entry.options)
        data[DATA_SETTINGS].update(Settings.from_options(entry.options))
        for entity in entities.values():
            entity.async_settings_changed()


async def _async_create_alerts_device(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create the device every alert entity belongs to (spec §11.5).

    It's created against the config entry itself, not only through the alerts'
    subentries, so that it exists (and keeps its ID) even when there are no alerts.
    """
    integration = await async_get_integration(hass, DOMAIN)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, ALERTS_DEVICE_ID)},
        name=ALERTS_DEVICE_NAME,
        manufacturer="Arkane Systems",
        model="Alert Redux",
        sw_version=str(integration.version),
        entry_type=dr.DeviceEntryType.SERVICE,
    )


def _alert_subentries(entry: ConfigEntry) -> dict[str, tuple[str, dict[str, Any]]]:
    """Return what identifies a change to each alert subentry."""
    return {
        subentry_id: (subentry.title, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_ALERT
    }


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
