"""Tests for serving the card: the version command and the refresh notification."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.components import persistent_notification
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import (
    ResourceStorageCollection,
    ResourceYAMLCollection,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.alert_redux.const import CARD_URL, DOMAIN, STORAGE_KEY
from custom_components.alert_redux.frontend import REFRESH_NOTIFICATION_ID

from .conftest import SetupAlerts, alert_subentry, group_subentry


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


async def test_notification_apart_from_an_alerts(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An alert named Card Updated has a notification of its own, and an
    undismissed refresh notification from before is replaced."""
    persistent_notification.async_create(hass, "Old", notification_id="x")
    persistent_notification.async_create(
        hass, "Refresh", notification_id=f"{DOMAIN}_card_updated"
    )
    await setup_alerts(
        alert_subentry("Card Updated", notifier_groups=["persistent"]),
        group_subentry("Persistent", "persistent", persistent=True),
    )
    notifications = await _notifications(hass)
    assert f"{DOMAIN}_card_updated" not in notifications  # the old one
    await hass.services.async_call(
        DOMAIN, "fire", {"entity_id": f"{DOMAIN}.card_updated"}, blocking=True
    )
    await hass.async_block_till_done()
    notifications = await _notifications(hass)
    assert REFRESH_NOTIFICATION_ID in notifications
    assert f"{DOMAIN}_card_updated" in notifications  # the alert's
    assert "x" in notifications


async def test_upgrade_keeps_a_card_updated_alerts_notification(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """Replacing the old refresh notification leaves an alert's that has its ID:
    on an upgrade, the alert is registered, though not yet added."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"alerts": {}, "card_version": "0.0.1"},
    }
    er.async_get(hass).async_get_or_create(
        DOMAIN, DOMAIN, "card", suggested_object_id="card_updated"
    )
    persistent_notification.async_create(
        hass, "Card Updated is firing.", notification_id=f"{DOMAIN}_card_updated"
    )
    await setup_alerts(
        alert_subentry("Card Updated", "card", notifier_groups=["persistent"]),
        group_subentry("Persistent", "persistent", persistent=True),
    )
    notifications = await _notifications(hass)
    assert REFRESH_NOTIFICATION_ID in notifications
    assert f"{DOMAIN}_card_updated" in notifications


@pytest.fixture
def extra_modules(hass: HomeAssistant) -> set[str]:
    """Stand in for the frontend (which needs its build to set up) and its URLs."""
    hass.data[DATA_EXTRA_MODULE_URL] = urls = set()
    return urls


def _card_urls(urls: Any) -> list[str]:
    return [(u.get("url") if isinstance(u, dict) else u).split("?")[0] for u in urls]


async def test_storage_resource_registered(
    hass: HomeAssistant, setup_alerts: SetupAlerts, extra_modules: set[str]
) -> None:
    """In storage mode the card is a resource."""
    await setup_alerts()
    assert _card_urls(hass.data[LOVELACE_DATA].resources.async_items()) == [CARD_URL]
    assert not extra_modules


async def test_storage_resource_current_left_loaded(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """A resource that's already current is kept, and HA isn't left to reload it."""
    integration = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_URL}?v={integration.version}"
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace_resources",
        "data": {"items": [{"id": "card", "type": "module", "url": url}]},
    }
    # The fixture's lovelace setup made the collection before the store was filled.
    resources = ResourceStorageCollection(hass, hass.data[LOVELACE_DATA].dashboards[None])
    hass.data[LOVELACE_DATA].resources = resources

    await setup_alerts()
    assert resources.loaded
    assert [item["url"] for item in resources.async_items()] == [url]


@pytest.mark.parametrize(
    ("error", "level"),
    [(HomeAssistantError("store"), logging.WARNING), (KeyError("id"), logging.ERROR)],
)
async def test_storage_resource_error_falls_back(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    extra_modules: set[str],
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    level: int,
) -> None:
    """An error from the resource collection, expected or not, doesn't fail setup."""
    with patch.object(ResourceStorageCollection, "async_create_item", side_effect=error):
        await setup_alerts()
    assert _card_urls(extra_modules) == [CARD_URL]
    assert any(
        r.levelno == level and "Lovelace resource" in r.message for r in caplog.records
    )
    assert REFRESH_NOTIFICATION_ID in await _notifications(hass)


async def test_yaml_resources_fall_back_to_extra_js(
    hass: HomeAssistant, setup_alerts: SetupAlerts, extra_modules: set[str]
) -> None:
    """Where resources are a read-only YAML list, the card loads in every page.

    That's so even when the user lists the card there too: they can reload the list
    without it, and the card guards against being defined twice.
    """
    hass.data[LOVELACE_DATA].resource_mode = "yaml"
    hass.data[LOVELACE_DATA].resources = ResourceYAMLCollection(
        [{"type": "module", "url": CARD_URL}]
    )

    await setup_alerts()
    assert _card_urls(extra_modules) == [CARD_URL]


async def test_frontend_not_loaded(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Without the frontend nothing loads the card, and a reload doesn't serve it again."""
    hass.data[LOVELACE_DATA].resource_mode = "yaml"
    hass.data[LOVELACE_DATA].resources = ResourceYAMLCollection([])

    with patch.object(
        hass.http,
        "async_register_static_paths",
        wraps=hass.http.async_register_static_paths,
    ) as register:
        entry = await setup_alerts()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert register.call_count == 1
    assert DATA_EXTRA_MODULE_URL not in hass.data
    assert REFRESH_NOTIFICATION_ID not in await _notifications(hass)
