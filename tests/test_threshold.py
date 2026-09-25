"""Tests for threshold alerts (spec §4.1)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import SetupAlerts, threshold_alert

TEMP = "sensor.server_room"
LIMIT = "input_number.server_room_max"
ALERT = "alert_redux.server_room_hot"


async def _set(hass: HomeAssistant, entity_id: str, state: str, **attrs) -> None:
    hass.states.async_set(entity_id, state, attrs)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str = ALERT) -> str:
    return hass.states.get(entity_id).state


async def test_threshold_with_hysteresis(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Above the maximum fires; it ends once back inside by the hysteresis."""
    hass.states.async_set(TEMP, "25")
    await setup_alerts(
        threshold_alert("Server Room Hot", entity_id=TEMP, maximum="30", hysteresis=2)
    )
    state = hass.states.get(ALERT)
    assert state.state == "idle"
    assert state.attributes["kind"] == "threshold"
    assert state.attributes["source_entity"] == TEMP
    assert state.attributes["subject_entity"] == TEMP
    assert state.attributes["maximum"] == "30"
    assert state.attributes["minimum"] is None
    assert state.attributes["hysteresis"] == 2
    assert state.attributes["value"] == 25

    await _set(hass, TEMP, "30")
    assert _state(hass) == "idle"
    await _set(hass, TEMP, "31")
    assert _state(hass) == "active"
    await _set(hass, TEMP, "29")
    assert _state(hass) == "active"
    assert hass.states.get(ALERT).attributes["value"] == 29
    await _set(hass, TEMP, "28")
    assert _state(hass) == "idle"


async def test_minimum_and_limit_from_entity(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(TEMP, "20")
    hass.states.async_set(LIMIT, "30")
    await setup_alerts(
        threshold_alert(
            "Server Room Hot",
            entity_id=TEMP,
            minimum="5",
            maximum="{{ states('input_number.server_room_max') }}",
        )
    )
    await _set(hass, LIMIT, "15")
    assert _state(hass) == "active"
    await _set(hass, LIMIT, "25")
    assert _state(hass) == "idle"
    await _set(hass, TEMP, "4")
    assert _state(hass) == "active"


async def test_no_data(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """A value or a limit that isn't a number means no data."""
    hass.states.async_set(TEMP, "20")
    hass.states.async_set(LIMIT, "30")
    await setup_alerts(
        threshold_alert(
            "Server Room Hot",
            entity_id=TEMP,
            maximum="{{ states('input_number.server_room_max') }}",
        )
    )
    await _set(hass, TEMP, "unavailable")
    assert _state(hass) == "no_data"
    assert hass.states.get(ALERT).attributes["missing_inputs"] == [TEMP]
    await _set(hass, TEMP, "20")
    assert _state(hass) == "idle"
    await _set(hass, LIMIT, "unknown")
    assert _state(hass) == "no_data"
    assert hass.states.get(ALERT).attributes["missing_inputs"] == [LIMIT]


async def test_attribute_and_template_values(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set("climate.lounge", "heat", {"current_temperature": 17})
    hass.states.async_set(TEMP, "20")
    await setup_alerts(
        threshold_alert(
            "Lounge Cold",
            entity_id="climate.lounge",
            attribute="current_temperature",
            minimum="18",
        ),
        threshold_alert(
            "Server Room Hot",
            value_template="{{ states('sensor.server_room') | float(0) * 2 }}",
            maximum="30",
        ),
    )
    assert _state(hass, "alert_redux.lounge_cold") == "active"
    assert hass.states.get(ALERT).attributes["subject_entity"] is None
    assert _state(hass) == "active"
    await _set(hass, "climate.lounge", "heat", current_temperature=19)
    assert _state(hass, "alert_redux.lounge_cold") == "idle"


async def test_delay_on(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set(TEMP, "20")
    await setup_alerts(
        threshold_alert(
            "Server Room Hot", entity_id=TEMP, maximum="30", delay_on={"minutes": 5}
        )
    )
    await _set(hass, TEMP, "35")
    assert _state(hass) == "idle"
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass) == "active"
