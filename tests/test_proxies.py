"""Tests for the voice proxies for Alexa and Google Home (spec §14.2)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
    async_should_expose,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    label_registry as lr,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import SetupAlerts, generator_subentry, state_alert

ALERT = "alert_redux.back_door_open"
SWITCH = "switch.back_door_open"
BUTTON = "button.snooze_back_door_open"
PROXIES = {"proxy_switch": True, "proxy_snooze_button": True}


@pytest.fixture(autouse=True)
async def core(hass: HomeAssistant) -> None:
    """Set up the core integration, which exposure belongs to."""
    assert await async_setup_component(hass, "homeassistant", {})


async def _setup(hass: HomeAssistant, setup_alerts: SetupAlerts, **data):
    hass.states.async_set("binary_sensor.back_door", "off")
    entry = await setup_alerts(
        state_alert(
            "Back Door Open",
            "binary_sensor.back_door",
            subentry_id="door",
            **{**PROXIES, **data},
        )
    )
    await hass.async_block_till_done()
    return entry


async def _door(hass: HomeAssistant, state: str) -> None:
    hass.states.async_set("binary_sensor.back_door", state)
    await hass.async_block_till_done()


async def _call(hass: HomeAssistant, domain: str, service: str, entity_id: str):
    await hass.services.async_call(
        domain, service, {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_proxies_made(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """An alert's proxies are made with its name, and no device."""
    await _setup(hass, setup_alerts)
    switch = hass.states.get(SWITCH)
    button = hass.states.get(BUTTON)
    assert switch.name == "Back Door Open"
    assert switch.state == "off"
    assert switch.attributes["alert"] == ALERT
    assert button.name == "Snooze Back Door Open"
    assert button.attributes["snooze_duration"] == 3600
    registry = er.async_get(hass)
    assert registry.async_get(SWITCH).device_id is None


async def test_no_proxies_by_default(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Proxies are opt-in."""
    hass.states.async_set("binary_sensor.back_door", "off")
    await setup_alerts(state_alert("Back Door Open", "binary_sensor.back_door"))
    assert hass.states.get(SWITCH) is None
    assert hass.states.get(BUTTON) is None


async def test_switch(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The switch is on while the alert is active; off acknowledges, on unacks."""
    await _setup(hass, setup_alerts)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "switch", "turn_on", SWITCH)
    assert err.value.translation_key == "not_firing"
    # Turning it off while the alert isn't firing does nothing.
    await _call(hass, "switch", "turn_off", SWITCH)
    assert hass.states.get(ALERT).state == "idle"

    await _door(hass, "on")
    assert hass.states.get(SWITCH).state == "on"
    await _call(hass, "switch", "turn_off", SWITCH)
    assert hass.states.get(ALERT).state == "ack"
    assert hass.states.get(SWITCH).state == "off"
    await _call(hass, "switch", "turn_on", SWITCH)
    assert hass.states.get(ALERT).state == "active"
    assert hass.states.get(SWITCH).state == "on"

    await _door(hass, "off")
    assert hass.states.get(SWITCH).state == "off"


async def test_switch_unacknowledgeable(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An unacknowledgeable alert's switch shows it, but won't turn off (§6.1)."""
    await _setup(hass, setup_alerts, acknowledgeable=False)
    await _door(hass, "on")
    assert hass.states.get(SWITCH).state == "on"
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "switch", "turn_off", SWITCH)
    assert err.value.translation_key == "not_acknowledgeable"
    with pytest.raises(ServiceValidationError):
        await _call(hass, "button", "press", BUTTON)


async def test_snooze_button(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The button snoozes for the alert's snooze button duration."""
    await _setup(hass, setup_alerts, button_snooze_duration={"minutes": 20})
    assert hass.states.get(BUTTON).attributes["snooze_duration"] == 1200
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "button", "press", BUTTON)
    assert err.value.translation_key == "not_firing"

    await _door(hass, "on")
    now = dt_util.utcnow()
    await _call(hass, "button", "press", BUTTON)
    state = hass.states.get(ALERT)
    assert state.state == "ack"
    until = state.attributes["snoozed_until"]
    assert abs(until - now - timedelta(minutes=20)) < timedelta(seconds=5)
    assert hass.states.get(SWITCH).state == "off"
    # Turning the switch on unsnoozes it.
    await _call(hass, "switch", "turn_on", SWITCH)
    assert hass.states.get(ALERT).state == "active"
    assert hass.states.get(ALERT).attributes.get("snoozed_until") is None


async def test_exposure(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Proxies are exposed to Alexa and Google, and hidden from Assist, once."""
    entry = await _setup(hass, setup_alerts)
    for proxy in (SWITCH, BUTTON):
        assert async_should_expose(hass, "cloud.alexa", proxy)
        assert async_should_expose(hass, "cloud.google_assistant", proxy)
        assert not async_should_expose(hass, "conversation", proxy)
    # The alert itself goes to Assist only.
    assert async_should_expose(hass, "conversation", ALERT)
    assert not async_should_expose(hass, "cloud.alexa", ALERT)

    async_expose_entity(hass, "cloud.alexa", SWITCH, False)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH) is not None
    assert not async_should_expose(hass, "cloud.alexa", SWITCH)


async def test_option_off_and_on(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Turning an option off removes that proxy; on again makes a new one."""
    entry = await _setup(hass, setup_alerts)
    subentry = entry.subentries["door"]
    data = {k: v for k, v in subentry.data.items() if k != "proxy_switch"}
    hass.config_entries.async_update_subentry(entry, subentry, data=data)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert hass.states.get(SWITCH) is None
    assert registry.async_get(SWITCH) is None
    assert hass.states.get(BUTTON) is not None

    hass.config_entries.async_update_subentry(
        entry, subentry, data={**data, "proxy_switch": True}
    )
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH) is not None
    assert async_should_expose(hass, "cloud.alexa", SWITCH)


async def test_deleted_alert(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Deleting an alert removes its proxies; unloading doesn't."""
    entry = await _setup(hass, setup_alerts)
    registry = er.async_get(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(SWITCH) is not None
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"

    assert hass.config_entries.async_remove_subentry(entry, "door")
    await hass.async_block_till_done()
    assert registry.async_get(SWITCH) is None
    assert registry.async_get(BUTTON) is None


async def test_follows_name_area_and_labels(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Proxies follow the alert's name, area, and labels, but not the alerts label."""
    await _setup(hass, setup_alerts)
    registry = er.async_get(hass)
    alerts_label = registry.async_get(ALERT).labels
    assert alerts_label
    assert not registry.async_get(SWITCH).labels

    area = ar.async_get(hass).async_create("Kitchen")
    label = lr.async_get(hass).async_create("Doors")
    registry.async_update_entity(
        ALERT,
        name="Kitchen Door",
        area_id=area.id,
        labels={*alerts_label, label.label_id},
    )
    await hass.async_block_till_done()
    for proxy in (SWITCH, BUTTON):
        entry = registry.async_get(proxy)
        assert entry.area_id == area.id
        assert entry.labels == {label.label_id}
    assert hass.states.get(SWITCH).name == "Kitchen Door"
    assert hass.states.get(BUTTON).name == "Snooze Kitchen Door"


async def test_generated_alerts(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """A generator's option gives each of its alerts proxies."""
    hass.states.async_set("lock.front_door", "unlocked")
    entry = await setup_alerts(
        generator_subentry(
            "Unlocked",
            "state",
            "gen",
            targets={"domains": ["lock"]},
            target_state="unlocked",
            proxy_switch=True,
        )
    )
    await hass.async_block_till_done()
    switch = hass.states.get("switch.front_door_unlocked")
    assert switch is not None
    assert switch.state == "on"
    assert hass.states.get("button.snooze_front_door_unlocked") is None

    assert hass.config_entries.async_remove_subentry(entry, "gen")
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get("switch.front_door_unlocked") is None
