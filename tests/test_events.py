"""Tests for the event set as a whole (spec §11.3)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Event, HomeAssistant, callback
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alert_redux.const import DOMAIN, EVENT_TYPES

from .conftest import SetupAlerts, alert_subentry, state_alert

COMMON = {"entity_id", "name", "priority", "kind", "old_state", "new_state", "user_id"}
LEAK = "alert_redux.leak"
DOOR = "alert_redux.back_door_open"
SENSOR = "binary_sensor.back_door"


async def test_every_event_carries_the_common_data(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Drive every kind of change, and check each event's data."""
    seen: list[Event] = []

    @callback
    def _record(event: Event) -> None:
        seen.append(event)

    for event_type in EVENT_TYPES:
        hass.bus.async_listen(event_type, _record)

    async def call(service: str, entity_id: str, **data) -> None:
        await hass.services.async_call(
            DOMAIN, service, {"entity_id": entity_id, **data}, blocking=True
        )
        await hass.async_block_till_done()

    hass.states.async_set(SENSOR, "off")
    entry = await setup_alerts(
        alert_subentry("Leak", "leak"),
        state_alert("Back Door Open", SENSOR),
        state_alert(
            "Back Door Left Open",
            SENSOR,
            supersedes=[{"alert": DOOR}],
        ),
    )
    await call("fire", LEAK)
    await call("ack", LEAK)
    await call("unack", LEAK)
    await call("snooze", LEAK, duration={"minutes": 1})
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await call("disable", LEAK)
    await call("enable", LEAK)
    hass.states.async_set(SENSOR, "on")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    hass.states.async_set(SENSOR, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(SENSOR, "off")
    await hass.async_block_till_done()
    hass.config_entries.async_remove_subentry(entry, "leak")
    await hass.async_block_till_done()

    assert {event.event_type for event in seen} == set(EVENT_TYPES)
    for event in seen:
        assert COMMON <= event.data.keys(), event.event_type
