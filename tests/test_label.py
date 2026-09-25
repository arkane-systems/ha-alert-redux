"""Tests for the label applied to every alert (spec §11.5)."""

from __future__ import annotations

from types import MappingProxyType

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr

from custom_components.alert_redux.const import (
    ALERTS_LABEL_NAME,
    DOMAIN,
    SUBENTRY_ALERT,
)

from .conftest import SetupAlerts, alert_subentry

LEAK = "alert_redux.leak"
DOOR = "alert_redux.back_door_open"


def _label_id(hass: HomeAssistant) -> str | None:
    label = lr.async_get(hass).async_get_label_by_name(ALERTS_LABEL_NAME)
    return label.label_id if label else None


def _labels(hass: HomeAssistant, entity_id: str) -> set[str]:
    return er.async_get(hass).async_get(entity_id).labels


async def _add_alert(hass: HomeAssistant, entry, title: str) -> None:
    subentry = ConfigSubentry(
        data=MappingProxyType(alert_subentry(title)["data"]),
        subentry_type=SUBENTRY_ALERT,
        title=title,
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    await hass.async_block_till_done()


async def test_label_created_and_applied(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(alert_subentry("Leak", subentry_id="leak"))

    label_id = _label_id(hass)
    assert label_id is not None
    assert label_id in _labels(hass, LEAK)

    await _add_alert(hass, entry, "Back Door Open")
    assert label_id in _labels(hass, DOOR)
    # Names are untouched.
    assert hass.states.get(DOOR).name == "Back Door Open"


async def test_existing_alerts_labelled_on_upgrade(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Alerts registered before the label existed (0.3.0) get it once."""
    er.async_get(hass).async_get_or_create(
        DOMAIN, DOMAIN, "leak", suggested_object_id="leak"
    )

    await setup_alerts(alert_subentry("Leak", subentry_id="leak"))

    assert _label_id(hass) in _labels(hass, LEAK)


async def test_removed_label_not_reapplied(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(alert_subentry("Leak", subentry_id="leak"))
    er.async_get(hass).async_update_entity(LEAK, labels=set())

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _labels(hass, LEAK) == set()


async def test_deleted_label_not_recreated(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(alert_subentry("Leak", subentry_id="leak"))
    lr.async_get(hass).async_delete(_label_id(hass))

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await _add_alert(hass, entry, "Back Door Open")

    assert _label_id(hass) is None
    assert _labels(hass, DOOR) == set()


async def test_existing_label_with_same_name_reused(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    existing = lr.async_get(hass).async_create(ALERTS_LABEL_NAME)

    await setup_alerts(alert_subentry("Leak", subentry_id="leak"))

    assert _labels(hass, LEAK) == {existing.label_id}
    assert len(lr.async_get(hass).async_list_labels()) == 1
