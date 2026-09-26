"""The inputs of condition alerts (spec §4.1, §4.4).

A source watches whatever a condition alert depends on and reports its result
through a callback, together with the inputs that are missing data. The result is
None when there's no data (an input is missing, unavailable, unknown, or won't
parse); otherwise it's True or False, or for a threshold alert, a Reading.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Mapping
import logging
import math
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

from .model import Reading

_LOGGER = logging.getLogger(__name__)

type SourceCallback = Callable[[Any, list[str]], None]

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
    def _report(self, result: Any, missing_inputs: list[str]) -> None:
        if self._on_update is not None:
            self._on_update(result, missing_inputs)


class StateSource(Source):
    """True while an entity is in a target state (the state and alert state kinds).

    The entity being unavailable or unknown means no data, unless that is a
    target state; the entity not existing always means no data.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        target_states: str | Collection[str],
    ) -> None:
        """Initialize the source with one target state, or several."""
        super().__init__(hass)
        self._entity_id = entity_id
        self._target_states = (
            frozenset({target_states})
            if isinstance(target_states, str)
            else frozenset(target_states)
        )
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
            state.state in _NO_DATA_STATES and state.state not in self._target_states
        ):
            self._report(None, [self._entity_id])
        else:
            self._report(state.state in self._target_states, [])


class TemplateSource(Source):
    """True while a template renders true (the template kind, and extra conditions).

    Only clear booleans count as data. An error, an undefined variable, or a result
    of none, unknown, or unavailable means no data; so does anything else that
    isn't recognisably true or false, since reading it as false would hide a
    broken alert.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        template: str,
        description: str,
        variables: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialize the source; description names it in log messages, and
        variables are passed to the template."""
        super().__init__(hass)
        self._template = Template(template, hass)
        self._description = description
        self._variables = dict(variables) if variables else None
        self._info: TrackTemplateResultInfo | None = None
        self._warned = False

    def _async_start(self) -> None:
        self._info = async_track_template_result(
            self.hass,
            [TrackTemplate(self._template, self._variables)],
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
        return missing_entities(self.hass, self._info)


def missing_entities(
    hass: HomeAssistant, info: TrackTemplateResultInfo | None
) -> list[str]:
    """Return the entities tracked templates read that are missing data."""
    if info is None:
        return []
    entities = info.listeners.get("entities", set())
    return sorted(
        entity_id
        for entity_id in entities
        if (state := hass.states.get(entity_id)) is None
        or state.state in _NO_DATA_STATES
    )


def to_number(result: Any) -> float | None:
    """Return a template result as a finite number, or None if it isn't one."""
    if isinstance(result, bool) or result is None or isinstance(result, TemplateError):
        return None
    try:
        number = float(result)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class ThresholdSource(Source):
    """A threshold alert's value and limits, as a Reading (spec §4.1).

    The value is a template (an entity's state or attribute is turned into one);
    so is each limit, which may be a plain number. A value, or a configured limit,
    that isn't a number means no data.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        value: str,
        minimum: str | None,
        maximum: str | None,
        description: str,
        variables: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialize the source; description names it in log messages, and
        variables are passed to the templates."""
        super().__init__(hass)
        self._variables = dict(variables) if variables else None
        self._templates = {
            name: Template(template, hass)
            for name, template in (
                ("value", value),
                ("minimum", minimum),
                ("maximum", maximum),
            )
            if template is not None
        }
        self._description = description
        self._results: dict[Template, Any] = {}
        self._info: TrackTemplateResultInfo | None = None

    def _async_start(self) -> None:
        self._results = {}
        self._info = async_track_template_result(
            self.hass,
            [
                TrackTemplate(template, self._variables)
                for template in self._templates.values()
            ],
            self._async_result,
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
        for update in updates:
            self._results[update.template] = update.result
        numbers = {
            name: to_number(self._results.get(template))
            for name, template in self._templates.items()
        }
        if any(number is None for number in numbers.values()):
            self._report(None, missing_entities(self.hass, self._info))
            return
        self._report(
            Reading(
                value=numbers["value"],  # type: ignore[arg-type]
                minimum=numbers.get("minimum"),
                maximum=numbers.get("maximum"),
            ),
            [],
        )


def value_template(entity_id: str, attribute: str | None) -> str:
    """Return a template reading an entity's state, or one of its attributes."""
    if attribute:
        return f"{{{{ state_attr({entity_id!r}, {attribute!r}) }}}}"
    return f"{{{{ states({entity_id!r}) }}}}"


class SourceSet:
    """Several named sources, reported together once each has reported.

    A condition alert combines its main criterion with the extra condition (and
    an on/off alert its two sides) through this, so that its own rule decides
    what the results mean together.
    """

    def __init__(self, sources: Mapping[str, Source]) -> None:
        """Initialize the set."""
        self._sources = dict(sources)
        self._results: dict[str, tuple[Any, list[str]]] = {}
        self._on_update: Callable[[dict[str, tuple[Any, list[str]]]], None] | None = (
            None
        )

    @callback
    def async_start(
        self, on_update: Callable[[dict[str, tuple[Any, list[str]]]], None]
    ) -> None:
        """Start every source; results are reported once all have reported."""
        self._on_update = on_update
        self._results = {}
        for name, source in self._sources.items():
            source.async_start(self._make_callback(name))

    @callback
    def async_stop(self) -> None:
        """Stop every source."""
        self._on_update = None
        for source in self._sources.values():
            source.async_stop()

    def _make_callback(self, name: str) -> SourceCallback:
        @callback
        def _on_update(result: Any, missing_inputs: list[str]) -> None:
            self._results[name] = (result, missing_inputs)
            if self._on_update is not None and len(self._results) == len(self._sources):
                self._on_update(dict(self._results))

        return _on_update
