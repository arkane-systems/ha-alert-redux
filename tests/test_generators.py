"""Tests for generators: one alert per matching target (spec §12.3)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EntityCategory
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
    area_registry as ar,
)
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_CREATED,
    EVENT_DELETED,
    STORAGE_KEY,
    SUBENTRY_GENERATOR,
)
from custom_components.alert_redux.generators import Candidate, TargetCriteria

from .conftest import SetupAlerts, alert_subentry, generator_subentry

FRONT = "lock.front_door"
BACK = "lock.back_door"
FRONT_ALERT = "alert_redux.front_door_unlocked"
BACK_ALERT = "alert_redux.back_door_unlocked"
SENSOR = "sensor.alert_redux_generator_unlocked"


@pytest.fixture(autouse=True)
def no_reload(hass: HomeAssistant) -> Iterator[None]:
    """Fail any test that reloads the entry: changes apply in place."""
    with patch.object(
        hass.config_entries,
        "async_schedule_reload",
        side_effect=AssertionError("entry reloaded"),
    ):
        yield


def _lock(
    hass: HomeAssistant, entity_id: str, state: str = "locked", **options: Any
) -> er.RegistryEntry:
    """Register a lock and give it a state."""
    domain, object_id = entity_id.split(".", 1)
    entry = er.async_get(hass).async_get_or_create(
        domain, "test", object_id, suggested_object_id=object_id, **options
    )
    hass.states.async_set(entry.entity_id, state, {"friendly_name": _title(object_id)})
    return entry


def _title(object_id: str) -> str:
    return object_id.replace("_", " ").title()


def _unlocked(**data: Any) -> dict[str, Any]:
    return generator_subentry(
        "Unlocked",
        "state",
        "gen",
        targets={"domains": ["lock"]},
        target_state="unlocked",
        **data,
    )


async def _settle(hass: HomeAssistant, seconds: float = 2) -> None:
    """Let the generators' debounced refresh run."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


# Matching (spec §12.3): AND across criteria, OR within each.


def _candidate(entity_id: str, **fields: Any) -> Candidate:
    return Candidate(entity_id=entity_id, key=entity_id, name=entity_id, **fields)


def test_criteria() -> None:
    """Every criterion that's set must match; any value within one will do."""
    door = _candidate(
        "binary_sensor.front_door",
        labels=frozenset({"doors", "outside"}),
        area="hall",
        device_class="door",
    )
    assert not TargetCriteria().matches(door)
    assert TargetCriteria(labels=frozenset({"doors", "other"})).matches(door)
    assert not TargetCriteria(labels=frozenset({"other"})).matches(door)
    assert TargetCriteria(
        domains=frozenset({"binary_sensor"}),
        device_classes=frozenset({"door", "window"}),
        areas=frozenset({"hall"}),
    ).matches(door)
    assert not TargetCriteria(
        domains=frozenset({"binary_sensor"}), areas=frozenset({"kitchen"})
    ).matches(door)
    assert TargetCriteria(pattern="binary_sensor.*_door").matches(door)
    assert not TargetCriteria(pattern="lock.*").matches(door)
    assert not TargetCriteria(
        pattern="binary_sensor.*", exclude=frozenset({"binary_sensor.front_door"})
    ).matches(door)


# Generating alerts.


async def test_one_alert_per_target(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Each matching entity gets its own alert, about it."""
    _lock(hass, FRONT, "unlocked")
    _lock(hass, BACK)
    hass.states.async_set("binary_sensor.back_door", "on")
    await setup_alerts(_unlocked())

    front = hass.states.get(FRONT_ALERT)
    assert front.state == "active"
    assert front.name == "Front Door Unlocked"
    assert front.attributes["source_entity"] == FRONT
    assert front.attributes["subject_entity"] == FRONT
    assert front.attributes["generated_by"] == SENSOR
    assert hass.states.get(BACK_ALERT).state == "idle"
    assert hass.states.get("alert_redux.back_door_unlocked_2") is None

    sensor = hass.states.get(SENSOR)
    assert sensor.state == "2"
    assert sensor.name == "Alert Redux generator Unlocked"
    assert sensor.attributes["targets"] == [BACK, FRONT]
    assert sensor.attributes["alerts"] == [BACK_ALERT, FRONT_ALERT]
    assert sensor.attributes["problems"] == []
    # Generated alerts get the alerts label; the generator's sensor doesn't.
    registry = er.async_get(hass)
    assert registry.async_get(FRONT_ALERT).labels
    assert not registry.async_get(SENSOR).labels


async def test_target_added_later(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A lock added later gets its alert once the registries settle."""
    _lock(hass, FRONT)
    await setup_alerts(_unlocked())
    created = async_capture_events(hass, EVENT_CREATED)

    _lock(hass, BACK, "unlocked")
    await _settle(hass)

    assert hass.states.get(BACK_ALERT).state == "active"
    assert [event.data["entity_id"] for event in created] == [BACK_ALERT]
    assert hass.states.get(SENSOR).state == "2"


async def test_target_without_registry_entry(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An entity with no registry entry matches by domain, and goes when its
    state does."""
    await setup_alerts(_unlocked())
    hass.states.async_set("lock.shed", "unlocked", {"friendly_name": "Shed"})
    await _settle(hass)
    assert hass.states.get("alert_redux.shed_unlocked").state == "active"

    deleted = async_capture_events(hass, EVENT_DELETED)
    hass.states.async_remove("lock.shed")
    await _settle(hass)
    assert hass.states.get("alert_redux.shed_unlocked") is None
    assert [event.data["entity_id"] for event in deleted] == [
        "alert_redux.shed_unlocked"
    ]


async def test_target_stops_matching(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """Removing a target's label removes its alert, announcing the deletion."""
    label = lr.async_get(hass).async_create("Watched")
    front = _lock(hass, FRONT, "unlocked")
    registry = er.async_get(hass)
    registry.async_update_entity(front.entity_id, labels={label.label_id})
    entry = await setup_alerts(
        generator_subentry(
            "Unlocked",
            subentry_id="gen",
            targets={"labels": [label.label_id]},
            target_state="unlocked",
        )
    )
    assert hass.states.get(FRONT_ALERT).state == "active"
    deleted = async_capture_events(hass, EVENT_DELETED)

    registry.async_update_entity(front.entity_id, labels=set())
    await _settle(hass)

    assert hass.states.get(FRONT_ALERT) is None
    assert registry.async_get(FRONT_ALERT) is None
    assert [event.data["entity_id"] for event in deleted] == [FRONT_ALERT]
    assert deleted[0].data["old_state"] == "active"
    assert hass.states.get(SENSOR).state == "0"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"]["alerts"] == {}


async def test_matching_through_device(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Labels and areas count through the entity's device."""
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Hall")
    label = lr.async_get(hass).async_create("Doors")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "front")}
    )
    dr.async_get(hass).async_update_device(
        device.id, area_id=area.id, labels={label.label_id}
    )
    _lock(hass, FRONT, device_id=device.id)
    _lock(hass, BACK)
    await setup_alerts(
        generator_subentry(
            "Unlocked",
            subentry_id="gen",
            targets={"areas": [area.id], "labels": [label.label_id]},
            target_state="unlocked",
        )
    )
    assert hass.states.get(SENSOR).attributes["targets"] == [FRONT]


async def test_which_entities_can_be_targets(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Diagnostic entities match; disabled and configuration entities, and
    Alert Redux's own entities, don't."""
    _lock(hass, "sensor.front_battery", "10", entity_category=EntityCategory.DIAGNOSTIC)
    _lock(hass, "sensor.back_battery", "10", disabled_by=er.RegistryEntryDisabler.USER)
    _lock(hass, "sensor.lock_setting", "10", entity_category=EntityCategory.CONFIG)
    await setup_alerts(
        generator_subentry(
            "Low",
            "threshold",
            "gen",
            targets={"domains": ["sensor"]},
            minimum="20",
            hysteresis=0,
        )
    )
    sensor = hass.states.get("sensor.alert_redux_generator_low")
    assert sensor.attributes["targets"] == ["sensor.front_battery"]
    alert = hass.states.get("alert_redux.front_battery_low")
    assert alert.state == "active"
    assert alert.attributes["value"] == 10


async def test_alert_state_generator(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An alert state generator watches fixed alerts; generated alerts are never
    targets, so it can't feed on its own."""
    await setup_alerts(
        alert_subentry("Leak", subentry_id="leak"),
        generator_subentry(
            "Escalated",
            "alert_state",
            "gen",
            targets={"domains": [DOMAIN]},
            alert_states=["active"],
        ),
    )
    # On a first setup, the fixed alert is registered after generators look.
    await _settle(hass)
    sensor = hass.states.get("sensor.alert_redux_generator_escalated")
    assert sensor.attributes["targets"] == ["alert_redux.leak"]
    await hass.services.async_call(
        DOMAIN, "fire", {"entity_id": "alert_redux.leak"}, blocking=True
    )
    await hass.async_block_till_done()
    escalated = hass.states.get("alert_redux.leak_escalated")
    assert escalated.state == "active"
    assert escalated.attributes["source_entity"] == "alert_redux.leak"


async def test_target_variables(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Templates, including the name template and messages, get the target."""
    _lock(hass, FRONT, "unlocked")
    await setup_alerts(
        generator_subentry(
            "Open",
            "template",
            "gen",
            targets={"domains": ["lock"]},
            name_template="{{ target_name }} is open",
            template="{{ is_state(target, 'unlocked') }}",
            message="{{ target_name }} ({{ target }}) is unlocked",
        )
    )
    alert = hass.states.get("alert_redux.front_door_open")
    assert alert.name == "Front Door is open"
    assert alert.state == "active"
    assert alert.attributes["message"] == "Front Door (lock.front_door) is unlocked"
    assert alert.attributes["subject_entity"] == FRONT

    hass.states.async_set(FRONT, "locked")
    await hass.async_block_till_done()
    assert hass.states.get("alert_redux.front_door_open").state == "idle"


async def test_name_template_failure(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A name template that fails gives the default name, and a problem."""
    _lock(hass, FRONT)
    await setup_alerts(_unlocked(name_template="{{ target_name | nonexistent }}"))
    assert hass.states.get(FRONT_ALERT).name == "Front Door Unlocked"
    (problem,) = hass.states.get(SENSOR).attributes["problems"]
    assert problem.startswith(f"{FRONT}: the name template failed")


async def test_target_renamed(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """A renamed target keeps its alert, its state, and its entity ID."""
    _lock(hass, FRONT, "unlocked")
    await setup_alerts(_unlocked())
    await hass.services.async_call(
        DOMAIN, "ack", {"entity_id": FRONT_ALERT}, blocking=True
    )
    deleted = async_capture_events(hass, EVENT_DELETED)
    created = async_capture_events(hass, EVENT_CREATED)

    er.async_get(hass).async_update_entity(FRONT, new_entity_id="lock.main_door")
    hass.states.async_remove(FRONT)
    hass.states.async_set("lock.main_door", "unlocked", {"friendly_name": "Main Door"})
    await _settle(hass)

    alert = hass.states.get(FRONT_ALERT)
    assert alert.state == "ack"
    assert alert.attributes["source_entity"] == "lock.main_door"
    assert alert.name == "Main Door Unlocked"
    assert hass.states.get(SENSOR).attributes["targets"] == ["lock.main_door"]
    assert not deleted
    assert not created


# Changing generators in place.


def _generator(data: dict[str, Any]) -> ConfigSubentry:
    return ConfigSubentry(
        data=MappingProxyType(data["data"]),
        subentry_type=SUBENTRY_GENERATOR,
        title=data["title"],
        unique_id=None,
    )


async def test_generator_added(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    _lock(hass, FRONT, "unlocked")
    entry = await setup_alerts()
    hass.config_entries.async_add_subentry(entry, _generator(_unlocked()))
    await hass.async_block_till_done()
    assert hass.states.get(FRONT_ALERT).state == "active"
    assert hass.states.get(SENSOR).state == "1"


async def test_generator_edited(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Editing a generator updates its alerts in place."""
    _lock(hass, FRONT, "unlocked")
    _lock(hass, BACK)
    entry = await setup_alerts(_unlocked())
    await hass.services.async_call(
        DOMAIN, "ack", {"entity_id": FRONT_ALERT}, blocking=True
    )
    subentry = entry.subentries["gen"]
    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        title="Insecure",
        data={
            **subentry.data,
            "priority": "critical",
            "targets": {"pattern": "*front*"},
        },
    )
    await hass.async_block_till_done()

    alert = hass.states.get(FRONT_ALERT)
    assert alert.state == "ack"
    assert alert.name == "Front Door Insecure"
    assert alert.attributes["priority"] == "critical"
    assert hass.states.get(BACK_ALERT) is None
    sensor = hass.states.get(SENSOR)
    assert sensor.name == "Alert Redux generator Insecure"
    assert sensor.state == "1"


async def test_generator_deleted(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Deleting a generator removes its alerts and its sensor."""
    _lock(hass, FRONT)
    _lock(hass, BACK)
    entry = await setup_alerts(_unlocked())
    deleted = async_capture_events(hass, EVENT_DELETED)

    hass.config_entries.async_remove_subentry(entry, "gen")
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_ALERT) is None
    assert hass.states.get(BACK_ALERT) is None
    assert hass.states.get(SENSOR) is None
    assert sorted(event.data["entity_id"] for event in deleted) == [
        BACK_ALERT,
        FRONT_ALERT,
    ]


# The refresh action.


async def test_refresh_generator(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Refreshing re-evaluates targets straight away."""
    await setup_alerts(_unlocked())
    _lock(hass, FRONT, "unlocked")
    await hass.services.async_call(
        DOMAIN, "refresh_generator", {"entity_id": SENSOR}, blocking=True
    )
    assert hass.states.get(FRONT_ALERT).state == "active"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "refresh_generator",
            {"entity_id": "sensor.alert_redux_firing"},
            blocking=True,
        )


# Restarts, and the startup grace period.


async def test_generated_alert_survives_reload(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A generated alert's state is restored, and it isn't taken for deleted."""
    _lock(hass, FRONT, "unlocked")
    entry = await setup_alerts(_unlocked())
    await hass.services.async_call(
        DOMAIN, "ack", {"entity_id": FRONT_ALERT}, blocking=True
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    events = [async_capture_events(hass, e) for e in (EVENT_CREATED, EVENT_DELETED)]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(FRONT_ALERT).state == "ack"
    assert all(not captured for captured in events)


async def test_startup_grace(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """While HA starts, an alert whose target hasn't appeared is kept until the
    grace period after startup has passed."""
    hass.states.async_set("lock.shed", "unlocked", {"friendly_name": "Shed"})
    _lock(hass, FRONT, "unlocked")
    entry = await setup_alerts(_unlocked())
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # A restart: the shed's lock (no registry entry) hasn't come back yet.
    hass.states.async_remove("lock.shed")
    hass.set_state(CoreState.starting)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # Kept, and still firing through the no-data grace period.
    shed = hass.states.get("alert_redux.shed_unlocked")
    assert shed.state == "active"
    assert shed.attributes["missing_inputs"] == ["lock.shed"]
    await _settle(hass)
    assert hass.states.get("alert_redux.shed_unlocked") is not None

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=4))
    await _settle(hass)
    assert hass.states.get("alert_redux.shed_unlocked") is not None

    freezer.tick(timedelta(minutes=2))
    await _settle(hass)
    assert hass.states.get("alert_redux.shed_unlocked") is None
    assert hass.states.get(FRONT_ALERT).state == "active"


async def test_startup_grace_target_returns(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A target that turns up during the grace period keeps its alert."""
    hass.states.async_set("lock.shed", "unlocked", {"friendly_name": "Shed"})
    entry = await setup_alerts(_unlocked())
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_remove("lock.shed")
    hass.set_state(CoreState.starting)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set("lock.shed", "unlocked", {"friendly_name": "Shed"})
    await _settle(hass)

    freezer.tick(timedelta(minutes=6))
    await _settle(hass)
    assert hass.states.get("alert_redux.shed_unlocked").state == "active"
