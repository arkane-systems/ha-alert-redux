"""Tests for the alert state condition kind (spec §4.1, §8.4)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alert_redux.const import DOMAIN

from .conftest import SetupAlerts, alert_state_alert, alert_subentry

OPEN = "alert_redux.back_door_open"
UNACKED = "alert_redux.back_door_unacknowledged"


async def _call(hass: HomeAssistant, service: str, entity_id: str = OPEN) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str = UNACKED) -> str:
    return hass.states.get(entity_id).state


async def test_escalates_when_unacknowledged(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Fires once the watched alert has been active for the delay."""
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_state_alert(
            "Back Door Unacknowledged", OPEN, ["active"], delay_on={"minutes": 30}
        ),
    )
    state = hass.states.get(UNACKED)
    assert state.state == "idle"
    assert state.attributes["kind"] == "alert_state"
    assert state.attributes["source_entity"] == OPEN
    assert state.attributes["target_states"] == ["active"]
    assert state.attributes["subject_entity"] == OPEN

    await _call(hass, "fire")
    await _tick(hass, freezer, 29)
    assert _state(hass) == "idle"
    await _tick(hass, freezer, 1)
    assert _state(hass) == "active"

    await _call(hass, "dismiss")
    assert _state(hass) == "idle"


async def test_acknowledging_restarts_the_time(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_state_alert(
            "Back Door Unacknowledged", OPEN, ["active"], delay_on={"minutes": 30}
        ),
    )
    await _call(hass, "fire")
    await _tick(hass, freezer, 20)
    await _call(hass, "ack")
    await _tick(hass, freezer, 5)
    await _call(hass, "unack")
    await _tick(hass, freezer, 29)
    assert _state(hass) == "idle"
    await _tick(hass, freezer, 1)
    assert _state(hass) == "active"


async def test_several_states(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Active and acknowledged together mean firing."""
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_state_alert("Back Door Unacknowledged", OPEN, ["active", "ack"]),
    )
    await _call(hass, "fire")
    await _call(hass, "ack")
    assert _state(hass) == "active"


async def test_missing_alert_means_no_data(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A watched alert that doesn't exist fails towards no_data (spec §12.4)."""
    await setup_alerts(
        alert_state_alert("Back Door Unacknowledged", "alert_redux.gone", ["active"])
    )
    state = hass.states.get(UNACKED)
    assert state.state == "no_data"
    assert state.attributes["missing_inputs"] == ["alert_redux.gone"]
