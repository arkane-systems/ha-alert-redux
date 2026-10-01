"""Voice control through Assist (spec §14.1).

SPIKE: a single conversation trigger that answers with what it heard, to check
that an integration's sentence trigger can speak its reply, through the built-in
agent and through a pipeline with an LLM agent.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers.script import ScriptRunResult
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.trigger import async_initialize_triggers

from .const import DOMAIN
from .triggers import async_validate_triggers

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_voice(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Attach the voice commands once Home Assistant has started."""
    unsubs: list[CALLBACK_TYPE] = []

    async def _attach() -> None:
        if "conversation" not in hass.config.components:
            return
        config = await async_validate_triggers(
            hass,
            [{"trigger": "conversation", "command": ["alert redux spike {thing}"]}],
        )
        unsub = await async_initialize_triggers(
            hass, config, _async_spoken, DOMAIN, "voice", _log
        )
        if unsub is not None:
            unsubs.append(unsub)

    @callback
    def _started(_hass: HomeAssistant) -> None:
        hass.async_create_task(_attach(), f"{DOMAIN} voice")

    unsubs.append(async_at_started(hass, _started))

    @callback
    def _unload() -> None:
        while unsubs:
            unsubs.pop()()

    return _unload


async def _async_spoken(
    run_variables: dict[str, Any], context: Context | None = None
) -> ScriptRunResult:
    trigger = run_variables["trigger"]
    heard = trigger["slots"].get("thing", "")
    user_id = trigger["user_input"]["context"].get("user_id")
    _LOGGER.warning("Spike heard %r from user %s", heard, user_id)
    return ScriptRunResult(
        conversation_response=f"Alert Redux heard {heard}.",
        service_response=None,
        variables={},
    )


def _log(level: int, message: str, **kwargs: Any) -> None:
    _LOGGER.log(level, "voice: %s", message, **kwargs)
