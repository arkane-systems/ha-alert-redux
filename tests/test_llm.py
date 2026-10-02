"""Tests for the voice commands as LLM tools, from llm.py (spec §14.1).

The llm integration's tools platform arrived in HA 2026.8; before that, HA
offers registered intents by itself (test_llm_legacy.py).
"""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant.components.llm")

# Imported once the skip has had its chance: llm.py needs the llm integration.
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from custom_components.alert_redux.llm import async_get_tools  # noqa: E402

from .conftest import SetupAlerts, state_alert

BACK = "alert_redux.back_door_open"
INTENTS = {
    "AlertReduxAcknowledge",
    "AlertReduxUnacknowledge",
    "AlertReduxSnooze",
    "AlertReduxListFiring",
}


def _ours(api: llm.APIInstance) -> dict[str, str]:
    """Return our tools' names by intent type (HA 2026.8 names them by intent;
    from 2026.9 they're prefixed alert_redux__)."""
    return {
        tool.name.removeprefix("alert_redux__"): tool.name
        for tool in api.tools
        if tool.name.removeprefix("alert_redux__") in INTENTS
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
    assert set(_ours(api)) == INTENTS
    assert "AlertReduxListFiring" in api.api_prompt


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
            tool_name=_ours(api)["AlertReduxSnooze"],
            tool_args={"name": "back door open", "minutes": 20},
        )
    )
    assert result["speech"]["plain"]["speech"] == (
        "Snoozed Back Door Open for 20 minutes."
    )
    assert hass.states.get(BACK).state == "ack"
