"""Tests for voice commands through Assist (spec §14.1)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.auth.models import User
from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
    async_should_expose,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.alert_redux.voice import INTENT_SNOOZE, INTENTS

from .conftest import SetupAlerts, state_alert

BACK = "alert_redux.back_door_open"
GARAGE = "alert_redux.garage_door_open"


@pytest.fixture(autouse=True)
async def assist(hass: HomeAssistant) -> None:
    """Set up Assist: the core integration (for exposure), and conversation."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})


async def _alerts(hass: HomeAssistant, setup_alerts: SetupAlerts, **data) -> None:
    hass.states.async_set("binary_sensor.back_door", "on")
    hass.states.async_set("binary_sensor.garage_door", "off")
    await setup_alerts(
        state_alert("Back Door Open", "binary_sensor.back_door", **data),
        state_alert("Garage Door Open", "binary_sensor.garage_door"),
    )
    await hass.async_block_till_done()


async def _say(hass: HomeAssistant, text: str, user: User | None = None) -> str:
    result = await conversation.async_converse(
        hass, text, None, Context(user_id=user.id if user else None), language="en"
    )
    await hass.async_block_till_done()
    return result.response.speech["plain"]["speech"]


async def test_acknowledge_by_name(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: User
) -> None:
    """An alert is acknowledged by name, recording who did it."""
    await _alerts(hass, setup_alerts)
    reply = await _say(hass, "Acknowledge the back door open alert", hass_admin_user)
    assert reply == "Acknowledged Back Door Open."
    state = hass.states.get(BACK)
    assert state.state == "ack"
    assert state.attributes["last_acked_by"] == hass_admin_user.id
    assert await _say(hass, "ack back door open") == (
        "Back Door Open is already acknowledged."
    )


async def test_acknowledge_refusals(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Names that don't fit, or alerts in the wrong state, are answered."""
    await _alerts(hass, setup_alerts)
    assert await _say(hass, "acknowledge garage door open") == (
        "Garage Door Open isn't firing."
    )
    assert await _say(hass, "acknowledge the kitchen") == (
        "I don't know an alert called kitchen."
    )
    assert await _say(hass, "acknowledge door open") == (
        "Which one: Back Door Open or Garage Door Open?"
    )


async def test_unacknowledgeable(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An unacknowledgeable alert can't be acknowledged or snoozed (§6.1)."""
    await _alerts(hass, setup_alerts, acknowledgeable=False)
    assert await _say(hass, "acknowledge back door open") == (
        "Back Door Open can't be acknowledged or snoozed."
    )
    assert await _say(hass, "snooze back door open") == (
        "Back Door Open can't be acknowledged or snoozed."
    )
    assert hass.states.get(BACK).state == "active"


async def test_no_name(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """With no name, the one alert that fits is acted on; with several, none is."""
    await _alerts(hass, setup_alerts)
    assert await _say(hass, "acknowledge the alert") == "Acknowledged Back Door Open."
    assert await _say(hass, "acknowledge the alert") == "No alert needs acknowledging."

    hass.states.async_set("binary_sensor.garage_door", "on")
    await hass.async_block_till_done()
    assert await _say(hass, "snooze the alert") == (
        "Which one: Back Door Open or Garage Door Open?"
    )
    assert hass.states.get(GARAGE).state == "active"


async def test_unacknowledge(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The acknowledgement is removed, by either sentence."""
    await _alerts(hass, setup_alerts)
    assert await _say(hass, "unacknowledge back door open") == (
        "Back Door Open isn't acknowledged."
    )
    await _say(hass, "acknowledge back door open")
    assert await _say(
        hass, "remove the acknowledgement from the back door open alert"
    ) == ("Removed the acknowledgement from Back Door Open.")
    assert hass.states.get(BACK).state == "active"


async def test_snooze(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """A spoken duration, or else the alert's snooze button duration."""
    await _alerts(hass, setup_alerts)
    now = dt_util.utcnow()
    assert await _say(hass, "snooze back door open for half an hour") == (
        "Snoozed Back Door Open for 30 minutes."
    )
    until = hass.states.get(BACK).attributes["snoozed_until"]
    assert abs(until - now - timedelta(minutes=30)) < timedelta(seconds=5)

    assert await _say(hass, "snooze the back door open alert") == (
        "Snoozed Back Door Open for 1 hour."
    )
    assert await _say(hass, "snooze back door open for a while") == (
        "How long should I snooze it for?"
    )


async def test_snooze_own_duration(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The default is the alert's own snooze button duration (§9.11)."""
    await _alerts(hass, setup_alerts, button_snooze_duration={"minutes": 10})
    assert await _say(hass, "snooze back door open") == (
        "Snoozed Back Door Open for 10 minutes."
    )


async def test_list_firing(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The query lists the firing alerts."""
    await _alerts(hass, setup_alerts)
    assert await _say(hass, "What alerts are firing?") == (
        "One alert is firing: Back Door Open."
    )
    hass.states.async_set("binary_sensor.garage_door", "on")
    await hass.async_block_till_done()
    await _say(hass, "acknowledge garage door open")
    assert await _say(hass, "are there any alerts") == (
        "2 alerts are firing: Back Door Open; and Garage Door Open, acknowledged."
    )


async def test_unexposed_alert(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Voice can't reach an alert that isn't exposed to Assist."""
    await _alerts(hass, setup_alerts)
    async_expose_entity(hass, "conversation", BACK, False)
    assert await _say(hass, "acknowledge back door open") == (
        "I don't know an alert called back door open."
    )
    assert await _say(hass, "which alerts are active") == "No alerts are firing."


async def test_exposed_once(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Alerts are exposed to Assist once, and never forced back."""
    await _alerts(hass, setup_alerts)
    assert async_should_expose(hass, "conversation", BACK)
    async_expose_entity(hass, "conversation", BACK, False)
    entry = hass.config_entries.async_entries("alert_redux")[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert not async_should_expose(hass, "conversation", BACK)
    assert async_should_expose(hass, "conversation", GARAGE)
    # Not to the other assistants.
    assert not async_should_expose(hass, "cloud.alexa", BACK)


async def test_intent_minutes(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The snooze intent takes minutes, as an LLM agent gives them."""
    await _alerts(hass, setup_alerts)
    response = await intent.async_handle(
        hass,
        "test",
        INTENT_SNOOZE,
        {"name": {"value": "Back Door Open"}, "minutes": {"value": 15}},
        assistant="conversation",
    )
    assert (
        response.speech["plain"]["speech"] == "Snoozed Back Door Open for 15 minutes."
    )


async def test_unload_removes_intents(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Unloading the entry removes the intents and the sentences."""
    await _alerts(hass, setup_alerts)
    entry = hass.config_entries.async_entries("alert_redux")[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    registered = {handler.intent_type for handler in intent.async_get(hass)}
    assert not registered & set(INTENTS)
    reply = await _say(hass, "acknowledge back door open")
    assert reply != "Acknowledged Back Door Open."
