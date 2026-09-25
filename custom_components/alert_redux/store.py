"""Persistent state for Alert Redux (spec §15.1).

A single Store is the source of truth for everything that must survive a restart.
Each alert's record is keyed by its entity's unique ID and saved shortly after every
change; Home Assistant flushes pending delayed saves when it stops, and unloading the
config entry flushes too. The records also tell setup which alerts are new and which
have been deleted since the last run.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import (
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_SAVE_DELAY,
    STORAGE_VERSION,
)


class AlertStore:
    """The persisted records of every alert."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store; call async_load before use."""
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            private=True,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._alerts: dict[str, dict[str, Any]] = {}
        self._card_version: str | None = None
        self._label_id: str | None = None

    async def async_load(self) -> None:
        """Load the persisted records."""
        data = await self._store.async_load() or {}
        self._alerts = data.get("alerts", {})
        self._card_version = data.get("card_version")
        self._label_id = data.get("label_id")

    @property
    def card_version(self) -> str | None:
        """Return the card version the user was last told to refresh for."""
        return self._card_version

    @callback
    def set_card_version(self, version: str) -> None:
        """Remember the card version the user was told to refresh for."""
        self._card_version = version
        self._async_schedule_save()

    @property
    def label_id(self) -> str | None:
        """Return the ID of the alerts label, once it has been created."""
        return self._label_id

    @callback
    def set_label_id(self, label_id: str) -> None:
        """Remember the alerts label, so it's created only once."""
        self._label_id = label_id
        self._async_schedule_save()

    @callback
    def alert_ids(self) -> set[str]:
        """Return the unique IDs of every stored alert."""
        return set(self._alerts)

    @callback
    def get_alert(self, unique_id: str) -> dict[str, Any] | None:
        """Return the stored record for an alert, if any."""
        return self._alerts.get(unique_id)

    @callback
    def set_alert(self, unique_id: str, record: dict[str, Any]) -> None:
        """Store an alert's record and schedule a save."""
        self._alerts[unique_id] = record
        self._async_schedule_save()

    @callback
    def remove_alert(self, unique_id: str) -> None:
        """Forget an alert and schedule a save."""
        if self._alerts.pop(unique_id, None) is not None:
            self._async_schedule_save()

    async def async_flush(self) -> None:
        """Save now, replacing any pending delayed save."""
        await self._store.async_save(self._data())

    @callback
    def _async_schedule_save(self) -> None:
        self._store.async_delay_save(self._data, STORAGE_SAVE_DELAY)

    @callback
    def _data(self) -> dict[str, Any]:
        return {
            "alerts": self._alerts,
            "card_version": self._card_version,
            "label_id": self._label_id,
        }
