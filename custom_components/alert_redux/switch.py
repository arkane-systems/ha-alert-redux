"""The proxy switches, for Alexa and Google Home (spec §14.2).

A proxy switch emulates the built-in alert integration's entity: it's on while
its alert is active (unacknowledged). Turning it off acknowledges the alert, and
turning it on again removes the acknowledgement (and any snooze). It can't be
turned on while the alert isn't firing. On Alexa, Home Assistant also shows a
switch as a contact sensor, which can start a routine as the alert fires.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_PROXIES, DOMAIN, SERVICE_ACK, SERVICE_UNACK, AlertState
from .proxies import PROXY_SWITCH, ProxyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the alerts' proxy switches."""
    hass.data[DOMAIN][DATA_PROXIES].async_platform_ready(
        PROXY_SWITCH, ProxySwitch, async_add_entities
    )


class ProxySwitch(ProxyEntity, SwitchEntity):
    """On while the alert is active; off to acknowledge it."""

    kind = PROXY_SWITCH
    _attr_icon = "mdi:alert"

    @property
    def name(self) -> str:
        """Return the alert's name."""
        return self.alert_name

    @property
    def is_on(self) -> bool:
        """Return whether the alert wants acknowledging: active (firing, and
        unacknowledged), or latched (spec §10)."""
        alert = self.alert
        return alert is not None and alert.state in (
            AlertState.ACTIVE,
            AlertState.LATCHED,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Acknowledge the alert; an unacknowledgeable one refuses (§6.1)."""
        alert = self._require_alert()
        if alert.state in (AlertState.ACTIVE, AlertState.LATCHED):
            await self._async_act(alert, SERVICE_ACK)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Remove the alert's acknowledgement; refused if it isn't firing."""
        alert = self._require_alert()
        if alert.state == AlertState.ACK:
            await self._async_act(alert, SERVICE_UNACK)
        elif not alert.firing:
            raise self._not_firing(alert)
