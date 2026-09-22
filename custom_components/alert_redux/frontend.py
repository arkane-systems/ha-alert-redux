"""Serve the bundled Lovelace card(s) and register them with the dashboard.

The card bundle lives inside the integration package, so a single HACS install of the
integration delivers both. On setup we expose the bundle directory via a static path,
then register the card as a Lovelace *resource* (storage-mode dashboards). If the
Lovelace resource collection is unavailable (e.g. YAML-mode dashboards), we fall back
to ``add_extra_js_url``, which loads the module app-wide.

The resource URL carries a ``?v=<version>`` query so that browsers pick up a new
bundle after an upgrade; an existing resource pointing at an older version is updated
in place rather than duplicated.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CARD_URL, CARD_URL_BASE, DOMAIN

_LOGGER = logging.getLogger(__name__)

_DATA_REGISTERED = "frontend_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
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

        add_extra_js_url(hass, url)
        _LOGGER.debug("Loaded Alert Redux card via add_extra_js_url")

    data[_DATA_REGISTERED] = True


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
