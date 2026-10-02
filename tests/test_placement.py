"""Tests for an alert's area and labels, in the entity registry (spec §11.6)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alert_redux.const import SUBENTRY_ALERT, SUBENTRY_GENERATOR

from .conftest import SetupAlerts, alert_subentry, generator_subentry
from .test_config_flow import FORM, GENERATOR_FORM, _start, _start_generator, _suggested

DOOR = "alert_redux.back_door_open"
FRONT_ALERT = "alert_redux.front_door_unlocked"


def _alerts_label(hass: HomeAssistant) -> str:
    label = lr.async_get(hass).async_get_label_by_name("Alert Redux")
    assert label is not None
    return label.label_id


def _entry(hass: HomeAssistant, entity_id: str) -> er.RegistryEntry:
    entry = er.async_get(hass).async_get(entity_id)
    assert entry is not None
    return entry


async def _settle(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()


# A fixed alert.


async def test_new_alert_is_placed_once(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The form's area and labels travel with a new alert and are applied when its
    entity is first added; after that they're the registry's, never forced back."""
    entry = await setup_alerts()
    kitchen = ar.async_get(hass).async_create("Kitchen")
    safety = lr.async_get(hass).async_create("Safety")

    result = await _start(hass, entry, "manual")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            **FORM,
            "placement": {"area_id": kitchen.id, "labels": [safety.label_id]},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = entry.subentries.values()
    assert subentry.data["placement"] == {
        "area_id": kitchen.id,
        "labels": [safety.label_id],
    }
    registry_entry = _entry(hass, DOOR)
    assert registry_entry.area_id == kitchen.id
    assert registry_entry.labels == {safety.label_id, _alerts_label(hass)}

    # Removed by hand, and not put back, even after a restart of the entry.
    er.async_get(hass).async_update_entity(DOOR, area_id=None, labels=set())
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    registry_entry = _entry(hass, DOOR)
    assert registry_entry.area_id is None
    assert registry_entry.labels == set()


async def test_placement_is_not_alert_configuration(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The stored placement isn't part of the alert's data, so it can't restart a
    condition's delays."""
    kitchen = ar.async_get(hass).async_create("Kitchen")
    await setup_alerts(
        alert_subentry(
            "Back Door Open",
            placement={"area_id": kitchen.id, "labels": []},
        )
    )
    entity = hass.data["alert_redux"]["component"].get_entity(DOOR)
    assert "placement" not in entity.definition.data
    assert entity.definition.placement is not None
    assert _entry(hass, DOOR).area_id == kitchen.id


async def test_edit_shows_and_writes_the_registry(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Editing an alert pre-fills the area and labels from the registry (so
    changes made elsewhere show), and saving writes them back."""
    entry = await setup_alerts(alert_subentry("Back Door Open", "door"))
    areas = ar.async_get(hass)
    kitchen, hall = areas.async_create("Kitchen"), areas.async_create("Hall")
    safety = lr.async_get(hass).async_create("Safety")
    er.async_get(hass).async_update_entity(
        DOOR, area_id=kitchen.id, labels={safety.label_id}
    )

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ALERT),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "door"},
    )
    shown = _suggested(result["data_schema"].schema["placement"].schema.schema)
    assert shown == {"area_id": kitchen.id, "labels": [safety.label_id]}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**FORM, "placement": {"area_id": hall.id}},
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    registry_entry = _entry(hass, DOOR)
    assert registry_entry.area_id == hall.id
    # The form is an editor for the registry's values: a label left out is removed.
    assert registry_entry.labels == set()
    assert "placement" not in entry.subentries["door"].data


# A generator.


def _lock(hass: HomeAssistant, area_id: str | None) -> None:
    registry = er.async_get(hass)
    lock = registry.async_get_or_create(
        "lock", "test", "front_door", suggested_object_id="front_door"
    )
    registry.async_update_entity(lock.entity_id, area_id=area_id)
    hass.states.async_set(lock.entity_id, "unlocked", {"friendly_name": "Front Door"})


def _unlocked(**data: Any) -> dict[str, Any]:
    return generator_subentry(
        "Unlocked",
        "state",
        "gen",
        targets={"domains": ["lock"]},
        target_state="unlocked",
        **data,
    )


async def test_generated_alert_takes_its_targets_area_and_the_labels(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hall = ar.async_get(hass).async_create("Hall")
    safety = lr.async_get(hass).async_create("Safety")
    _lock(hass, hall.id)
    await setup_alerts(
        _unlocked(placement={"area_from_target": True, "labels": [safety.label_id]})
    )
    registry_entry = _entry(hass, FRONT_ALERT)
    assert registry_entry.area_id == hall.id
    assert registry_entry.labels == {safety.label_id, _alerts_label(hass)}


async def test_generated_alert_in_a_fixed_area(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hall = ar.async_get(hass).async_create("Hall")
    other = ar.async_get(hass).async_create("Other")
    _lock(hass, hall.id)
    await setup_alerts(_unlocked(placement={"area_id": other.id}))
    assert _entry(hass, FRONT_ALERT).area_id == other.id


async def test_generator_without_placement_leaves_alerts_alone(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A generator made before placement existed touches nothing."""
    hall = ar.async_get(hass).async_create("Hall")
    _lock(hass, hall.id)
    await setup_alerts(_unlocked())
    registry_entry = _entry(hass, FRONT_ALERT)
    assert registry_entry.area_id is None
    assert registry_entry.labels == {_alerts_label(hass)}


async def test_editing_the_generator_updates_its_alerts(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """New labels are added and dropped ones removed; a label put on by hand, and
    the alerts label, stay."""
    labels = lr.async_get(hass)
    hall = ar.async_get(hass).async_create("Hall")
    safety, doors = labels.async_create("Safety"), labels.async_create("Doors")
    mine = labels.async_create("Mine")
    _lock(hass, hall.id)
    entry = await setup_alerts(
        _unlocked(placement={"area_from_target": True, "labels": [safety.label_id]})
    )
    registry = er.async_get(hass)
    registry.async_update_entity(
        FRONT_ALERT, labels=_entry(hass, FRONT_ALERT).labels | {mine.label_id}
    )

    subentry = entry.subentries["gen"]
    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        data={
            **subentry.data,
            "placement": {"area_from_target": True, "labels": [doors.label_id]},
        },
    )
    await hass.async_block_till_done()
    assert _entry(hass, FRONT_ALERT).labels == {
        doors.label_id,
        mine.label_id,
        _alerts_label(hass),
    }


async def test_generated_alert_follows_its_target_area(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    areas = ar.async_get(hass)
    hall, porch = areas.async_create("Hall"), areas.async_create("Porch")
    _lock(hass, hall.id)
    await setup_alerts(_unlocked(placement={"area_from_target": True}))
    assert _entry(hass, FRONT_ALERT).area_id == hall.id

    er.async_get(hass).async_update_entity("lock.front_door", area_id=porch.id)
    await _settle(hass)
    assert _entry(hass, FRONT_ALERT).area_id == porch.id


async def test_restart_does_not_force_a_generated_alerts_area_back(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The stored placement is what a restored alert was built with, so setting
    up again finds nothing changed."""
    hall = ar.async_get(hass).async_create("Hall")
    safety = lr.async_get(hass).async_create("Safety")
    _lock(hass, hall.id)
    entry = await setup_alerts(
        _unlocked(placement={"area_from_target": True, "labels": [safety.label_id]})
    )
    er.async_get(hass).async_update_entity(FRONT_ALERT, area_id=None, labels=set())

    await hass.config_entries.async_reload(entry.entry_id)
    await _settle(hass)
    registry_entry = _entry(hass, FRONT_ALERT)
    assert registry_entry.area_id is None
    assert registry_entry.labels == set()


async def test_generator_form_defaults_to_the_targets_area(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A new generator uses its targets' areas; an existing one without any
    placement shows the option off."""
    entry = await setup_alerts(_unlocked())
    result = await _start_generator(hass, entry, "state")
    section = result["data_schema"].schema["placement"].schema.schema
    defaults = {str(key): key.default() for key in section if callable(key.default)}
    assert defaults.get("area_from_target") is True

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_GENERATOR),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "gen"},
    )
    section = result["data_schema"].schema["placement"].schema.schema
    defaults = {str(key): key.default() for key in section if callable(key.default)}
    assert defaults.get("area_from_target") is False
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**GENERATOR_FORM, "placement": {"area_from_target": False}}
    )
    assert "placement" not in entry.subentries["gen"].data


async def test_form_order(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Area and labels sit with the name, priority, and icon; the other three
    sections close the form, alphabetically (spec §12.1)."""
    entry = await setup_alerts()
    for result in (
        await _start(hass, entry, "state"),
        await _start_generator(hass, entry, "state"),
    ):
        keys = [str(key) for key in result["data_schema"].schema]
        assert keys[keys.index("icon") + 1] == "placement"
        assert keys[-3:] == ["notifications", "supersession", "voice"]
