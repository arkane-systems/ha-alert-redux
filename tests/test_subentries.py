"""Tests for applying subentry and option changes in place, without a reload."""

from __future__ import annotations

from collections.abc import Iterator
from types import MappingProxyType
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_CREATED,
    EVENT_DELETED,
    EVENT_ENDED,
    EVENT_FIRED,
    SUBENTRY_ALERT,
)

from .conftest import SetupAlerts, alert_subentry, state_alert

SENSOR = "binary_sensor.back_door"
DOOR = "alert_redux.back_door_open"
LEAK = "alert_redux.leak"


@pytest.fixture(autouse=True)
def no_reload(hass: HomeAssistant) -> Iterator[None]:
    """Fail any test that reloads the entry."""
    with (
        patch.object(
            hass.config_entries,
            "async_schedule_reload",
            side_effect=AssertionError("entry reloaded"),
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            side_effect=AssertionError("entry reloaded"),
        ),
    ):
        yield


def _new_subentry(data: dict) -> ConfigSubentry:
    return ConfigSubentry(
        data=MappingProxyType(data["data"]),
        subentry_type=SUBENTRY_ALERT,
        title=data["title"],
        unique_id=None,
    )


async def test_add_alert_in_place(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(SENSOR, "on")
    entry = await setup_alerts(alert_subentry("Leak", subentry_id="leak"))
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    created = async_capture_events(hass, EVENT_CREATED)
    fired = async_capture_events(hass, EVENT_FIRED)

    subentry = _new_subentry(state_alert("Back Door Open", SENSOR))
    hass.config_entries.async_add_subentry(entry, subentry)
    await hass.async_block_till_done()

    assert hass.states.get(DOOR).state == "active"
    entity = er.async_get(hass).async_get(DOOR)
    assert entity.config_subentry_id == subentry.subentry_id
    assert [event.data["entity_id"] for event in created] == [DOOR]
    assert len(fired) == 1
    # The existing alert was left alone.
    assert not [event for event in changes if event.data["entity_id"] == LEAK]
    assert entry.state is ConfigEntryState.LOADED


async def test_remove_alert_in_place(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(
        alert_subentry("Leak", subentry_id="leak"),
        alert_subentry("Back Door Open", subentry_id="door"),
    )
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    deleted = async_capture_events(hass, EVENT_DELETED)

    hass.config_entries.async_remove_subentry(entry, "door")
    await hass.async_block_till_done()

    assert hass.states.get(DOOR) is None
    assert er.async_get(hass).async_get(DOOR) is None
    assert [event.data["entity_id"] for event in deleted] == [DOOR]
    assert not [event for event in changes if event.data["entity_id"] == LEAK]
    assert "door" not in hass.data[DOMAIN]["store"].alert_ids()


async def test_edit_manual_alert_in_place(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(alert_subentry("Back Door Open", subentry_id="door"))
    await hass.services.async_call(DOMAIN, "fire", {"entity_id": DOOR}, blocking=True)

    subentry = entry.subentries["door"]
    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        title="Back Door Ajar",
        data={**subentry.data, "priority": "critical"},
    )
    await hass.async_block_till_done()

    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["friendly_name"] == "Back Door Ajar"
    assert state.attributes["priority"] == "critical"


async def test_edit_firing_condition_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An edit keeps the firing if the new condition holds, and ends it if not."""
    hass.states.async_set(SENSOR, "on")
    hass.states.async_set("binary_sensor.side_door", "off")
    entry = await setup_alerts(
        state_alert("Back Door Open", SENSOR, subentry_id="door")
    )
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": DOOR}, blocking=True)
    firing_since = hass.states.get(DOOR).attributes["firing_since"]
    fired = async_capture_events(hass, EVENT_FIRED)
    ended = async_capture_events(hass, EVENT_ENDED)
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    subentry = entry.subentries["door"]
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, "priority": "critical"}
    )
    await hass.async_block_till_done()
    state = hass.states.get(DOOR)
    assert state.state == "ack"
    assert state.attributes["firing_since"] == firing_since
    assert not fired
    assert all(event.data["new_state"].state == "ack" for event in changes)

    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        data={**subentry.data, "entity_id": "binary_sensor.side_door"},
    )
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).state == "idle"
    assert hass.states.get(DOOR).attributes["source_entity"] == (
        "binary_sensor.side_door"
    )
    assert [event.data["reason"] for event in ended] == ["resolved"]
    assert not fired


async def test_options_reach_alerts(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(SENSOR, "on")
    entry = await setup_alerts(state_alert("Back Door Open", SENSOR))
    assert hass.states.get(DOOR).attributes["no_data_grace"] == 600

    hass.config_entries.async_update_entry(
        entry, options={"no_data_grace": {"minutes": 1}, "startup_delay": {}}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).attributes["no_data_grace"] == 60
