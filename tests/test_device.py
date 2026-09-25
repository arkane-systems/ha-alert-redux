"""Tests for the virtual device all alert entities belong to (spec §11.5)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.alert_redux.const import (
    ALERTS_DEVICE_ID,
    ALERTS_DEVICE_NAME,
    DOMAIN,
)

from .conftest import SetupAlerts, alert_subentry, state_alert

SENSOR = "binary_sensor.back_door"
DOOR = "alert_redux.back_door_open"
LEAK = "alert_redux.leak"


def _device(hass: HomeAssistant) -> dr.DeviceEntry | None:
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, ALERTS_DEVICE_ID)})


async def test_device_exists_without_alerts(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts()

    device = _device(hass)
    assert device is not None
    assert device.name == ALERTS_DEVICE_NAME
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.area_id is None
    assert device.config_entries_subentries == {entry.entry_id: {None}}


async def test_alerts_belong_to_the_device(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(SENSOR, "off")
    entry = await setup_alerts(
        alert_subentry("Leak", subentry_id="leak"),
        state_alert("Back Door Open", SENSOR, subentry_id="door"),
    )

    device = _device(hass)
    registry = er.async_get(hass)
    for entity_id in (LEAK, DOOR):
        assert registry.async_get(entity_id).device_id == device.id
    assert device.config_entries_subentries == {
        entry.entry_id: {None, "leak", "door"}
    }
    # The device's name isn't added to the alerts' names or entity IDs.
    assert hass.states.get(DOOR).name == "Back Door Open"
    on_device = er.async_entries_for_device(registry, device.id)
    assert {entity.entity_id for entity in on_device} == {LEAK, DOOR}


async def test_device_survives_deleting_every_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(alert_subentry("Leak", subentry_id="leak"))
    device_id = _device(hass).id

    hass.config_entries.async_remove_subentry(entry, "leak")
    await hass.async_block_till_done()

    device = _device(hass)
    assert device is not None
    assert device.id == device_id
    assert device.config_entries_subentries == {entry.entry_id: {None}}
    assert er.async_get(hass).async_get(LEAK) is None


async def test_existing_alerts_join_the_device(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Alerts registered before the device existed (0.3.0) are moved onto it."""
    registry = er.async_get(hass)
    registry.async_get_or_create(DOMAIN, DOMAIN, "leak", suggested_object_id="leak")
    assert registry.async_get(LEAK).device_id is None

    await setup_alerts(alert_subentry("Leak", subentry_id="leak"))

    assert registry.async_get(LEAK).device_id == _device(hass).id
