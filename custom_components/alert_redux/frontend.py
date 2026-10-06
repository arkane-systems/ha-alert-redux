"""Serve the bundled Lovelace card(s) and register them with the dashboard.

The card bundle lives inside the integration package, so a single HACS install of the
integration delivers both. On setup we expose the bundle directory via a static path,
then register the card as a Lovelace *resource* (storage-mode dashboards). Where we
can't write resources (YAML-mode dashboards, where they're a read-only list, or no
Lovelace at all), we fall back to ``add_extra_js_url``, which loads the module in
every frontend page, out of sight of the dashboard's resource list.

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
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
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

    # http is a hard dependency, so a failure here is a bug: let it surface.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(Path(__file__).parent / "frontend"), False)]
    )

    integration = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_URL}?v={integration.version}"

    if not await _async_register_lovelace_resource(hass, url):
        if DATA_EXTRA_MODULE_URL not in hass.data:
            _LOGGER.info("The frontend isn't loaded, so the Alert Redux card isn't")
            return
        add_extra_js_url(hass, url)
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

    Returns False if we can't manage the resource (no Lovelace, or resources kept in
    YAML, where an entry the user has added themselves counts as registered), so the
    caller can fall back to another loading mechanism.
    """
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        return False

    resources = lovelace.resources
    if lovelace.resource_mode != "storage":
        # A read-only list: the user keeps it, and may have added the card to it.
        return any(
            (item.get("url") or "").split("?")[0] == CARD_URL
            for item in resources.async_items()
        )

    try:
        # async_items() sees nothing until the collection is loaded, and we'd then
        # create a duplicate of a resource that's already there.
        if not resources.loaded:
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
    except (HomeAssistantError, vol.Invalid):
        _LOGGER.warning(
            "Could not register the Alert Redux card as a Lovelace resource; "
            "loading it in every page instead",
            exc_info=True,
        )
        return False
    return True
