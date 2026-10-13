"""The React to Alert Redux alerts blueprint (blueprints/automation/alert_redux).

The blueprint isn't part of the integration, so nothing else loads it. These
tests check that Home Assistant accepts it, that its description lists exactly
the variables it gives the actions, and that it picks the right alerts and
branches when the integration's events arrive.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util

BLUEPRINT = (
    Path(__file__).parent.parent
    / "blueprints"
    / "automation"
    / "alert_redux"
    / "react_to_alerts.yaml"
)

# The variables holding the inputs, which the actions don't need to know about.
INTERNAL = {
    "chosen_alerts",
    "chosen_labels",
    "chosen_generators",
    "min_priority",
    "every_fire",
    "end_reasons",
}


def _blueprint() -> Blueprint:
    return Blueprint(
        yaml_util.load_yaml(BLUEPRINT),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )


def _record(phase: str) -> list[dict[str, Any]]:
    """An action recording the variables, for the given branch."""
    return [
        {
            "action": "test.record",
            "data": {
                "phase": phase,
                "alert": "{{ alert }}",
                "alert_name": "{{ alert_name }}",
                "priority": "{{ priority }}",
                "message": "{{ message }}",
                "reason": "{{ reason }}",
                "latched": "{{ latched }}",
                "duration": "{{ duration }}",
                "subject_entity": "{{ subject_entity }}",
                "by_supersession": "{{ by_supersession }}",
            },
        }
    ]


async def _setup(hass: HomeAssistant, **inputs: Any) -> list[ServiceCall]:
    calls = async_mock_service(hass, "test", "record")
    config = BlueprintInputs(
        _blueprint(),
        {
            "alias": "React",
            "use_blueprint": {
                "path": "alert_redux/react_to_alerts.yaml",
                "input": {
                    "fired_actions": _record("fired"),
                    "ended_actions": _record("ended"),
                    "acked_actions": _record("acked"),
                    **inputs,
                },
            },
        },
    ).async_substitute()
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    return calls


def _alert(hass: HomeAssistant, object_id: str, **attributes: Any) -> str:
    entity_id = f"alert_redux.{object_id}"
    hass.states.async_set(
        entity_id,
        "active",
        {"friendly_name": object_id.replace("_", " ").title(), **attributes},
    )
    return entity_id


async def _event(
    hass: HomeAssistant, event: str, entity_id: str, priority: str = "warning", **data
) -> None:
    hass.bus.async_fire(
        f"alert_redux_{event}",
        {
            "entity_id": entity_id,
            "name": hass.states.get(entity_id).name,
            "priority": priority,
            "kind": "state",
            **data,
        },
    )
    await hass.async_block_till_done()


def test_home_assistant_accepts_it() -> None:
    """The blueprint passes Home Assistant's own schema."""
    blueprint = _blueprint()
    assert blueprint.domain == "automation"
    assert "alerts" in blueprint.inputs


def test_description_lists_the_variables() -> None:
    """Every variable the actions can use is described, and nothing else."""
    blueprint = _blueprint()
    described = set(re.findall(r"^- `(\w+)`", blueprint.metadata["description"], re.M))
    described |= set(
        re.findall(r"^- `\w+` and `(\w+)`", blueprint.metadata["description"], re.M)
    )
    variables = set(blueprint.data["variables"]) - INTERNAL
    assert described == variables


async def test_every_alert_by_default(hass: HomeAssistant) -> None:
    """With nothing chosen, every alert's firing, ending, and acknowledgement runs."""
    calls = await _setup(hass)
    alert = _alert(
        hass,
        "freezer_too_warm",
        message="The freezer is at -5 °C.",
        subject_entity="sensor.freezer",
    )

    await _event(hass, "fired", alert, fire_count=1, new_state="active")
    await _event(hass, "acked", alert, new_state="ack")
    await _event(
        hass,
        "ended",
        alert,
        fire_count=1,
        duration_seconds=4000,
        reason="resolved",
        new_state="idle",
    )

    assert [call.data["phase"] for call in calls] == ["fired", "acked", "ended"]
    fired, acked, ended = (call.data for call in calls)
    assert fired["alert"] == alert
    assert fired["alert_name"] == "Freezer Too Warm"
    assert fired["message"] == "The freezer is at -5 °C."
    assert fired["subject_entity"] == "sensor.freezer"
    assert acked["by_supersession"] is False
    assert ended["reason"] == "resolved"
    assert ended["duration"] == "1 hour 6 minutes"
    assert ended["latched"] is False


async def test_chosen_alerts_labels_and_generators(hass: HomeAssistant) -> None:
    """Only the chosen alerts, the alerts with a chosen label, or a chosen
    generator's alerts are included."""
    calls = await _setup(
        hass,
        alerts=["alert_redux.chosen"],
        generators=["sensor.alert_redux_generator_temperature"],
    )
    chosen = _alert(hass, "chosen")
    generated = _alert(
        hass, "kitchen_temperature", generated_by="sensor.alert_redux_generator_temperature"
    )
    other = _alert(hass, "other", generated_by="sensor.alert_redux_generator_doors")

    for alert in (chosen, generated, other):
        await _event(hass, "fired", alert, fire_count=1)

    assert [call.data["alert"] for call in calls] == [chosen, generated]


async def test_lowest_priority(hass: HomeAssistant) -> None:
    """Alerts below the lowest priority are left out."""
    calls = await _setup(hass, min_priority="critical")
    alert = _alert(hass, "door_open")

    await _event(hass, "fired", alert, priority="warning", fire_count=1)
    await _event(hass, "fired", alert, priority="emergency", fire_count=1)

    assert [call.data["priority"] for call in calls] == ["emergency"]


@pytest.mark.parametrize(("every_fire", "runs"), [(False, 1), (True, 2)])
async def test_firing_again(hass: HomeAssistant, every_fire: bool, runs: int) -> None:
    """Firing again while firing runs only with Every fire on."""
    calls = await _setup(hass, every_fire=every_fire)
    alert = _alert(hass, "doorbell")

    await _event(hass, "fired", alert, fire_count=1)
    await _event(hass, "fired", alert, fire_count=2)

    assert len(calls) == runs


@pytest.mark.parametrize(
    ("reason", "runs"),
    [("resolved", True), ("no_data", True), ("dismissed", False), ("disabled", False)],
)
async def test_end_reasons(hass: HomeAssistant, reason: str, runs: bool) -> None:
    """Only the chosen end reasons run the ended actions."""
    calls = await _setup(hass, end_reasons=["resolved", "no_data"])
    alert = _alert(hass, "water_leak")

    await _event(hass, "ended", alert, reason=reason, duration_seconds=30)

    assert bool(calls) is runs


async def test_latched_and_supersession(hass: HomeAssistant) -> None:
    """Ending into the latch and acknowledgement by supersession are told apart."""
    calls = await _setup(hass)
    alert = _alert(hass, "smoke")

    await _event(
        hass, "ended", alert, reason="resolved", duration_seconds=90, new_state="latched"
    )
    await _event(hass, "acked", alert, pre_acked_by="alert_redux.fire", new_state="ack")

    ended, acked = (call.data for call in calls)
    assert ended["latched"] is True
    assert ended["duration"] == "1 minute"
    assert acked["by_supersession"] is True
