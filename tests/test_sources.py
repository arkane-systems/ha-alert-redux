"""Tests for condition alert inputs (spec §4.1, §4.4)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.alert_redux.model import Reading
from custom_components.alert_redux.sources import (
    Source,
    SourceSet,
    StateSource,
    TemplateSource,
    ThresholdSource,
    value_template,
)

DOOR = "binary_sensor.door"
TEMP = "sensor.temperature"


class Recorder:
    """Collects what a source reports."""

    def __init__(self) -> None:
        self.results: list[tuple[bool | None, list[str]]] = []

    def __call__(self, result: bool | None, missing_inputs: list[str]) -> None:
        self.results.append((result, missing_inputs))

    @property
    def last(self) -> tuple[bool | None, list[str]]:
        return self.results[-1]


async def _start(hass: HomeAssistant, source: Source) -> Recorder:
    recorder = Recorder()
    source.async_start(recorder)
    await hass.async_block_till_done()
    return recorder


async def test_state_source(hass: HomeAssistant) -> None:
    hass.states.async_set(DOOR, "off")
    source = StateSource(hass, DOOR, "on")
    recorder = await _start(hass, source)
    assert recorder.last == (False, [])

    for state, expected in (
        ("on", (True, [])),
        ("unavailable", (None, [DOOR])),
        ("unknown", (None, [DOOR])),
        ("off", (False, [])),
    ):
        hass.states.async_set(DOOR, state)
        await hass.async_block_till_done()
        assert recorder.last == expected

    hass.states.async_remove(DOOR)
    await hass.async_block_till_done()
    assert recorder.last == (None, [DOOR])

    source.async_stop()
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    assert recorder.last == (None, [DOOR])


async def test_state_source_late_entity(hass: HomeAssistant) -> None:
    """An entity that doesn't exist yet is no data until it appears."""
    recorder = await _start(hass, StateSource(hass, DOOR, "on"))
    assert recorder.last == (None, [DOOR])
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    assert recorder.last == (True, [])


async def test_state_source_targeting_unavailable(hass: HomeAssistant) -> None:
    """Targeting unavailable makes it a match, not missing data."""
    hass.states.async_set(DOOR, "unavailable")
    recorder = await _start(hass, StateSource(hass, DOOR, "unavailable"))
    assert recorder.last == (True, [])
    hass.states.async_set(DOOR, "unknown")
    await hass.async_block_till_done()
    assert recorder.last == (None, [DOOR])
    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    assert recorder.last == (False, [])


@pytest.mark.parametrize(
    ("rendered", "expected"),
    [
        ("true", True),
        ("on", True),
        ("Yes", True),
        ("1", True),
        ("5", True),
        ("false", False),
        ("off", False),
        ("no", False),
        ("0", False),
        ("unknown", None),
        ("unavailable", None),
        ("none", None),
        ("", None),
        ("banana", None),
    ],
)
async def test_template_truthiness(
    hass: HomeAssistant, rendered: str, expected: bool | None
) -> None:
    hass.states.async_set("sensor.value", rendered)
    recorder = await _start(
        hass, TemplateSource(hass, "{{ states('sensor.value') }}", "test")
    )
    assert recorder.last[0] is expected


async def test_template_tracks_changes_and_missing_inputs(hass: HomeAssistant) -> None:
    hass.states.async_set(TEMP, "20")
    source = TemplateSource(
        hass, "{{ states('sensor.temperature') | float > 25 }}", "t"
    )
    recorder = await _start(hass, source)
    assert recorder.last == (False, [])

    hass.states.async_set(TEMP, "30")
    await hass.async_block_till_done()
    assert recorder.last == (True, [])

    # float without a default fails on a non-number: a render error.
    hass.states.async_set(TEMP, "unavailable")
    await hass.async_block_till_done()
    assert recorder.last == (None, [TEMP])

    hass.states.async_set(TEMP, "10")
    await hass.async_block_till_done()
    assert recorder.last == (False, [])
    source.async_stop()


async def test_template_undefined_variable(hass: HomeAssistant) -> None:
    recorder = await _start(hass, TemplateSource(hass, "{{ nonexistent > 1 }}", "t"))
    assert recorder.last[0] is None


async def test_source_set(hass: HomeAssistant) -> None:
    """Results are reported together, once every source has reported."""
    hass.states.async_set(DOOR, "on")
    hass.states.async_set(TEMP, "30")
    sources = SourceSet(
        {
            "main": StateSource(hass, DOOR, "on"),
            "condition": TemplateSource(
                hass, "{{ states('sensor.temperature') | float > 25 }}", "t"
            ),
        }
    )
    reports: list[dict] = []
    sources.async_start(reports.append)
    await hass.async_block_till_done()
    assert reports[0] == {"main": (True, []), "condition": (True, [])}

    hass.states.async_set(TEMP, "20")
    await hass.async_block_till_done()
    assert reports[-1] == {"main": (True, []), "condition": (False, [])}

    hass.states.async_set(DOOR, "unavailable")
    await hass.async_block_till_done()
    assert reports[-1]["main"] == (None, [DOOR])

    sources.async_stop()
    count = len(reports)
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    assert len(reports) == count


async def test_threshold_source(hass: HomeAssistant) -> None:
    hass.states.async_set(TEMP, "30")
    hass.states.async_set("input_number.max", "28")
    recorder = await _start(
        hass,
        ThresholdSource(
            hass,
            value_template(TEMP, None),
            "5",
            "{{ states('input_number.max') }}",
            "t",
        ),
    )
    assert recorder.last == (Reading(30.0, 5.0, 28.0), [])

    hass.states.async_set("input_number.max", "unavailable")
    await hass.async_block_till_done()
    assert recorder.last == (None, ["input_number.max"])

    hass.states.async_set("input_number.max", "35")
    hass.states.async_set(TEMP, "hot")
    await hass.async_block_till_done()
    assert recorder.last == (None, [])


async def test_threshold_attribute(hass: HomeAssistant) -> None:
    hass.states.async_set("climate.lounge", "heat", {"current_temperature": 19.5})
    recorder = await _start(
        hass,
        ThresholdSource(
            hass,
            value_template("climate.lounge", "current_temperature"),
            "18",
            None,
            "t",
        ),
    )
    assert recorder.last == (Reading(19.5, 18.0, None), [])
