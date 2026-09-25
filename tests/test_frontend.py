"""Tests for serving the card: the version command and the refresh notification."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.alert_redux.const import DOMAIN, STORAGE_KEY
from custom_components.alert_redux.frontend import REFRESH_NOTIFICATION_ID

from .conftest import SetupAlerts


@pytest.fixture(autouse=True)
async def lovelace(hass: HomeAssistant) -> None:
    """Set up the dashboards, so that the card can be registered."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "lovelace", {})


async def _notifications(hass: HomeAssistant) -> dict[str, Any]:
    return persistent_notification._async_get_or_create_notifications(hass)  # noqa: SLF001


async def test_info_command(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_ws_client
) -> None:
    """The card can ask for the integration's version."""
    await setup_alerts()
    integration = await async_get_integration(hass, DOMAIN)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "alert_redux/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"version": str(integration.version)}


async def test_refresh_notification_once_per_version(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """A new card version asks for a browser refresh; restarts don't repeat it."""
    entry = await setup_alerts()
    assert REFRESH_NOTIFICATION_ID in await _notifications(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    integration = await async_get_integration(hass, DOMAIN)
    assert (
        hass_storage[STORAGE_KEY]["data"]["card_version"] == str(integration.version)
    )


async def test_no_notification_for_known_version(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    integration = await async_get_integration(hass, DOMAIN)
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"alerts": {}, "card_version": str(integration.version)},
    }
    await setup_alerts()
    assert REFRESH_NOTIFICATION_ID not in await _notifications(hass)


async def test_notification_for_upgrade(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"alerts": {}, "card_version": "0.0.1"},
    }
    await setup_alerts()
    assert REFRESH_NOTIFICATION_ID in await _notifications(hass)
