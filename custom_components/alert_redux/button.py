"""The proxy snooze buttons, for Alexa and Google Home (spec §14.2).

"Snooze <name>" snoozes its alert for the alert's snooze button duration
(§9.11). The assistants show it as a scene. Unsnoozing is the proxy switch's.

Not to be confused with buttons.py, the notification buttons.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_DURATION,
    ATTR_SNOOZE_DURATION,
    DATA_PROXIES,
    DOMAIN,
    SERVICE_SNOOZE,
)
from .proxies import PROXY_SNOOZE, ProxyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the alerts' proxy snooze buttons."""
    hass.data[DOMAIN][DATA_PROXIES].async_platform_ready(
        PROXY_SNOOZE, ProxySnoozeButton, async_add_entities
    )


class ProxySnoozeButton(ProxyEntity, ButtonEntity):
    """Snoozes the alert for its snooze button duration."""

    kind = PROXY_SNOOZE
    _attr_icon = "mdi:alarm-snooze"

    @property
    def name(self) -> str:
        """Return "Snooze" and the alert's name."""
        return f"Snooze {self.alert_name}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the alert, and how long a press snoozes it for."""
        attributes = super().extra_state_attributes
        if (alert := self.alert) is not None:
            attributes[ATTR_SNOOZE_DURATION] = alert.button_snooze.total_seconds()
        return attributes

    async def async_press(self) -> None:
        """Snooze the alert; refused if it isn't firing or latched, or can't be
        snoozed."""
        alert = self._require_alert()
        if not alert.firing and not alert.latched:
            raise self._not_firing(alert)
        # Seconds, not a timedelta: the action call is recorded as an event.
        await self._async_act(
            alert, SERVICE_SNOOZE, {ATTR_DURATION: alert.button_snooze.total_seconds()}
        )
