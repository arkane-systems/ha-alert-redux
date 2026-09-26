"""The Alert Redux integration."""

from __future__ import annotations

import inspect
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DATA,
    ATTR_DURATION,
    ATTR_KIND,
    ATTR_NAME,
    ATTR_NEW_STATE,
    ATTR_OLD_STATE,
    ATTR_PRIORITY,
    ATTR_UNTIL,
    ATTR_USER_ID,
    CONF_DEFAULT_GROUPS,
    CONF_FALLBACK_GROUP,
    DATA_ADD_ENTITIES,
    DATA_COMPONENT,
    DATA_ENTITIES,
    DATA_GROUPS,
    DATA_LABEL,
    DATA_NOTIFIER,
    DATA_OPTIONS,
    DATA_SETTINGS,
    DATA_STARTUP_UNTIL,
    DATA_STORE,
    DATA_SUBENTRIES,
    DOMAIN,
    EVENT_DELETED,
    NOTIFIER_STORAGE_KEY,
    SERVICE_ACK,
    SERVICE_DISABLE,
    SERVICE_DISMISS,
    SERVICE_ENABLE,
    SERVICE_FIRE,
    SERVICE_SNOOZE,
    SERVICE_SUSPEND,
    SERVICE_UNACK,
    SUBENTRY_ALERT,
    SUBENTRY_NOTIFIER_GROUP,
)
from .entity import AlertEntity, create_alert_entity
from .frontend import async_register_frontend, async_setup_websocket
from .labels import async_setup_label
from .model import AlertRuntime, Settings
from .notifier import GroupConfig, Notifier
from .issues import async_check_default_groups
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
    component.async_register_entity_service(
        SERVICE_SNOOZE,
        {vol.Required(ATTR_DURATION): cv.positive_time_period},
        "async_snooze",
    )
    # Disabling is for maintenance and debugging, not everyday use (spec §16).
    _register_admin_entity_service(
        hass, component, SERVICE_DISABLE, None, "async_disable"
    )
    _register_admin_entity_service(
        hass, component, SERVICE_ENABLE, None, "async_enable"
    )
    _register_admin_entity_service(
        hass,
        component,
        SERVICE_SUSPEND,
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Exclusive(ATTR_DURATION, "end"): cv.positive_time_period,
                    vol.Exclusive(ATTR_UNTIL, "end"): cv.datetime,
                }
            ),
            cv.has_at_least_one_key(ATTR_DURATION, ATTR_UNTIL),
        ),
        "async_suspend",
    )
    async_setup_websocket(hass)
    return True


def _entity_services_take_admin_only(component: EntityComponent[AlertEntity]) -> bool:
    """Return whether this Home Assistant can make entity actions admin-only."""
    return (
        "admin_only"
        in inspect.signature(component.async_register_entity_service).parameters
    )


def _register_admin_entity_service(
    hass: HomeAssistant,
    component: EntityComponent[AlertEntity],
    name: str,
    schema: Any,
    method: str,
) -> None:
    """Register an entity action that only admins may call.

    Home Assistant 2026.9 added admin_only to entity actions. Before that, an admin
    action dispatches to the entities in the same way, with the same schema.
    """
    if _entity_services_take_admin_only(component):
        component.async_register_entity_service(name, schema, method, admin_only=True)
        return

    async def _async_handle(call: ServiceCall) -> None:
        # The component's own registry of entities, by entity ID, as it uses.
        await service.entity_service_call(hass, component._entities, method, call)

    service.async_register_admin_service(
        hass,
        DOMAIN,
        name,
        _async_handle,
        cv.make_entity_service_schema({}) if schema is None else schema,
    )


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
    data[DATA_LABEL] = async_setup_label(hass, store)

    notifier = data[DATA_NOTIFIER] = Notifier(
        hass, store_key=NOTIFIER_STORAGE_KEY, issue_domain=DOMAIN
    )
    await notifier.async_load()
    _async_configure_notifier(notifier, settings)
    groups = data[DATA_GROUPS] = _group_subentries(entry)
    notifier.async_set_groups(_group_configs(groups))
    notifier.async_start()
    async_check_default_groups(hass, entry, settings)

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
    await data[DATA_NOTIFIER].async_stop()
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

    groups = _group_subentries(entry)
    groups_changed = groups != data[DATA_GROUPS]
    if groups_changed:
        if deleted := data[DATA_GROUPS].keys() - groups.keys():
            _async_forget_deleted_groups(hass, entry, deleted)
        data[DATA_GROUPS] = groups
        data[DATA_NOTIFIER].async_set_groups(_group_configs(groups))

    if dict(entry.options) != data[DATA_OPTIONS]:
        data[DATA_OPTIONS] = dict(entry.options)
        data[DATA_SETTINGS].update(Settings.from_options(entry.options))
        _async_configure_notifier(data[DATA_NOTIFIER], data[DATA_SETTINGS])
        for entity in entities.values():
            entity.async_settings_changed()
    elif groups_changed:
        # Alerts show their groups' names.
        for entity in entities.values():
            if entity.hass is not None:
                entity.async_write_ha_state()

    async_check_default_groups(hass, entry, data[DATA_SETTINGS])


def _alert_subentries(entry: ConfigEntry) -> dict[str, tuple[str, dict[str, Any]]]:
    """Return what identifies a change to each alert subentry."""
    return {
        subentry_id: (subentry.title, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_ALERT
    }


def _async_forget_deleted_groups(
    hass: HomeAssistant, entry: ConfigEntry, deleted: set[str]
) -> None:
    """Drop deleted notifier groups from the default and fallback groups.

    Alerts' own group lists are left alone: a missing group is skipped, and an
    alert with none left notifies the fallback, whereas pruning its list to empty
    would silently make it notify nobody.
    """
    options = dict(entry.options)
    defaults = options.get(CONF_DEFAULT_GROUPS) or []
    if not deleted.isdisjoint(defaults):
        # Emptied, the defaults count as unset: alerts using them notify the
        # fallback, and a Repairs issue says so.
        options[CONF_DEFAULT_GROUPS] = [g for g in defaults if g not in deleted]
    if options.get(CONF_FALLBACK_GROUP) in deleted:
        options[CONF_FALLBACK_GROUP] = None
    if options != dict(entry.options):
        hass.config_entries.async_update_entry(entry, options=options)


def _async_configure_notifier(notifier: Notifier, settings: Settings) -> None:
    notifier.async_configure(
        fallback_group=settings.fallback_group, retry_timeout=settings.retry_timeout
    )


def _group_subentries(entry: ConfigEntry) -> dict[str, tuple[str, dict[str, Any]]]:
    """Return each notifier group subentry's name and definition."""
    return {
        subentry_id: (subentry.title, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_NOTIFIER_GROUP
    }


def _group_configs(
    groups: dict[str, tuple[str, dict[str, Any]]],
) -> list[GroupConfig]:
    return [
        GroupConfig.from_dict(group_id, name, definition)
        for group_id, (name, definition) in groups.items()
    ]


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
