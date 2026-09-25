"""Tests for on/off alerts (spec §4.1)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import SetupAlerts, on_off_alert

MOTION = "binary_sensor.garage_motion"
DOOR = "binary_sensor.garage_door"
ALERT = "alert_redux.garage_intruder"
ON = "{{ is_state('binary_sensor.garage_motion', 'on') }}"
OFF = "{{ is_state('binary_sensor.garage_door', 'off') }}"


async def _set(hass: HomeAssistant, entity_id: str, state: str) -> None:
    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant) -> str:
    return hass.states.get(ALERT).state


async def _restart(hass: HomeAssistant, entry) -> None:
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_template_sides(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """On when the on side becomes true; off when the off side does."""
    hass.states.async_set(MOTION, "off")
    hass.states.async_set(DOOR, "on")
    await setup_alerts(
        on_off_alert("Garage Intruder", on_template=ON, off_template=OFF)
    )
    state = hass.states.get(ALERT)
    assert state.state == "idle"
    assert state.attributes["kind"] == "on_off"
    assert state.attributes["on_template"] == ON
    assert state.attributes["off_triggers"] == []

    await _set(hass, MOTION, "on")
    assert _state(hass) == "active"
    # Motion stopping doesn't end it: only the off side does.
    await _set(hass, MOTION, "off")
    assert _state(hass) == "active"
    await _set(hass, DOOR, "off")
    assert _state(hass) == "idle"


async def test_first_evaluation_fires(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An on side already true when a new alert starts is an edge (decision 1)."""
    hass.states.async_set(MOTION, "on")
    hass.states.async_set(DOOR, "on")
    await setup_alerts(
        on_off_alert("Garage Intruder", on_template=ON, off_template=OFF)
    )
    assert _state(hass) == "active"


async def test_no_refire_while_still_on(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(MOTION, "on")
    hass.states.async_set(DOOR, "on")
    # The motion sensor's state as is, so that unavailable is no data.
    entry = await setup_alerts(
        on_off_alert(
            "Garage Intruder",
            on_template="{{ states('binary_sensor.garage_motion') }}",
            off_template=OFF,
        )
    )
    await _set(hass, DOOR, "off")
    assert _state(hass) == "idle"
    await _set(hass, DOOR, "on")
    assert _state(hass) == "idle"  # Motion never went off: no new edge.

    # Nor after a restart, or a dropout.
    await _restart(hass, entry)
    assert _state(hass) == "idle"
    await _set(hass, MOTION, "unavailable")
    assert _state(hass) == "no_data"
    await _set(hass, MOTION, "on")
    assert _state(hass) == "idle"

    await _set(hass, MOTION, "off")
    await _set(hass, MOTION, "on")
    assert _state(hass) == "active"


async def test_no_data_counts_only_the_live_side(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(MOTION, "off")
    hass.states.async_set(DOOR, "on")
    await setup_alerts(
        on_off_alert("Garage Intruder", on_template=ON, off_template=OFF)
    )
    await _set(hass, DOOR, "unavailable")
    assert _state(hass) == "idle"  # The off side doesn't matter while idle.
    await _set(hass, DOOR, "on")
    await _set(hass, MOTION, "on")
    await _set(hass, MOTION, "unavailable")
    assert _state(hass) == "active"
    assert hass.states.get(ALERT).attributes["no_data_since"] is None


async def test_trigger_sides(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    await setup_alerts(
        on_off_alert(
            "Garage Intruder",
            on_triggers=[{"trigger": "event", "event_type": "garage_alarm"}],
            off_triggers=[{"trigger": "event", "event_type": "garage_all_clear"}],
        )
    )
    assert _state(hass) == "idle"
    hass.bus.async_fire("garage_all_clear")
    await hass.async_block_till_done()
    assert _state(hass) == "idle"
    hass.bus.async_fire("garage_alarm")
    await hass.async_block_till_done()
    assert _state(hass) == "active"
    hass.bus.async_fire("garage_all_clear")
    await hass.async_block_till_done()
    assert _state(hass) == "idle"


async def test_trigger_with_template(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A trigger counts only while its side's template is true."""
    hass.states.async_set(DOOR, "on")
    await setup_alerts(
        on_off_alert(
            "Garage Intruder",
            on_triggers=[{"trigger": "event", "event_type": "garage_alarm"}],
            on_template="{{ is_state('binary_sensor.garage_door', 'off') }}",
            off_template="{{ is_state('binary_sensor.garage_door', 'on') }}",
        )
    )
    hass.bus.async_fire("garage_alarm")
    await hass.async_block_till_done()
    assert _state(hass) == "idle"
    await _set(hass, DOOR, "off")
    hass.bus.async_fire("garage_alarm")
    await hass.async_block_till_done()
    assert _state(hass) == "active"
    await _set(hass, DOOR, "on")
    assert _state(hass) == "idle"


async def test_extra_condition_and_delays(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set(MOTION, "off")
    hass.states.async_set(DOOR, "on")
    hass.states.async_set("input_boolean.away", "on")
    await setup_alerts(
        on_off_alert(
            "Garage Intruder",
            on_template=ON,
            off_template=OFF,
            condition="{{ is_state('input_boolean.away', 'on') }}",
            delay_on={"minutes": 1},
        )
    )
    await _set(hass, MOTION, "on")
    assert _state(hass) == "idle"
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass) == "active"
    # The extra condition turning false ends it.
    await _set(hass, "input_boolean.away", "off")
    assert _state(hass) == "idle"
