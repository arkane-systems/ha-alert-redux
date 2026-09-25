"""Tests for the alert entity and its actions."""

from __future__ import annotations

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_UNACKED,
)

from .conftest import SetupAlerts, alert_subentry

DOOR = "alert_redux.back_door_open"


async def _call(
    hass: HomeAssistant, service: str, entity_id: str | list[str], **kwargs
) -> None:
    await hass.services.async_call(
        DOMAIN,
        service,
        {"entity_id": entity_id, **kwargs.pop("data", {})},
        blocking=True,
        **kwargs,
    )


async def test_entity_created(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """An alert subentry becomes an idle alert_redux entity with its config."""
    entry = await setup_alerts(alert_subentry("Back Door Open", priority="critical"))

    state = hass.states.get(DOOR)
    assert state is not None
    assert state.state == "idle"
    assert state.attributes["kind"] == "manual"
    assert state.attributes["priority"] == "critical"
    assert state.attributes["acknowledgeable"] is True
    assert state.attributes["user_dismissable"] is False
    assert state.attributes["fire_count"] == 0
    assert state.attributes["icon"] == "mdi:alert-octagon"

    entity = er.async_get(hass).async_get(DOOR)
    assert entity is not None
    assert entity.translation_key == "alert"
    assert entity.config_entry_id == entry.entry_id
    assert entity.config_subentry_id in entry.subentries


async def test_custom_icon(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """A configured icon replaces the priority's default."""
    await setup_alerts(alert_subentry("Back Door Open", icon="mdi:door-open"))
    assert hass.states.get(DOOR).attributes["icon"] == "mdi:door-open"


async def test_lifecycle(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user
) -> None:
    """Fire, ack, unack, refire, and dismiss, with events carrying the user."""
    await setup_alerts(alert_subentry("Back Door Open"))
    fired = async_capture_events(hass, EVENT_FIRED)
    acked = async_capture_events(hass, EVENT_ACKED)
    unacked = async_capture_events(hass, EVENT_UNACKED)
    ended = async_capture_events(hass, EVENT_ENDED)
    context = Context(user_id=hass_admin_user.id)

    await _call(hass, "fire", DOOR, data={"data": {"room": "hall"}}, context=context)
    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["fire_count"] == 1
    assert state.attributes["fire_data"] == {"room": "hall"}
    assert state.attributes["firing_since"] is not None
    assert len(fired) == 1
    assert fired[0].data == {
        "entity_id": DOOR,
        "name": "Back Door Open",
        "priority": "warning",
        "kind": "manual",
        "old_state": "idle",
        "new_state": "active",
        "user_id": hass_admin_user.id,
        "fire_count": 1,
        "fire_data": {"room": "hall"},
    }
    assert fired[0].context.id == context.id

    await _call(hass, "ack", DOOR, context=context)
    state = hass.states.get(DOOR)
    assert state.state == "ack"
    assert state.attributes["last_acked_by"] == hass_admin_user.id
    assert state.attributes["last_acked"] is not None
    assert acked[0].data["old_state"] == "active"
    assert acked[0].data["new_state"] == "ack"
    assert acked[0].data["user_id"] == hass_admin_user.id

    # Firing again keeps the acknowledgement and counts the fire.
    await _call(hass, "fire", DOOR)
    state = hass.states.get(DOOR)
    assert state.state == "ack"
    assert state.attributes["fire_count"] == 2
    assert fired[1].data["old_state"] == fired[1].data["new_state"] == "ack"
    assert fired[1].data["fire_count"] == 2
    assert fired[1].data["user_id"] is None

    await _call(hass, "unack", DOOR, context=context)
    state = hass.states.get(DOOR)
    assert state.state == "active"
    assert state.attributes["last_unacked_by"] == hass_admin_user.id
    assert unacked[0].data["user_id"] == hass_admin_user.id

    await _call(hass, "ack", DOOR)
    await _call(hass, "dismiss", DOOR, context=context)
    state = hass.states.get(DOOR)
    assert state.state == "idle"
    assert state.attributes["fire_count"] == 0
    assert state.attributes["firing_since"] is None
    assert state.attributes["fire_data"] is None
    assert state.attributes["last_ended"] is not None
    assert ended[0].data["old_state"] == "ack"
    assert ended[0].data["new_state"] == "idle"
    assert ended[0].data["fire_count"] == 2
    assert ended[0].data["duration_seconds"] >= 0
    assert ended[0].data["reason"] == "dismissed"
    assert ended[0].data["user_id"] == hass_admin_user.id
    # Ending clears the acknowledgement without an _unacked event.
    assert len(unacked) == 1


async def test_inapplicable_actions_are_noops(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Actions that don't apply do nothing, even across several targets."""
    await setup_alerts(alert_subentry("Back Door Open"), alert_subentry("Leak"))
    events = [
        async_capture_events(hass, event)
        for event in (EVENT_FIRED, EVENT_ACKED, EVENT_UNACKED, EVENT_ENDED)
    ]
    leak = "alert_redux.leak"

    await _call(hass, "ack", [DOOR, leak])
    await _call(hass, "unack", [DOOR, leak])
    await _call(hass, "dismiss", [DOOR, leak])
    assert all(not captured for captured in events)

    await _call(hass, "fire", leak)
    await _call(hass, "unack", [DOOR, leak])
    await _call(hass, "ack", [DOOR, leak])
    assert hass.states.get(DOOR).state == "idle"
    assert hass.states.get(leak).state == "ack"


async def test_unacknowledgeable(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Acknowledging an unacknowledgeable alert is refused."""
    await setup_alerts(alert_subentry("Back Door Open", acknowledgeable=False))
    await _call(hass, "fire", DOOR)

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "ack", DOOR)
    assert err.value.translation_key == "not_acknowledgeable"
    assert hass.states.get(DOOR).state == "active"
