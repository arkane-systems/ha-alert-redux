"""Tests for persisting alert state across restarts (spec §15.1)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_CREATED,
    EVENT_DELETED,
    EVENT_FIRED,
    STORAGE_KEY,
)

from .conftest import SetupAlerts, alert_subentry

DOOR = "alert_redux.back_door_open"


async def test_state_survives_reload(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """A fired and acknowledged alert comes back as it was, silently."""
    entry = await setup_alerts(alert_subentry("Back Door Open", subentry_id="door"))
    await hass.services.async_call(
        DOMAIN, "fire", {"entity_id": DOOR, "data": {"x": 1}}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": DOOR}, blocking=True)
    before = hass.states.get(DOOR)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # Unloading flushed the store.
    stored = hass_storage[STORAGE_KEY]["data"]["alerts"]["door"]
    assert stored["runtime"]["acked"] is True

    events = [
        async_capture_events(hass, event)
        for event in (EVENT_CREATED, EVENT_FIRED, EVENT_ACKED)
    ]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = hass.states.get(DOOR)
    assert after.state == "ack"
    for attribute in ("firing_since", "fire_count", "fire_data", "last_acked"):
        assert after.attributes[attribute] == before.attributes[attribute]
    assert all(not captured for captured in events)


async def test_cold_start_from_storage(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """Stored state is restored at startup; only new alerts are announced, and
    stored alerts with no subentry are announced as deleted."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            "alerts": {
                "door": {
                    "entity_id": DOOR,
                    "name": "Back Door Open",
                    "kind": "manual",
                    "priority": "warning",
                    "runtime": {
                        "firing": True,
                        "acked": False,
                        "firing_since": "2026-01-01T12:00:00+00:00",
                        "last_fired": "2026-01-01T12:00:00+00:00",
                        "fire_count": 3,
                    },
                },
                "gone": {
                    "entity_id": "alert_redux.gone",
                    "name": "Gone",
                    "kind": "manual",
                    "priority": "notice",
                    "runtime": {"firing": False},
                },
            }
        },
    }
    created = async_capture_events(hass, EVENT_CREATED)
    deleted = async_capture_events(hass, EVENT_DELETED)

    await setup_alerts(
        alert_subentry("Back Door Open", subentry_id="door"),
        alert_subentry("Leak", subentry_id="leak"),
    )

    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["fire_count"] == 3
    assert state.attributes["firing_since"].isoformat() == "2026-01-01T12:00:00+00:00"
    assert [event.data["entity_id"] for event in created] == ["alert_redux.leak"]
    assert [event.data["entity_id"] for event in deleted] == ["alert_redux.gone"]
    assert deleted[0].data["old_state"] == "idle"
