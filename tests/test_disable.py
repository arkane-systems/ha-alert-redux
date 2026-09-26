"""Tests for disabling and suspending alerts (spec §6.3, §6.4)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)
import voluptuous as vol

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_DISABLED,
    EVENT_ENABLED,
    EVENT_ENDED,
    EVENT_FIRED,
)

from .conftest import (
    SetupAlerts,
    alert_subentry,
    event_alert,
    group_subentry,
    on_off_alert,
    state_alert,
)

DOOR = "alert_redux.back_door_open"
SENSOR = "binary_sensor.back_door"
PHONE = group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}])
DEFAULTS = {"default_groups": ["phones"]}


async def _call(
    hass: HomeAssistant, service: str, entity_id: str = DOOR, **data: Any
) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": entity_id, **data}, blocking=True
    )
    await hass.async_block_till_done()


async def _set(hass: HomeAssistant, entity_id: str, state: str) -> None:
    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_disable_firing_condition_alert(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    freezer: FrozenDateTimeFactory,
    hass_admin_user,
) -> None:
    """Disabling ends the firing with a done message, and ignores the input."""
    calls = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR, delay_on={"minutes": 1}),
        PHONE,
        options=DEFAULTS,
    )
    await _tick(hass, freezer, 1)
    assert hass.states.get(DOOR).state == "active"
    order: list[str] = []
    ended = async_capture_events(hass, EVENT_ENDED)
    disabled = async_capture_events(hass, EVENT_DISABLED)

    @callback
    def _record(event: Event) -> None:
        order.append(event.event_type)

    hass.bus.async_listen(EVENT_ENDED, _record)
    hass.bus.async_listen(EVENT_DISABLED, _record)

    await _tick(hass, freezer, 4)
    await hass.services.async_call(
        DOMAIN,
        "disable",
        {"entity_id": DOOR},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()
    state = hass.states.get(DOOR)
    assert state.state == "disabled"
    assert state.attributes["disabled_until"] is None
    assert state.attributes["last_disabled_by"] == hass_admin_user.id
    assert state.attributes["firing_since"] is None
    assert order == [EVENT_ENDED, EVENT_DISABLED]
    assert ended[0].data["reason"] == "disabled"
    assert ended[0].data["new_state"] == "disabled"
    assert disabled[0].data["old_state"] == "active"
    assert disabled[0].data["user_id"] == hass_admin_user.id
    assert calls[-1].data["message"] == (
        "Back Door Open was disabled; stopped firing after 4 minutes."
    )

    # The input is ignored while disabled.
    fired = async_capture_events(hass, EVENT_FIRED)
    await _set(hass, SENSOR, "off")
    await _set(hass, SENSOR, "on")
    await _tick(hass, freezer, 5)
    assert hass.states.get(DOOR).state == "disabled"
    assert not fired

    # Enabled, it starts from scratch: no data, then delay_on, then a new firing.
    enabled = async_capture_events(hass, EVENT_ENABLED)
    await _call(hass, "enable")
    assert len(enabled) == 1
    assert enabled[0].data["old_state"] == "disabled"
    assert hass.states.get(DOOR).state == "idle"
    assert hass.states.get(DOOR).attributes["delay_on_until"] is not None
    await _tick(hass, freezer, 1)
    assert hass.states.get(DOOR).state == "active"
    assert calls[-1].data["message"] == "Back Door Open is firing."


async def test_enable_waits_for_data(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A re-enabled condition alert has no data until its input reports."""
    await setup_alerts(state_alert("Back Door Open", SENSOR))
    await _call(hass, "disable")
    await _call(hass, "enable")
    assert hass.states.get(DOOR).state == "no_data"
    await _set(hass, SENSOR, "on")
    assert hass.states.get(DOOR).state == "active"


async def test_enable_rearms_on_off(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A re-enabled on/off alert whose on side is already true fires."""
    hass.states.async_set("binary_sensor.motion", "on")
    hass.states.async_set("binary_sensor.door", "on")
    alert = "alert_redux.intruder"
    await setup_alerts(
        on_off_alert(
            "Intruder",
            on_template="{{ is_state('binary_sensor.motion', 'on') }}",
            off_template="{{ is_state('binary_sensor.door', 'off') }}",
        )
    )
    assert hass.states.get(alert).state == "active"
    await _call(hass, "disable", alert)
    await _call(hass, "enable", alert)
    assert hass.states.get(alert).state == "active"


async def test_disabled_event_alert_ignores_its_trigger(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    alert = "alert_redux.doorbell"
    await setup_alerts(event_alert("Doorbell", "doorbell"))
    hass.bus.async_fire("doorbell")
    await hass.async_block_till_done()
    assert hass.states.get(alert).state == "active"

    await _call(hass, "disable", alert)
    assert hass.states.get(alert).attributes["event_expires"] is None
    hass.bus.async_fire("doorbell")
    await hass.async_block_till_done()
    assert hass.states.get(alert).state == "disabled"

    await _call(hass, "enable", alert)
    assert hass.states.get(alert).state == "idle"
    hass.bus.async_fire("doorbell")
    await hass.async_block_till_done()
    assert hass.states.get(alert).state == "active"


async def test_disabled_manual_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Fire, ack, snooze, and dismiss do nothing while disabled."""
    await setup_alerts(
        alert_subentry("Back Door Open"),
        alert_subentry("Fire Alarm", acknowledgeable=False),
    )
    await _call(hass, "disable")
    fired = async_capture_events(hass, EVENT_FIRED)
    await _call(hass, "fire")
    await _call(hass, "ack")
    await _call(hass, "unack")
    await _call(hass, "snooze", duration={"minutes": 5})
    await _call(hass, "dismiss")
    assert hass.states.get(DOOR).state == "disabled"
    assert not fired

    await _call(hass, "enable")
    assert hass.states.get(DOOR).state == "idle"

    # Unacknowledgeable alerts can be disabled.
    await _call(hass, "fire", "alert_redux.fire_alarm")
    await _call(hass, "disable", "alert_redux.fire_alarm")
    assert hass.states.get("alert_redux.fire_alarm").state == "disabled"


async def test_disable_twice_and_suspend(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The latest disable or suspend wins."""
    await setup_alerts(alert_subentry("Back Door Open"))
    disabled = async_capture_events(hass, EVENT_DISABLED)
    await _call(hass, "disable")
    await _call(hass, "disable")
    assert len(disabled) == 1

    await _call(hass, "suspend", duration={"hours": 1})
    assert len(disabled) == 2
    assert disabled[1].data["old_state"] == "disabled"
    until = dt_util.utcnow() + timedelta(hours=1)
    assert disabled[1].data["disabled_until"] == until
    assert hass.states.get(DOOR).attributes["disabled_until"] == until

    await _call(hass, "disable")
    assert hass.states.get(DOOR).attributes["disabled_until"] is None
    await _tick(hass, freezer, 90)
    assert hass.states.get(DOOR).state == "disabled"


async def test_suspend_for_a_duration(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A suspension re-enables the alert on time, as nobody's doing."""
    await setup_alerts(alert_subentry("Back Door Open"))
    enabled = async_capture_events(hass, EVENT_ENABLED)
    await _call(hass, "suspend", duration={"minutes": 30})
    assert hass.states.get(DOOR).state == "disabled"
    await _tick(hass, freezer, 29)
    assert hass.states.get(DOOR).state == "disabled"
    await _tick(hass, freezer, 1)
    state = hass.states.get(DOOR)
    assert state.state == "idle"
    assert state.attributes["disabled_until"] is None
    assert state.attributes["last_enabled_by"] is None
    assert len(enabled) == 1
    assert enabled[0].data["user_id"] is None


async def test_suspend_until(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Until a time; a time without a time zone is local time."""
    await hass.config.async_set_time_zone("America/Chicago")
    await setup_alerts(alert_subentry("Back Door Open"))
    local = dt_util.now() + timedelta(hours=2)
    await _call(
        hass, "suspend", until=local.replace(tzinfo=None).isoformat(timespec="seconds")
    )
    until = dt_util.parse_datetime(
        hass.states.get(DOOR).attributes["disabled_until"].isoformat()
    )
    assert until == local.replace(microsecond=0)
    await _tick(hass, freezer, 121)
    assert hass.states.get(DOOR).state == "idle"


async def test_suspend_errors(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    await setup_alerts(alert_subentry("Back Door Open"))
    with pytest.raises(ServiceValidationError):
        await _call(
            hass, "suspend", until=(dt_util.utcnow() - timedelta(minutes=1)).isoformat()
        )
    with pytest.raises(vol.Invalid):
        await _call(hass, "suspend")
    with pytest.raises(vol.Invalid):
        await _call(
            hass,
            "suspend",
            duration={"hours": 1},
            until=(dt_util.utcnow() + timedelta(hours=2)).isoformat(),
        )
    assert hass.states.get(DOOR).state == "idle"


@pytest.mark.parametrize("native", [True, False], ids=["admin_only", "fallback"])
async def test_admin_only(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_owner_user, native: bool
) -> None:
    """Disable, enable, and suspend need an admin; snooze doesn't.

    Both ways of registering them: admin_only (HA 2026.9 on), and the admin
    action used before that. The owner fixture makes sure the user created here
    isn't the owner.
    """
    with patch(
        "custom_components.alert_redux._entity_services_take_admin_only",
        return_value=native,
    ):
        await _check_admin_only(hass, setup_alerts)


async def _check_admin_only(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    await setup_alerts(alert_subentry("Back Door Open"))
    user = await hass.auth.async_create_user("Someone", group_ids=["system-users"])
    assert not user.is_admin
    context = Context(user_id=user.id)
    for service, data in (
        ("disable", {}),
        ("enable", {}),
        ("suspend", {"duration": {"hours": 1}}),
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                service,
                {"entity_id": DOOR, **data},
                blocking=True,
                context=context,
            )
    await hass.services.async_call(DOMAIN, "fire", {"entity_id": DOOR}, blocking=True)
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"entity_id": DOOR, "duration": {"minutes": 5}},
        blocking=True,
        context=context,
    )
    assert hass.states.get(DOOR).state == "ack"

    # An admin (or an automation, with no user) can.
    await hass.services.async_call(
        DOMAIN, "suspend", {"entity_id": DOOR, "duration": {"hours": 1}}, blocking=True
    )
    assert hass.states.get(DOOR).state == "disabled"
    await hass.services.async_call(DOMAIN, "enable", {"entity_id": DOOR}, blocking=True)
    assert hass.states.get(DOOR).state == "idle"
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "suspend", {"entity_id": DOOR}, blocking=True
        )
