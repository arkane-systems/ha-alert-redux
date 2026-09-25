"""An alert's messages and their template context (spec §9.5).

While an alert is firing, its on message, and its display message if it has one, are
rendered and kept up to date as the entities they read change. They are shown as
attributes, which is where the card reads them from (§13.1).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_track_template_result,
)
from homeassistant.helpers.template import Template

from .const import DEFAULT_ON_MESSAGE

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Messages:
    """The rendered messages of a firing alert."""

    message: str
    display_message: str | None = None


def message_context(
    hass: HomeAssistant,
    *,
    name: str,
    entity_id: str,
    priority: str,
    subject_entity: str | None,
    fire_count: int,
    fire_data: Mapping[str, Any] | None,
    reason: str,
    duration_seconds: float = 0,
    end_reason: str | None = None,
) -> dict[str, Any]:
    """Return the variables available to an alert's message templates.

    reason is why the notification is sent (on, reminder, or done); end_reason is
    why the firing ended, for the done message.
    """
    subject_name = name
    if subject_entity is not None and (state := hass.states.get(subject_entity)):
        subject_name = state.name
    return {
        "name": name,
        "entity_id": entity_id,
        "priority": priority,
        "subject_entity_id": subject_entity,
        "subject_entity_name": subject_name,
        "fire_count": fire_count,
        "fire_data": dict(fire_data or {}),
        "reason": reason,
        "end_reason": end_reason,
        "duration": readable_duration(duration_seconds),
        "duration_seconds": duration_seconds,
    }


def readable_duration(seconds: float) -> str:
    """Return a duration as text, e.g. "1 hour 5 minutes"."""
    seconds = int(seconds)
    if seconds < 60:
        return _plural(seconds, "second")
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = [
        _plural(amount, unit)
        for amount, unit in ((days, "day"), (hours, "hour"), (minutes, "minute"))
        if amount
    ]
    return " ".join(parts[:2])


def _plural(amount: int, unit: str) -> str:
    return f"{amount} {unit}" if amount == 1 else f"{amount} {unit}s"


class MessageTracker:
    """Renders a firing alert's messages, re-rendering as the entities they read change.

    A message that fails to render is logged: the on message then falls back to the
    default, and the display message to none, so the card shows the on message.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        message: str | None,
        display_message: str | None,
        variables: dict[str, Any],
        description: str,
        on_update: Callable[[Messages], None],
    ) -> None:
        """Initialize the tracker; description names the alert in log messages."""
        self.hass = hass
        self._message = Template(message or DEFAULT_ON_MESSAGE, hass)
        self._display = Template(display_message, hass) if display_message else None
        self._default = Template(DEFAULT_ON_MESSAGE, hass)
        self._variables = variables
        self._description = description
        self._on_update = on_update
        self._results: dict[Template, str | None] = {}
        self._info: TrackTemplateResultInfo | None = None
        self._starting = False

    @callback
    def async_start(self) -> Messages:
        """Start tracking, and return the first rendering."""
        templates = [self._message] + ([self._display] if self._display else [])
        self._info = async_track_template_result(
            self.hass,
            [TrackTemplate(template, self._variables) for template in templates],
            self._async_result,
            log_fn=self._log,
        )
        self._starting = True
        try:
            self._info.async_refresh()
        finally:
            self._starting = False
        return self.messages

    @callback
    def async_stop(self) -> None:
        """Stop tracking."""
        if self._info is not None:
            self._info.async_remove()
            self._info = None

    @property
    def messages(self) -> Messages:
        """Return the latest rendering."""
        message = self._results.get(self._message)
        if message is None:
            message = str(self._default.async_render(self._variables, parse_result=False))
        display = self._results.get(self._display) if self._display else None
        return Messages(message, display)

    def _log(self, level: int, message: str) -> None:
        _LOGGER.log(level, "%s: %s", self._description, message)

    @callback
    def _async_result(
        self,
        event: Event[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for update in updates:
            self._store(update.template, update.result)
        if not self._starting:
            self._on_update(self.messages)

    def _store(self, template: Template, result: Any) -> None:
        if isinstance(result, TemplateError):
            _LOGGER.warning(
                "%s: message template failed to render: %s", self._description, result
            )
            self._results[template] = None
        else:
            self._results[template] = "" if result is None else str(result)
