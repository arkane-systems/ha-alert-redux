"""The Alert Redux integration."""

from __future__ import annotations

import inspect
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    service,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DATA,
    ATTR_DURATION,
    ATTR_UNTIL,
    CONF_ALERT,
    CONF_DEFAULT_GROUPS,
    CONF_FALLBACK_GROUP,
    CONF_SUPERSEDES,
    DATA_ADD_ENTITIES,
    DATA_COMPONENT,
    DATA_ENTITIES,
    DATA_GENERATORS,
    DATA_GENERATOR_SUBENTRIES,
    DATA_GROUPS,
    DATA_LABEL,
    DATA_NOTIFIER,
    DATA_OPTIONS,
    DATA_SETTINGS,
    DATA_STARTUP_UNTIL,
    DATA_STORE,
    DATA_SUBENTRIES,
    DATA_SUMMARY,
    DATA_SUPERSESSION,
    DOMAIN,
    NOTIFIER_STORAGE_KEY,
    SERVICE_ACK,
    SERVICE_DISABLE,
    SERVICE_DISMISS,
    SERVICE_ENABLE,
    SERVICE_FIRE,
    SERVICE_REFRESH_GENERATOR,
    SERVICE_SNOOZE,
    SERVICE_SUSPEND,
    SERVICE_UNACK,
    SUBENTRY_ALERT,
    SUBENTRY_GENERATOR,
    SUBENTRY_NOTIFIER_GROUP,
    Priority,
)
from .buttons import async_setup_buttons
from .definitions import AlertDefinition, generator_unique_id
from .entity import AlertEntity, create_alert_entity
from .generators import GeneratorManager, async_forget_alert
from .frontend import async_register_frontend, async_setup_websocket
from .labels import async_setup_label
from .model import Settings
from .notifications import (
    async_notifications_renamed,
    async_quiet_hours_ended,
)
from .notifier import GroupConfig, Notification, Notifier
from .issues import async_check_broken_references, async_check_default_groups
from .store import AlertStore
from .summary import SummaryCoordinator
from .supersession import Supersession

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# The summary sensors (spec §11.2); alerts are our own domain's EntityComponent.
PLATFORMS = [Platform.SENSOR]


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
    # Generators are sensors, so their action is the domain's own (spec §12.3).
    async def _async_refresh_generator(call: ServiceCall) -> None:
        _async_refresh_generators(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_GENERATOR,
        _async_refresh_generator,
        vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids}),
    )
    async_setup_websocket(hass)
    return True


@callback
def _async_refresh_generators(hass: HomeAssistant, call: ServiceCall) -> None:
    """Re-evaluate the targeted generators' targets now."""
    registry = er.async_get(hass)
    prefix = generator_unique_id("")
    generators: GeneratorManager | None = hass.data[DOMAIN].get(DATA_GENERATORS)
    subentry_ids: list[str] = []
    for entity_id in call.data[ATTR_ENTITY_ID]:
        entry = registry.async_get(entity_id)
        subentry_id = (
            entry.unique_id.removeprefix(prefix)
            if entry is not None
            and entry.platform == DOMAIN
            and entry.unique_id.startswith(prefix)
            else None
        )
        if generators is None or subentry_id not in generators.generators:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_generator",
                translation_placeholders={"entity_id": entity_id},
            )
        subentry_ids.append(subentry_id)
    for subentry_id in subentry_ids:
        generators.async_refresh(subentry_id)


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

    data[DATA_LABEL] = async_setup_label(hass, store)

    @callback
    def _quiet_hours_ended(
        group_id: str, held: dict[str, list[Notification]]
    ) -> list[Notification]:
        return async_quiet_hours_ended(hass, group_id, held)

    notifier = data[DATA_NOTIFIER] = Notifier(
        hass,
        store_key=NOTIFIER_STORAGE_KEY,
        issue_domain=DOMAIN,
        on_quiet_ended=_quiet_hours_ended,
    )
    await notifier.async_load()
    _async_configure_notifier(notifier, settings)
    groups = data[DATA_GROUPS] = _group_subentries(entry)
    notifier.async_set_groups(_group_configs(groups))
    notifier.async_start()
    async_check_default_groups(hass, entry, settings)

    # The platform fills in the entities; supersession looks them up there.
    entities: dict[str, AlertEntity] = {}
    data[DATA_ENTITIES] = entities
    data[DATA_SUPERSESSION] = Supersession(hass, entities, settings)
    data[DATA_SUMMARY] = SummaryCoordinator(hass)

    @callback
    def _generated_alerts_changed() -> None:
        # Generated alerts came or went (spec §12.3).
        data[DATA_SUPERSESSION].async_refresh()
        async_check_broken_references(hass, entry)

    # Generators work out their alerts before any is added, so that their
    # stored records aren't taken for deleted alerts' (spec §12.3).
    generators = data[DATA_GENERATORS] = GeneratorManager(
        hass, entry, store, settings, entities, _generated_alerts_changed
    )
    generators.async_load()
    data[DATA_GENERATOR_SUBENTRIES] = _generator_subentries(entry)
    # Alerts deleted while Home Assistant was down: their notifications are
    # cleared too, so the notifier comes first.
    _async_forget_deleted_alerts(hass, entry, store)

    component: EntityComponent[AlertEntity] = data[DATA_COMPONENT]
    if not await component.async_setup_entry(entry):
        return False
    # Restored pre-acknowledgements whose source is no longer acknowledged are
    # stale (spec §8.3); references to missing alerts are raised (§12.4).
    data[DATA_SUPERSESSION].async_sweep_pre_acks()
    async_check_broken_references(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_registry_updated(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        _async_alert_registry_updated(hass, entry, event)

    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            _async_registry_updated,
            event_filter=_is_alert_registry_event,
        )
    )

    # Subentry and option changes are applied in place, not by reloading the
    # entry, so that other alerts don't go through unavailable and no_data.
    data[DATA_SUBENTRIES] = _alert_subentries(entry)
    data[DATA_OPTIONS] = dict(entry.options)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    # Taps on notification buttons (spec §9.11).
    entry.async_on_unload(async_setup_buttons(hass))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Alert Redux config entry."""
    data = hass.data[DOMAIN]
    data[DATA_GENERATORS].async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    unloaded = await data[DATA_COMPONENT].async_unload_entry(entry) and unloaded
    await data[DATA_NOTIFIER].async_stop()
    await data[DATA_STORE].async_flush()
    return unloaded


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Add, edit, and forget alerts, and apply new defaults, without a reload."""
    data = hass.data[DOMAIN]
    entities: dict[str, AlertEntity] = data[DATA_ENTITIES]
    old: dict[str, tuple[str, dict[str, Any]]] = data[DATA_SUBENTRIES]
    new = data[DATA_SUBENTRIES] = _alert_subentries(entry)

    # Home Assistant removes a deleted subentry's entities itself, through the
    # entity registry; what's left is their stored records and deleted events.
    generators: GeneratorManager = data[DATA_GENERATORS]
    old_generators: dict[str, tuple[str, dict[str, Any]]] = data[
        DATA_GENERATOR_SUBENTRIES
    ]
    new_generators = data[DATA_GENERATOR_SUBENTRIES] = _generator_subentries(entry)
    removed_generators = old_generators.keys() - new_generators.keys()
    for subentry_id in removed_generators:
        generators.async_remove_generator(subentry_id)
    if (removed := old.keys() - new.keys()) or removed_generators:
        for subentry_id in removed:
            entities.pop(subentry_id, None)
        _async_forget_deleted_alerts(hass, entry, data[DATA_STORE])

    for subentry_id in new.keys() - old.keys():
        entity = create_alert_entity(
            AlertDefinition.from_subentry(entry.subentries[subentry_id]),
            data[DATA_STORE],
            data[DATA_SETTINGS],
        )
        entities[subentry_id] = entity
        data[DATA_ADD_ENTITIES]([entity], config_subentry_id=subentry_id)

    for subentry_id in new.keys() & old.keys():
        if new[subentry_id] != old[subentry_id] and subentry_id in entities:
            entities[subentry_id].async_update_config(
                AlertDefinition.from_subentry(entry.subentries[subentry_id])
            )

    for subentry_id in new_generators.keys() - old_generators.keys():
        generators.async_add_generator(entry.subentries[subentry_id])
    for subentry_id in new_generators.keys() & old_generators.keys():
        if new_generators[subentry_id] != old_generators[subentry_id]:
            generators.async_update_generator(entry.subentries[subentry_id])

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

    # Relationships, or the alerts themselves, may have changed (spec §8).
    data[DATA_SUPERSESSION].async_refresh()
    async_check_broken_references(hass, entry)
    async_check_default_groups(hass, entry, data[DATA_SETTINGS])


@callback
def _is_alert_registry_event(data: er.EventEntityRegistryUpdatedData) -> bool:
    """Return whether an entity registry change is to an alert entity."""
    prefix = f"{DOMAIN}."
    return data["entity_id"].startswith(prefix) or (
        data["action"] == "update"
        and data.get("old_entity_id", "").startswith(prefix)
    )


@callback
def _async_alert_registry_updated(
    hass: HomeAssistant, entry: ConfigEntry, event: Event[er.EventEntityRegistryUpdatedData]
) -> None:
    """Follow an alert's entity ID being renamed, and recheck references (§12.4).

    An alert being added or removed may fix or break other alerts' references.
    """
    data = event.data
    if data["action"] == "update" and (old := data.get("old_entity_id")):
        _async_follow_rename(hass, entry, old, data["entity_id"])
    hass.data[DOMAIN][DATA_SUPERSESSION].async_refresh()
    async_check_broken_references(hass, entry)


@callback
def _async_follow_rename(
    hass: HomeAssistant, entry: ConfigEntry, old: str, new: str
) -> None:
    """Rewrite references to a renamed alert in the other alerts' subentries, and
    follow its notifications' lifecycle key (spec §9.10).

    Pre-acknowledgements are kept by unique ID, so they need no rewriting.
    """
    async_notifications_renamed(hass, old, new)
    for subentry in list(entry.subentries.values()):
        # Generators' relationships refer to fixed alerts too (spec §12.3).
        if subentry.subentry_type not in (SUBENTRY_ALERT, SUBENTRY_GENERATOR):
            continue
        data = dict(subentry.data)
        if data.get(CONF_ALERT) == old:
            data[CONF_ALERT] = new
        relationships = data.get(CONF_SUPERSEDES) or []
        if any(rel.get(CONF_ALERT) == old for rel in relationships):
            data[CONF_SUPERSEDES] = [
                {**rel, CONF_ALERT: new} if rel.get(CONF_ALERT) == old else rel
                for rel in relationships
            ]
        if data != subentry.data:
            hass.config_entries.async_update_subentry(entry, subentry, data=data)


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
        fallback_group=settings.fallback_group,
        retry_timeout=settings.retry_timeout,
        quiet_entity=settings.quiet_entity,
        quiet_threshold=settings.quiet_threshold.urgency,
    )


def _generator_subentries(
    entry: ConfigEntry,
) -> dict[str, tuple[str, dict[str, Any]]]:
    """Return what identifies a change to each generator subentry."""
    return {
        subentry_id: (subentry.title, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_GENERATOR
    }


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
        GroupConfig.from_dict(group_id, name, definition, _threshold_urgency)
        for group_id, (name, definition) in groups.items()
    ]


def _threshold_urgency(priority: str) -> int:
    """Return a group's quiet-hours threshold, a priority, as an urgency."""
    return Priority(priority).urgency


def _async_forget_deleted_alerts(
    hass: HomeAssistant, entry: ConfigEntry, store: AlertStore
) -> None:
    """Drop stored alerts whose subentry or generator target is gone, announcing
    each deletion and clearing its notifications."""
    current = {
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_ALERT
    } | hass.data[DOMAIN][DATA_GENERATORS].generated_ids()
    for unique_id in store.alert_ids() - current:
        async_forget_alert(hass, store, unique_id)
