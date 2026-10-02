"""Voice proxies for Alexa and Google Home (spec §14.2).

Neither assistant can see an alert entity, so an alert can opt into a proxy
switch (on while it's active; off to acknowledge it, on again to remove the
acknowledgement) and a snooze button. The ProxyManager makes and removes them
as alerts' options change, keeps them in step with their alerts, and gives them
their alert's area and labels.

Proxies act through the alert actions, with their own context, so the rules of
§6 and §16 apply unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ALERT,
    CONF_PROXY_SNOOZE_BUTTON,
    CONF_PROXY_SWITCH,
    DATA_ENTITIES,
    DATA_LABEL,
    DOMAIN,
)
from .exposure import ALEXA, ASSIST, GOOGLE, async_set_exposure

if TYPE_CHECKING:
    from .entity import AlertEntity

PROXY_SWITCH = "switch"
PROXY_SNOOZE = "snooze"

# Each kind of proxy: the alert's option for it, and its platform.
_KINDS = {
    PROXY_SWITCH: (CONF_PROXY_SWITCH, Platform.SWITCH),
    PROXY_SNOOZE: (CONF_PROXY_SNOOZE_BUTTON, Platform.BUTTON),
}


def proxy_unique_id(kind: str, alert_unique_id: str) -> str:
    """Return a proxy's unique ID."""
    return f"proxy_{kind}_{alert_unique_id}"


class ProxyEntity(Entity):
    """A proxy for one alert: it follows the alert, and acts on it."""

    _attr_should_poll = False
    kind = ""

    def __init__(self, manager: ProxyManager, alert_unique_id: str) -> None:
        """Initialize the proxy."""
        self._manager = manager
        self.alert_unique_id = alert_unique_id
        self._attr_unique_id = proxy_unique_id(self.kind, alert_unique_id)

    @property
    def alert(self) -> AlertEntity | None:
        """Return the alert, if it's there."""
        entity = self.hass.data[DOMAIN].get(DATA_ENTITIES, {}).get(self.alert_unique_id)
        return entity if entity is not None and entity.hass is not None else None

    @property
    def alert_name(self) -> str:
        """Return the alert's name, as shown (a registry rename included)."""
        if (alert := self.alert) is None:
            return self._attr_name or ""
        state = self.hass.states.get(alert.entity_id)
        return state.name if state is not None else alert.name or alert.entity_id

    @property
    def available(self) -> bool:
        """Return whether the alert is there to act on."""
        if (alert := self.alert) is None:
            return False
        state = self.hass.states.get(alert.entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the alert's entity ID."""
        alert = self.alert
        return {ATTR_ALERT: alert.entity_id if alert is not None else None}

    async def async_added_to_hass(self) -> None:
        """Take on the alert's area and labels, and be exposed, once."""
        self._manager.async_proxy_added(self)

    async def async_will_remove_from_hass(self) -> None:
        """Stop following the alert."""
        self._manager.async_proxy_removed(self)

    def _require_alert(self) -> AlertEntity:
        if (alert := self.alert) is None:
            raise ServiceValidationError(f"{self.entity_id}'s alert isn't there.")
        return alert

    def _not_firing(self, alert: AlertEntity) -> ServiceValidationError:
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_firing",
            translation_placeholders={"entity_id": alert.entity_id},
        )

    async def _async_act(
        self, alert: AlertEntity, service: str, data: dict[str, Any] | None = None
    ) -> None:
        """Call an alert action, as this proxy's caller."""
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: alert.entity_id, **(data or {})},
            blocking=True,
            context=self._context,
        )


class ProxyManager:
    """Makes, removes, and updates the alerts' proxies."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self.hass = hass
        self._add: dict[str, AddEntitiesCallback] = {}
        self._factories: dict[str, type[ProxyEntity]] = {}
        # The proxies made, by alert unique ID and kind.
        self._proxies: dict[str, dict[str, ProxyEntity]] = {}

    @callback
    def async_platform_ready(
        self, kind: str, factory: type[ProxyEntity], add: AddEntitiesCallback
    ) -> None:
        """Take a platform's add-entities callback, and make its proxies."""
        self._factories[kind] = factory
        self._add[kind] = add
        for alert in list(self.hass.data[DOMAIN].get(DATA_ENTITIES, {}).values()):
            if alert.hass is not None:
                self._async_sync(alert)

    @callback
    def async_alert_written(self, alert: AlertEntity) -> None:
        """Bring an alert's proxies into line with its options, and its state."""
        self._async_sync(alert)
        for proxy in self._proxies.get(alert.unique_id, {}).values():
            if proxy.hass is not None:
                proxy.async_write_ha_state()

    @callback
    def _async_sync(self, alert: AlertEntity) -> None:
        unique_id = alert.unique_id
        assert unique_id is not None
        proxies = self._proxies.setdefault(unique_id, {})
        for kind, (option, _platform) in _KINDS.items():
            wanted = bool(alert.definition.data.get(option))
            if wanted and kind not in proxies and kind in self._add:
                proxy = proxies[kind] = self._factories[kind](self, unique_id)
                # The alert's own subentry, or its generator's: removing that
                # removes the proxy too.
                self._add[kind](
                    [proxy],
                    config_subentry_id=alert.definition.generator or unique_id,
                )
            elif not wanted and kind in proxies:
                self._async_remove(unique_id, kind)
                # Enabled again, it's a new proxy, exposed again.
                alert.async_proxy_forgotten(kind)

    @callback
    def async_alert_forgotten(self, unique_id: str) -> None:
        """Remove a deleted alert's proxies."""
        for kind in _KINDS:
            self._async_remove(unique_id, kind)
        self._proxies.pop(unique_id, None)

    @callback
    def _async_remove(self, unique_id: str, kind: str) -> None:
        proxy = self._proxies.get(unique_id, {}).pop(kind, None)
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            _KINDS[kind][1], DOMAIN, proxy_unique_id(kind, unique_id)
        )

        async def _remove() -> None:
            if proxy is not None and proxy.hass is not None:
                await proxy.async_remove(force_remove=True)
            if entity_id is not None and registry.async_get(entity_id) is not None:
                registry.async_remove(entity_id)

        self.hass.async_create_task(_remove(), eager_start=True)

    @callback
    def async_proxy_added(self, proxy: ProxyEntity) -> None:
        """Give a new proxy its alert's area and labels, and expose it, once."""
        self._proxies.setdefault(proxy.alert_unique_id, {})[proxy.kind] = proxy
        if (alert := proxy.alert) is None:
            return
        self._async_copy_registry(alert, proxy)
        if proxy.kind not in alert.proxies_exposed and async_set_exposure(
            self.hass, proxy.entity_id, {ALEXA: True, GOOGLE: True, ASSIST: False}
        ):
            alert.async_proxy_exposed(proxy.kind)

    @callback
    def async_proxy_removed(self, proxy: ProxyEntity) -> None:
        """Forget a proxy that's gone (unloaded or removed)."""
        proxies = self._proxies.get(proxy.alert_unique_id, {})
        if proxies.get(proxy.kind) is proxy:
            del proxies[proxy.kind]

    @callback
    def async_alert_registry_changed(self, alert: AlertEntity) -> None:
        """Follow a change to an alert's area or labels."""
        for proxy in self._proxies.get(alert.unique_id, {}).values():
            if proxy.hass is not None:
                self._async_copy_registry(alert, proxy)

    @callback
    def _async_copy_registry(self, alert: AlertEntity, proxy: ProxyEntity) -> None:
        """Give a proxy its alert's area and labels, but not the alerts label."""
        registry = er.async_get(self.hass)
        source = registry.async_get(alert.entity_id)
        target = registry.async_get(proxy.entity_id)
        if source is None or target is None:
            return
        labels = set(source.labels) - {self.hass.data[DOMAIN].get(DATA_LABEL)}
        if target.area_id != source.area_id or target.labels != labels:
            registry.async_update_entity(
                proxy.entity_id, area_id=source.area_id, labels=labels
            )
