"""Tests for rendering alert messages for the card (spec §9.5, §13.1)."""

from __future__ import annotations

import logging

import pytest
from homeassistant.core import HomeAssistant

from custom_components.alert_redux.const import DOMAIN

from .conftest import SetupAlerts, alert_subentry, state_alert

DOOR = "alert_redux.back_door_open"
SENSOR = "binary_sensor.back_door"
TEMP = "sensor.server_room"


async def _fire(hass: HomeAssistant, data: dict | None = None) -> None:
    await hass.services.async_call(
        DOMAIN,
        "fire",
        {"entity_id": DOOR, **({"data": data} if data else {})},
        blocking=True,
    )
    await hass.async_block_till_done()


def _attrs(hass: HomeAssistant, entity_id: str = DOOR) -> dict:
    return dict(hass.states.get(entity_id).attributes)


async def test_default_message(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """With nothing configured, the on message is the default; none while idle."""
    await setup_alerts(alert_subentry("Back Door Open", user_dismissable=True))
    assert _attrs(hass)["message"] is None
    assert _attrs(hass)["display_message"] is None

    await _fire(hass)
    assert _attrs(hass)["message"] == "Back Door Open is firing."
    assert _attrs(hass)["display_message"] is None

    await hass.services.async_call(
        DOMAIN, "dismiss", {"entity_id": DOOR}, blocking=True
    )
    await hass.async_block_till_done()
    assert _attrs(hass)["message"] is None


async def test_message_tracks_entities(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A message re-renders while firing as the entities it reads change."""
    hass.states.async_set(TEMP, "31")
    await setup_alerts(
        alert_subentry(
            "Back Door Open",
            message="Server room is {{ states('sensor.server_room') }} °C",
        )
    )
    await _fire(hass)
    assert _attrs(hass)["message"] == "Server room is 31 °C"

    hass.states.async_set(TEMP, "33")
    await hass.async_block_till_done()
    assert _attrs(hass)["message"] == "Server room is 33 °C"


async def test_message_context(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Messages can use the alert's context variables, including fire data."""
    hass.states.async_set(SENSOR, "off", {"friendly_name": "Back door"})
    await setup_alerts(
        alert_subentry(
            "Back Door Open",
            subject_entity=SENSOR,
            message=(
                "{{ subject_entity_name }}|{{ name }}|{{ priority }}|"
                "{{ fire_count }}|{{ fire_data.who }}|{{ reason }}"
            ),
        )
    )
    await _fire(hass, {"who": "cat"})
    assert _attrs(hass)["message"] == "Back door|Back Door Open|warning|1|cat|on"

    # Firing again updates the fire count and data.
    await _fire(hass, {"who": "dog"})
    assert _attrs(hass)["message"] == "Back door|Back Door Open|warning|2|dog|on"


async def test_subject_name_falls_back_to_name(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(
        alert_subentry("Back Door Open", message="{{ subject_entity_name }}")
    )
    await _fire(hass)
    assert _attrs(hass)["message"] == "Back Door Open"


async def test_display_message(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """The display message is rendered alongside the on message."""
    await setup_alerts(
        alert_subentry(
            "Back Door Open", message="On", display_message="Shut the {{ 'door' }}"
        )
    )
    await _fire(hass)
    assert _attrs(hass)["message"] == "On"
    assert _attrs(hass)["display_message"] == "Shut the door"


async def test_condition_alert_message(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Condition alerts render too; the state kind's entity is the subject."""
    hass.states.async_set(SENSOR, "off", {"friendly_name": "Back door"})
    await setup_alerts(
        state_alert(
            "Back Door Open", SENSOR, message="{{ subject_entity_name }} is open"
        )
    )
    assert _attrs(hass)["message"] is None
    hass.states.async_set(SENSOR, "on", {"friendly_name": "Back door"})
    await hass.async_block_till_done()
    assert _attrs(hass)["message"] == "Back door is open"


async def test_render_error_falls_back(
    hass: HomeAssistant, setup_alerts: SetupAlerts, caplog: pytest.LogCaptureFixture
) -> None:
    """A message that fails to render falls back to the default."""
    await setup_alerts(
        alert_subentry(
            "Back Door Open",
            message="{{ 1 / 0 }}",
            display_message="{{ 1 / 0 }}",
        )
    )
    with caplog.at_level(logging.WARNING):
        await _fire(hass)
    assert _attrs(hass)["message"] == "Back Door Open is firing."
    assert _attrs(hass)["display_message"] is None
    assert "message template failed to render" in caplog.text


async def test_edit_rerenders(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Editing a firing alert's message re-renders it at once."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open", subentry_id="door", message="Old")
    )
    await _fire(hass)
    subentry = entry.subentries["door"]
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, "message": "New"}
    )
    await hass.async_block_till_done()
    assert _attrs(hass)["message"] == "New"


async def test_message_after_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A restored firing alert renders its message again."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open", message="{{ fire_data.who }}")
    )
    await _fire(hass, {"who": "cat"})
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _attrs(hass)["message"] == "cat"
