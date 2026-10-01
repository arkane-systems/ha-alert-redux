"""Tests for the voice commands as LLM tools (spec §14.1)."""

from __future__ import annotations

import pytest
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from custom_components.alert_redux.llm import async_get_tools

from .conftest import SetupAlerts, state_alert

BACK = "alert_redux.back_door_open"
TOOLS = {
    "alert_redux__AlertReduxAcknowledge",
    "alert_redux__AlertReduxUnacknowledge",
    "alert_redux__AlertReduxSnooze",
    "alert_redux__AlertReduxListFiring",
}


@pytest.fixture(autouse=True)
async def assist(hass: HomeAssistant) -> None:
    """Set up the core integration (for exposure), conversation, and llm."""
    for domain in ("homeassistant", "conversation", "llm"):
        assert await async_setup_component(hass, domain, {})


def _context() -> llm.LLMContext:
    return llm.LLMContext(
        platform="test",
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def _setup(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    hass.states.async_set("binary_sensor.back_door", "on")
    await setup_alerts(state_alert("Back Door Open", "binary_sensor.back_door"))
    await hass.async_block_till_done()


async def test_tools_offered(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The Assist API offers the four tools, with the prompt."""
    await _setup(hass, setup_alerts)
    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, _context())
    assert TOOLS <= {tool.name for tool in api.tools}
    assert "alert_redux__AlertReduxListFiring" in api.api_prompt


async def test_tools_need_an_exposed_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Nothing is offered when no alert is exposed, or for another API."""
    await _setup(hass, setup_alerts)
    assert async_get_tools(hass, _context(), "other_api") is None
    async_expose_entity(hass, "conversation", BACK, False)
    assert async_get_tools(hass, _context(), llm.LLM_API_ASSIST) is None


async def test_tool_call(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Calling a tool acts on the alert, and says so."""
    await _setup(hass, setup_alerts)
    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, _context())
    result = await api.async_call_tool(
        llm.ToolInput(
            tool_name="alert_redux__AlertReduxSnooze",
            tool_args={"name": "back door open", "minutes": 20},
        )
    )
    assert result["speech"]["plain"]["speech"] == (
        "Snoozed Back Door Open for 20 minutes."
    )
    assert hass.states.get(BACK).state == "ack"
