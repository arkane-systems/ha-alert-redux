"""Tests for exporting and importing alert and generator definitions (spec §16)."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import entity_registry as er

from custom_components.alert_redux.const import DOMAIN

from .conftest import (
    SetupAlerts,
    alert_state_alert,
    alert_subentry,
    event_alert,
    generator_subentry,
    group_subentry,
    on_off_alert,
    state_alert,
    template_alert,
    threshold_alert,
    trigger_alert,
)

GROUP = "01GROUPQUIET"
GEN_A = "01GENERATORA"
GEN_B = "01GENERATORB"


async def _export(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    return await hass.services.async_call(
        DOMAIN, "export", data, blocking=True, return_response=True
    )


async def _import(hass: HomeAssistant, definitions: Any, **data: Any) -> dict[str, Any]:
    return await hass.services.async_call(
        DOMAIN,
        "import",
        {"definitions": definitions, **data},
        blocking=True,
        return_response=True,
    )


def _file(*alerts: dict[str, Any], generators: list[dict[str, Any]] | None = None):
    return {
        "format": "alert_redux",
        "version": 1,
        "alerts": list(alerts),
        "generators": generators or [],
    }


def _by_name(definitions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {definition["name"]: definition for definition in definitions}


async def _setup_everything(setup_alerts: SetupAlerts):
    return await setup_alerts(
        group_subentry("Quiet", GROUP),
        alert_subentry(
            "Back Door Open", "01MANUAL", ends_by_itself=False, notifier_groups=[GROUP]
        ),
        state_alert(
            "Leak", "binary_sensor.leak", "on", "01STATE", reminder_schedule=[5]
        ),
        template_alert("Hot", "{{ true }}", "01TEMPLATE", delay_on={"minutes": 5}),
        threshold_alert(
            "Cold", "01THRESHOLD", entity_id="sensor.temp", minimum="5", hysteresis=1
        ),
        on_off_alert(
            "Pump", "01ONOFF", on_template="{{ true }}", off_template="{{ false }}"
        ),
        trigger_alert(
            "Motion",
            [{"trigger": "state", "entity_id": "binary_sensor.motion", "to": "on"}],
            "01TRIGGER",
        ),
        event_alert("Button", "my_event", "01EVENT", duration={"seconds": 30}),
        alert_state_alert(
            "Watcher",
            "alert_redux.leak",
            ["active"],
            "01ALERTSTATE",
            supersedes=[{"alert": "alert_redux.hot", "propagation": "acknowledge"}],
        ),
        generator_subentry(
            "Low Batteries",
            "state",
            GEN_A,
            targets={"domains": ["binary_sensor"], "device_classes": ["battery"]},
            target_state="on",
            name_template="{{ target_name }} low",
            notifier_groups=[GROUP],
            supersedes=[{"generator": GEN_B}],
        ),
        generator_subentry(
            "Open Doors",
            "state",
            GEN_B,
            targets={"pattern": "^binary_sensor.door_"},
            target_state="on",
        ),
    )


async def test_export_everything(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An export has every alert and generator, with groups and generators by name."""
    await _setup_everything(setup_alerts)
    result = await _export(hass)

    assert result["format"] == "alert_redux"
    assert result["version"] == 1
    alerts = _by_name(result["alerts"])
    assert set(alerts) == {
        "Back Door Open",
        "Leak",
        "Hot",
        "Cold",
        "Pump",
        "Motion",
        "Button",
        "Watcher",
    }
    assert alerts["Back Door Open"]["id"] == "01MANUAL"
    assert alerts["Back Door Open"]["notifier_groups"] == ["Quiet"]
    assert alerts["Leak"]["kind"] == "state"
    generators = _by_name(result["generators"])
    assert generators["Low Batteries"]["notifier_groups"] == ["Quiet"]
    assert generators["Low Batteries"]["supersedes"] == [{"generator": "Open Doors"}]


async def test_export_selected(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Targeted exports are of the alerts, or of the generators' sensors."""
    await _setup_everything(setup_alerts)
    registry = er.async_get(hass)
    sensor = registry.async_get_entity_id("sensor", DOMAIN, f"generator_{GEN_B}")
    assert sensor is not None

    result = await _export(hass, entity_id=["alert_redux.leak", sensor])
    assert [alert["name"] for alert in result["alerts"]] == ["Leak"]
    assert [generator["name"] for generator in result["generators"]] == ["Open Doors"]

    with pytest.raises(ServiceValidationError):
        await _export(hass, entity_id="sensor.not_ours")


async def test_export_allowed_for_everyone_import_admin_only(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_read_only_user
) -> None:
    """Anyone can export; importing is for admins."""
    await setup_alerts(alert_subentry("Back Door Open"))
    context = Context(user_id=hass_read_only_user.id)

    result = await hass.services.async_call(
        DOMAIN, "export", {}, blocking=True, context=context, return_response=True
    )
    assert len(result["alerts"]) == 1
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "import",
            {"definitions": _file()},
            blocking=True,
            context=context,
        )


async def test_round_trip(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """What's exported and then deleted comes back the same, with the same IDs."""
    entry = await _setup_everything(setup_alerts)
    before = {
        subentry_id: (subentry.title, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
    }
    exported = await _export(hass)
    for subentry_id, subentry in list(entry.subentries.items()):
        if subentry.subentry_type != "notifier_group":
            hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done()
    assert hass.states.get("alert_redux.leak") is None

    result = await _import(hass, exported)
    await hass.async_block_till_done()

    assert len(result["created"]) == 10
    assert result["updated"] == result["unchanged"] == []
    after = {
        subentry_id: (subentry.title, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
    }
    assert after == before
    assert hass.states.get("alert_redux.leak") is not None
    assert hass.states.get("alert_redux.low_batteries") is None  # no targets exist


async def test_import_again_is_unchanged(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Importing what's already there changes nothing, even without overwrite."""
    entry = await _setup_everything(setup_alerts)
    exported = await _export(hass)
    before = {i: s.data for i, s in entry.subentries.items()}

    result = await _import(hass, exported)
    assert result["created"] == result["updated"] == []
    assert len(result["unchanged"]) == 10
    assert {i: s.data for i, s in entry.subentries.items()} == before


async def test_overwrite(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """A changed definition replaces the existing one only with overwrite."""
    entry = await _setup_everything(setup_alerts)
    exported = await _export(hass)
    changed = copy.deepcopy(exported)
    leak = _by_name(changed["alerts"])["Leak"]
    leak["priority"] = "critical"
    leak["target_state"] = "off"

    with pytest.raises(ServiceValidationError, match="Leak.*exists"):
        await _import(hass, changed)
    assert entry.subentries["01STATE"].data["priority"] == "warning"

    result = await _import(hass, changed, overwrite=True)
    assert [item["name"] for item in result["updated"]] == ["Leak"]
    assert entry.subentries["01STATE"].data["priority"] == "critical"
    assert entry.subentries["01STATE"].data["target_state"] == "off"
    # In place, as an edit.
    await hass.async_block_till_done()
    assert hass.states.get("alert_redux.leak").attributes["priority"] == "critical"


async def test_match_by_name_without_id(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A definition without an id is the existing one of that name, whatever the case."""
    entry = await _setup_everything(setup_alerts)
    definition = {
        "name": "leak",
        "kind": "state",
        "entity_id": "binary_sensor.leak",
        "target_state": "on",
        "priority": "emergency",
    }
    result = await _import(hass, _file(definition), overwrite=True)
    assert result["updated"][0]["id"] == "01STATE"
    assert entry.subentries["01STATE"].data["priority"] == "emergency"
    assert entry.subentries["01STATE"].title == "leak"


async def test_new_definitions_by_hand(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A hand-written definition gets the forms' defaults and a new ID."""
    entry = await setup_alerts(group_subentry("Quiet", GROUP))
    result = await _import(
        hass,
        _file(
            {
                "name": "Garage Open",
                "kind": "state",
                "entity_id": "binary_sensor.garage",
                "target_state": "on",
                "notifier_groups": ["quiet"],
                "proxy_switch": False,
                "message": "",
                "supersedes": [],
            }
        ),
    )
    await hass.async_block_till_done()
    (created,) = result["created"]
    subentry = entry.subentries[created["id"]]
    assert subentry.title == "Garage Open"
    assert dict(subentry.data) == {
        "kind": "state",
        "entity_id": "binary_sensor.garage",
        "target_state": "on",
        "priority": "warning",
        "acknowledgeable": True,
        "notifier_groups": [GROUP],
    }
    assert hass.states.get("alert_redux.garage_open") is not None


async def test_durations_are_converted(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Seconds and "HH:MM:SS" become what the duration selector stores."""
    entry = await setup_alerts()
    result = await _import(
        hass,
        _file(
            {
                "name": "Slow",
                "kind": "template",
                "template": "{{ true }}",
                "delay_on": "00:05:00",
                "delay_off": 90,
            }
        ),
    )
    data = entry.subentries[result["created"][0]["id"]].data
    assert data["delay_on"] == {"hours": 0, "minutes": 5, "seconds": 0}
    assert data["delay_off"] == {"hours": 0, "minutes": 1, "seconds": 30}


async def test_dry_run_changes_nothing(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A dry run says what would happen, and refuses what would be refused."""
    entry = await setup_alerts(alert_subentry("Back Door Open", "01MANUAL"))
    new = {"name": "Garage", "kind": "manual"}

    result = await _import(hass, _file(new), dry_run=True)
    assert result["dry_run"] is True
    assert [item["name"] for item in result["created"]] == ["Garage"]
    assert set(entry.subentries) == {"01MANUAL"}

    with pytest.raises(ServiceValidationError):
        await _import(hass, _file({"name": "X", "kind": "nonsense"}), dry_run=True)


async def test_all_or_nothing_lists_every_problem(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """One bad definition stops the import, and the error lists all the problems."""
    entry = await setup_alerts(
        group_subentry("Quiet", GROUP),
        alert_subentry("Back Door Open", "01MANUAL"),
        alert_subentry("Side Door", "01SIDE"),
    )
    definitions = _file(
        {"name": "Fine", "kind": "manual"},
        {"name": "Back Door Open", "kind": "manual", "priority": "critical"},
        {"name": "Bad Group", "kind": "manual", "notifier_groups": ["Loud"]},
        {"name": "No Entity", "kind": "state", "target_state": "on"},
        {"name": "Limits", "kind": "threshold", "entity_id": "sensor.t"},
        {"name": "Odd Field", "kind": "manual", "colour": "red"},
        {"id": "01OTHER", "name": "SIDE DOOR", "kind": "manual"},
    )
    with pytest.raises(ServiceValidationError) as err:
        await _import(hass, definitions)

    message = str(err.value)
    assert "alert 'Back Door Open': exists" in message
    assert "alert 'Bad Group': unknown_group" in message
    assert "alert 'No Entity': invalid_definition" in message
    assert "alert 'Limits': limit_required" in message
    assert "alert 'Odd Field': invalid_definition" in message
    assert "alert 'SIDE DOOR': name_exists" in message
    assert set(entry.subentries) == {GROUP, "01MANUAL", "01SIDE"}


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ("not a mapping", "invalid_file"),
        ({"format": "other", "version": 1}, "invalid_file"),
        ({"format": "alert_redux", "version": 2}, "invalid_file"),
        ({"format": "alert_redux", "version": 1, "extra": []}, "invalid_file"),
        (_file({"kind": "manual"}), "invalid_definition"),
        (
            _file({"name": "A", "kind": "manual"}, {"name": "a", "kind": "manual"}),
            "duplicate_in_file",
        ),
        (
            _file({"name": "A", "kind": "manual", "duration": "soon"}),
            "invalid_definition",
        ),
        (
            _file({"name": "A", "kind": "manual", "priority": "meh"}),
            "invalid_definition",
        ),
        (
            _file({"name": "A", "kind": "event", "event_type": "x", "event_data": 3}),
            "invalid_definition",
        ),
        (
            _file(
                {
                    "name": "A",
                    "kind": "template",
                    "template": "{{ 1 }}",
                    "supersedes": [{"alert": "alert_redux.a"}],
                }
            ),
            "supersedes_self",
        ),
        (
            _file(
                {
                    "name": "A",
                    "kind": "manual",
                    "supersedes": [
                        {"alert": "alert_redux.b", "propagation": "snooze"},
                    ],
                }
            ),
            "snooze_duration_missing",
        ),
        (
            _file({"name": "A", "kind": "trigger", "triggers": [{"trigger": "nope"}]}),
            "invalid_trigger",
        ),
        (
            _file(
                {
                    "name": "A",
                    "kind": "manual",
                    "buttons": [
                        {"label": "Close", "action": [{"action": "test.x"}]},
                        {"label": "Close", "action": [{"action": "test.y"}]},
                    ],
                }
            ),
            "button_label_duplicate",
        ),
        (
            _file(generators=[{"name": "G", "kind": "state", "target_state": "on"}]),
            "invalid_definition",
        ),
        (
            _file(
                generators=[
                    {
                        "name": "G",
                        "kind": "manual",
                        "targets": {"domains": ["sensor"]},
                    }
                ]
            ),
            "invalid_definition",
        ),
        (
            _file(
                generators=[
                    {
                        "name": "G",
                        "kind": "state",
                        "target_state": "on",
                        "targets": {"exclude": ["sensor.x"]},
                    }
                ]
            ),
            "targets_required",
        ),
        (
            _file(
                generators=[
                    {
                        "name": "G",
                        "kind": "state",
                        "target_state": "on",
                        "targets": {"domains": ["sensor"]},
                        "supersedes": [{"generator": "Nobody"}],
                    }
                ]
            ),
            "unknown_generator",
        ),
        (
            _file(
                generators=[
                    {
                        "name": "G",
                        "kind": "state",
                        "target_state": "on",
                        "targets": {"domains": ["sensor"]},
                        "supersedes": [{"generator": "G", "alert": "alert_redux.x"}],
                    }
                ]
            ),
            "relationship_target",
        ),
    ],
)
async def test_problems(
    hass: HomeAssistant, setup_alerts: SetupAlerts, payload: Any, code: str
) -> None:
    """Each kind of problem is refused with its code."""
    await setup_alerts()
    with pytest.raises(ServiceValidationError) as err:
        await _import(hass, payload)
    assert code in str(err.value)


async def test_kind_cannot_change(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An existing alert keeps its kind: the entities are made per kind."""
    await setup_alerts(alert_subentry("Back Door Open", "01MANUAL"))
    with pytest.raises(ServiceValidationError, match="kind_changed"):
        await _import(
            hass,
            _file(
                {
                    "id": "01MANUAL",
                    "name": "Back Door Open",
                    "kind": "template",
                    "template": "{{ true }}",
                }
            ),
            overwrite=True,
        )


async def test_id_used_by_another_type(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An id can't take over a subentry of another type."""
    await setup_alerts(group_subentry("Quiet", GROUP))
    with pytest.raises(ServiceValidationError, match="id_in_use"):
        await _import(hass, _file({"id": GROUP, "name": "A", "kind": "manual"}))


async def test_new_alert_clashing_with_an_entity_id(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A new alert whose entity ID is another alert's is a conflict."""
    await setup_alerts(alert_subentry("Back Door Open", "01MANUAL"))
    with pytest.raises(ServiceValidationError, match="entity_id_clash"):
        await _import(hass, _file({"name": "Back-Door Open", "kind": "manual"}))
    with pytest.raises(ServiceValidationError, match="entity_id_clash"):
        await _import(
            hass,
            _file(
                {"name": "Side Door", "kind": "manual"},
                {"name": "Side-Door", "kind": "manual"},
            ),
        )


async def test_cycle_across_the_import(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Alerts that supersede each other within one import are a cycle."""
    entry = await setup_alerts()
    with pytest.raises(ServiceValidationError, match="supersedes_cycle"):
        await _import(
            hass,
            _file(
                {
                    "name": "One",
                    "kind": "manual",
                    "supersedes": [{"alert": "alert_redux.two"}],
                },
                {
                    "name": "Two",
                    "kind": "manual",
                    "supersedes": [{"alert": "alert_redux.one"}],
                },
            ),
        )
    assert not entry.subentries


async def test_cycle_through_a_generator(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Generators superseding each other, even via names in the same file."""
    await setup_alerts()
    targets = {"domains": ["sensor"]}
    with pytest.raises(ServiceValidationError, match="supersedes_cycle"):
        await _import(
            hass,
            _file(
                generators=[
                    {
                        "name": "A",
                        "kind": "state",
                        "target_state": "on",
                        "targets": targets,
                        "supersedes": [{"generator": "B"}],
                    },
                    {
                        "name": "B",
                        "kind": "state",
                        "target_state": "on",
                        "targets": targets,
                        "supersedes": [{"generator": "a"}],
                    },
                ]
            ),
        )


async def test_generators_by_name_in_one_file(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """New generators can name each other, and get IDs for it."""
    entry = await setup_alerts()
    targets = {"domains": ["sensor"]}
    result = await _import(
        hass,
        _file(
            generators=[
                {
                    "name": "A",
                    "kind": "state",
                    "target_state": "on",
                    "targets": targets,
                    "supersedes": [{"generator": "B"}],
                },
                {
                    "name": "B",
                    "kind": "state",
                    "target_state": "on",
                    "targets": targets,
                },
            ]
        ),
    )
    ids = {item["name"]: item["id"] for item in result["created"]}
    assert entry.subentries[ids["A"]].data["supersedes"] == [{"generator": ids["B"]}]
