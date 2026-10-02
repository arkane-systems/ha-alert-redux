"""LLM tools for Alert Redux's voice commands (spec §14.1).

From Home Assistant 2026.8, integrations offer LLM agents their tools through
this platform; before that, Home Assistant offered every registered intent by
itself, so older versions get the same tools without it. Only the llm
integration imports this module.
"""

from __future__ import annotations

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import LLM_API_ASSIST, IntentTool, LLMContext, Tool

from .const import DOMAIN
from .voice import INTENTS, async_exposed_alerts

PROMPT = (
    "Alert Redux alerts (the alert_redux entities) are acknowledged, "
    "unacknowledged, and snoozed with the AlertReduxAcknowledge, "
    "AlertReduxUnacknowledge, and AlertReduxSnooze tools, never by turning them "
    "on or off. AlertReduxListFiring says which alerts are firing."
)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the voice commands as tools, if any alert is exposed."""
    if api_id != LLM_API_ASSIST or DOMAIN not in hass.data:
        return None
    if not async_exposed_alerts(hass, llm_context.assistant):
        return None
    handlers = {handler.intent_type: handler for handler in intent.async_get(hass)}
    tools: list[Tool] = [
        _intent_tool(intent_type, handlers[intent_type])
        for intent_type in INTENTS
        if intent_type in handlers
    ]
    return LLMTools(tools=tools, prompt=PROMPT) if tools else None


def _intent_tool(intent_type: str, handler: intent.IntentHandler) -> IntentTool:
    """Return an intent's tool, named with the domain as HA asks from 2026.9.

    In HA 2026.8, an IntentTool handled the intent its name named, so there the
    tool takes the intent's own name; from 2026.9 it keeps the intent type
    apart.
    """
    tool = IntentTool(f"{DOMAIN}__{intent_type}", handler)
    if not hasattr(tool, "intent_type"):
        tool = IntentTool(intent_type, handler)
    return tool
