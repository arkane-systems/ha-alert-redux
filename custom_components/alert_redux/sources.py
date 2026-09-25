"""The inputs of condition alerts (spec §4.1, §4.4).

A source watches whatever a condition alert depends on and reports a tri-state
result through a callback: True or False, or None when it has no data (an input is
missing, unavailable, unknown, or won't parse), together with the inputs that are
missing data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.template import Template

_LOGGER = logging.getLogger(__name__)

type SourceCallback = Callable[[bool | None, list[str]], None]

_NO_DATA_STATES = frozenset({STATE_UNAVAILABLE, STATE_UNKNOWN})
_TRUE = frozenset({"true", "on", "yes", "1"})
_FALSE = frozenset({"false", "off", "no", "0"})
_NO_DATA_RESULTS = frozenset({STATE_UNAVAILABLE, STATE_UNKNOWN, "none", ""})


def template_truth(result: Any) -> bool | None:
    """Judge a template's result: True, False, or None for no data (spec §4.1).

    Only clear booleans count: true/on/yes/1 and false/off/no/0 (in any case), real
    booleans, and numbers. Anything else is no data.
    """
    if result is None or isinstance(result, TemplateError):
        return None
    if isinstance(result, bool):
        return result
    if isinstance(result, (int, float)):
        return result != 0
    text = str(result).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return None


def is_unexpected_result(result: Any) -> bool:
    """Return whether a result is neither a boolean nor a recognised no-data value.

    Such a result usually means a mistake in the template, so it's worth a warning.
    """
    if result is None or isinstance(result, TemplateError):
        return False
    return template_truth(result) is None and (
        str(result).strip().lower() not in _NO_DATA_RESULTS
    )


class Source(ABC):
    """A condition alert's input, reporting through a callback once started."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the source."""
        self.hass = hass
        self._on_update: SourceCallback | None = None

    @callback
    def async_start(self, on_update: SourceCallback) -> None:
        """Start watching; the first result may be reported straight away."""
        self._on_update = on_update
        self._async_start()

    @callback
    def async_stop(self) -> None:
        """Stop watching; nothing more is reported."""
        self._on_update = None
        self._async_stop()

    @abstractmethod
    def _async_start(self) -> None: ...

    @abstractmethod
    def _async_stop(self) -> None: ...

    @callback
    def _report(self, result: bool | None, missing_inputs: list[str]) -> None:
        if self._on_update is not None:
            self._on_update(result, missing_inputs)


class StateSource(Source):
    """True while an entity is in a target state (the state kind).

    The entity being unavailable or unknown means no data, unless that is the
    target state; the entity not existing always means no data.
    """

    def __init__(self, hass: HomeAssistant, entity_id: str, target_state: str) -> None:
        """Initialize the source."""
        super().__init__(hass)
        self._entity_id = entity_id
        self._target_state = target_state
        self._unsub: CALLBACK_TYPE | None = None

    def _async_start(self) -> None:
        self._unsub = async_track_state_change_event(
            self.hass, self._entity_id, self._async_state_changed
        )
        self._async_evaluate()

    def _async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        self._async_evaluate()

    @callback
    def _async_evaluate(self) -> None:
        state = self.hass.states.get(self._entity_id)
        if state is None or (
            state.state in _NO_DATA_STATES and state.state != self._target_state
        ):
            self._report(None, [self._entity_id])
        else:
            self._report(state.state == self._target_state, [])


class TemplateSource(Source):
    """True while a template renders true (the template kind, and extra conditions).

    Only clear booleans count as data. An error, an undefined variable, or a result
    of none, unknown, or unavailable means no data; so does anything else that
    isn't recognisably true or false, since reading it as false would hide a
    broken alert.
    """

    def __init__(self, hass: HomeAssistant, template: str, description: str) -> None:
        """Initialize the source; description names it in log messages."""
        super().__init__(hass)
        self._template = Template(template, hass)
        self._description = description
        self._info: TrackTemplateResultInfo | None = None
        self._warned = False

    def _async_start(self) -> None:
        self._info = async_track_template_result(
            self.hass,
            [TrackTemplate(self._template, None)],
            self._async_result,
            strict=True,
            log_fn=self._log,
        )
        self._info.async_refresh()

    def _async_stop(self) -> None:
        if self._info is not None:
            self._info.async_remove()
            self._info = None

    def _log(self, level: int, message: str) -> None:
        _LOGGER.log(level, "%s: %s", self._description, message)

    @callback
    def _async_result(
        self,
        event: Event[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        result = updates[-1].result
        if isinstance(result, TemplateError):
            self._report(None, self._missing_inputs())
            return
        value = self._truth(result)
        self._report(value, [] if value is not None else self._missing_inputs())

    def _truth(self, result: Any) -> bool | None:
        value = template_truth(result)
        if value is None and is_unexpected_result(result) and not self._warned:
            self._warned = True
            _LOGGER.warning(
                "%s: template result %r isn't true or false; treating it as no data",
                self._description,
                result,
            )
        return value

    def _missing_inputs(self) -> list[str]:
        """Return the entities the template read that are missing data."""
        if self._info is None:
            return []
        entities = self._info.listeners.get("entities", set())
        return sorted(
            entity_id
            for entity_id in entities
            if (state := self.hass.states.get(entity_id)) is None
            or state.state in _NO_DATA_STATES
        )


class AndSource(Source):
    """Both sources must be true: a condition alert's extra condition (spec §4.1).

    Either source having no data means no data, even if the other is false: the
    alert depends on both (spec §4.4). Nothing is reported until both have
    reported.
    """

    def __init__(self, hass: HomeAssistant, first: Source, second: Source) -> None:
        """Initialize the source."""
        super().__init__(hass)
        self._sources = (first, second)
        self._results: list[tuple[bool | None, list[str]] | None] = [None, None]

    def _async_start(self) -> None:
        self._results = [None, None]
        for index, source in enumerate(self._sources):
            source.async_start(self._make_callback(index))

    def _async_stop(self) -> None:
        for source in self._sources:
            source.async_stop()

    def _make_callback(self, index: int) -> SourceCallback:
        @callback
        def _on_update(result: bool | None, missing_inputs: list[str]) -> None:
            self._results[index] = (result, missing_inputs)
            self._async_combine()

        return _on_update

    @callback
    def _async_combine(self) -> None:
        if any(result is None for result in self._results):
            return
        results = [result for result in self._results if result is not None]
        if any(value is None for value, _ in results):
            missing = sorted({entity for _, inputs in results for entity in inputs})
            self._report(None, missing)
        else:
            self._report(all(value for value, _ in results), [])
