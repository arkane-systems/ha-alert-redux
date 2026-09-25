"""Serve the bundled Lovelace card(s) and register them with the dashboard.

The card bundle lives inside the integration package, so a single HACS install of the
integration delivers both. On setup we expose the bundle directory via a static path,
then register the card as a Lovelace *resource* (storage-mode dashboards). If the
Lovelace resource collection is unavailable (e.g. YAML-mode dashboards), we fall back
to ``add_extra_js_url``, which loads the module app-wide.

The resource URL carries a ``?v=<version>`` query so that browsers pick up a new
bundle after an upgrade; an existing resource pointing at an older version is updated
in place rather than duplicated.

Browsers only load dashboard resources when the page loads, so after an install or
upgrade the new card isn't used until the page is refreshed. We can't do that from
here: instead a persistent notification asks for it, once per version, and the card
itself offers a reload when its version differs from ours (``alert_redux/info``).
"""

from __future__ import annotations

import logging
from pathlib import Path

from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration

from .const import CARD_URL, CARD_URL_BASE, DOMAIN
from .store import AlertStore

_LOGGER = logging.getLogger(__name__)

_DATA_REGISTERED = "frontend_registered"

REFRESH_NOTIFICATION_ID = f"{DOMAIN}_card_updated"


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register the websocket commands the cards use."""
    websocket_api.async_register_command(hass, _websocket_info)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/info"})
@websocket_api.async_response
async def _websocket_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the integration's version, which the card compares with its own."""
    integration = await async_get_integration(hass, DOMAIN)
    connection.send_result(msg["id"], {"version": str(integration.version)})


async def async_register_frontend(hass: HomeAssistant, store: AlertStore) -> None:
    """Serve the card bundle and make dashboards load it. Idempotent; never raises."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_DATA_REGISTERED):
        return

    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    CARD_URL_BASE, str(Path(__file__).parent / "frontend"), False
                )
            ]
        )
    except Exception:  # noqa: BLE001 - the card is optional; never block setup
        _LOGGER.warning("Could not serve the Alert Redux card bundle", exc_info=True)
        return

    integration = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_URL}?v={integration.version}"

    if not await _async_register_lovelace_resource(hass, url):
        from homeassistant.components.frontend import add_extra_js_url

        try:
            add_extra_js_url(hass, url)
        except Exception:  # noqa: BLE001 - e.g. the frontend isn't loaded
            _LOGGER.warning("Could not load the Alert Redux card", exc_info=True)
            return
        _LOGGER.debug("Loaded Alert Redux card via add_extra_js_url")

    data[_DATA_REGISTERED] = True
    _async_announce_version(hass, store, str(integration.version))


@callback
def _async_announce_version(hass: HomeAssistant, store: AlertStore, version: str) -> None:
    """Ask for a browser refresh the first time this card version is served."""
    if store.card_version == version:
        return
    persistent_notification.async_create(
        hass,
        f"The Alert Redux card is now version {version}. Refresh your browser "
        "(or, in the companion app, reload the page or clear its frontend cache) "
        "to start using it. Until then, dashboards may show an older card, or "
        "\"Custom element not found\".",
        title="Alert Redux card updated",
        notification_id=REFRESH_NOTIFICATION_ID,
    )
    store.set_card_version(version)


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    """Add or update the card as a storage-mode Lovelace resource.

    Returns False if the resource collection is not available, so the caller can
    fall back to another loading mechanism.
    """
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None or not hasattr(resources, "async_create_item"):
        return False

    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()

        for item in resources.async_items():
            if (item.get("url") or "").split("?")[0] != CARD_URL:
                continue
            if item["url"] != url:
                await resources.async_update_item(
                    item["id"], {"res_type": "module", "url": url}
                )
                _LOGGER.info("Updated Lovelace resource to %s", url)
            return True

        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.info("Registered Lovelace resource %s", url)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Lovelace resource registration unavailable", exc_info=True)
        return False
    return True
