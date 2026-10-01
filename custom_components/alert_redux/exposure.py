"""Exposing entities to voice assistants, once (spec §14.1, §14.2).

Alerts are exposed to Assist, and their proxies to Alexa and Google (and hidden
from Assist), once each, by the rule the alerts label follows (§11.5): what's
been done is remembered in the alert's stored record, and never forced back.
"""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
)
from homeassistant.core import HomeAssistant, callback

ASSIST = "conversation"
ALEXA = "cloud.alexa"
GOOGLE = "cloud.google_assistant"


@callback
def async_set_exposure(
    hass: HomeAssistant, entity_id: str, exposure: Mapping[str, bool]
) -> bool:
    """Expose an entity to assistants, or hide it; return whether it was done.

    Exposure belongs to Home Assistant's own core integration, so it can't be
    set before that's loaded (bare tests aren't); the caller tries again later.
    """
    if "homeassistant" not in hass.config.components:
        return False
    for assistant, should_expose in exposure.items():
        async_expose_entity(hass, assistant, entity_id, should_expose)
    return True
