"""Tests for the voice commands as LLM tools before HA 2026.8 (spec §14.1).

Before the llm integration's tools platform, HA's Assist API offered every
registered intent handler as a tool, if its platforms matched an exposed
domain. Only runs against such an HA (2026.6 or 2026.7, in the older-HA test
environment).
"""

from __future__ import annotations

import dataclasses
import importlib.util

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from .conftest import SetupAlerts, state_alert

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("homeassistant.components.llm") is not None,
    reason="HA 2026.8 and later offer tools through llm.py (test_llm.py)",
)

BACK = "alert_redux.back_door_open"


@pytest.fixture(autouse=True)
async def assist(hass: HomeAssistant) -> None:
    """Set up the core integration (for exposure), and conversation."""
    for domain in ("homeassistant", "conversation"):
        assert await async_setup_component(hass, domain, {})


async def test_intents_offered_as_tools(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The Assist API offers the intents as tools, and they work."""
    hass.states.async_set("binary_sensor.back_door", "on")
    await setup_alerts(state_alert("Back Door Open", "binary_sensor.back_door"))
    await hass.async_block_till_done()
    # LLMContext's fields changed between versions; give it those it has.
    fields = {
        "platform": "test",
        "context": Context(),
        "user_prompt": None,
        "language": "en",
        "assistant": "conversation",
        "device_id": None,
    }
    names = {field.name for field in dataclasses.fields(llm.LLMContext)}
    context = llm.LLMContext(**{k: v for k, v in fields.items() if k in names})
    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, context)
    tools = {tool.name for tool in api.tools}
    for intent_type in (
        "AlertReduxAcknowledge",
        "AlertReduxUnacknowledge",
        "AlertReduxSnooze",
        "AlertReduxListFiring",
    ):
        assert any(intent_type in name for name in tools), tools
    snooze = next(tool.name for tool in api.tools if "AlertReduxSnooze" in tool.name)
    result = await api.async_call_tool(
        llm.ToolInput(tool_name=snooze, tool_args={"name": "back door open"})
    )
    assert result["speech"]["plain"]["speech"] == "Snoozed Back Door Open for 1 hour."
