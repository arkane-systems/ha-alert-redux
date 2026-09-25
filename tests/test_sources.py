"""Tests for condition alert inputs (spec §4.1, §4.4)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.alert_redux.sources import (
    AndSource,
    Source,
    StateSource,
    TemplateSource,
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


async def test_and_source(hass: HomeAssistant) -> None:
    hass.states.async_set(DOOR, "on")
    hass.states.async_set(TEMP, "30")
    source = AndSource(
        hass,
        StateSource(hass, DOOR, "on"),
        TemplateSource(hass, "{{ states('sensor.temperature') | float > 25 }}", "t"),
    )
    recorder = await _start(hass, source)
    # Nothing is reported until both inputs have been.
    assert recorder.results[0] == (True, [])
    assert recorder.last == (True, [])

    hass.states.async_set(TEMP, "20")
    await hass.async_block_till_done()
    assert recorder.last == (False, [])

    # No data on either side is no data, even when the other side is false.
    hass.states.async_set(DOOR, "unavailable")
    await hass.async_block_till_done()
    assert recorder.last == (None, [DOOR])

    hass.states.async_set(DOOR, "off")
    hass.states.async_set(TEMP, "unavailable")
    await hass.async_block_till_done()
    assert recorder.last == (None, [TEMP])

    source.async_stop()
    hass.states.async_set(TEMP, "30")
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    assert recorder.last == (None, [TEMP])
