"""Home Assistant triggers, for event alerts (spec §4.2).

A TriggerWatcher attaches an alert's triggers once Home Assistant has started, as
automations do, and after the startup delay (§15.3), so that entities still loading
don't fire them. Each firing is handed on with its trigger variables made JSON-safe,
so that they can be stored with the alert and survive a restart.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type TriggerCallback = Callable[[dict[str, Any], Context | None], None]


def bus_event_trigger(
    event_type: str, event_data: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Return the trigger configuration of a bus event alert (spec §4.2, F23)."""
    trigger: dict[str, Any] = {"trigger": "event", "event_type": event_type}
    if event_data:
        trigger["event_data"] = event_data
    return [trigger]


def json_safe(value: Any) -> Any:
    """Return trigger variables as plain JSON data.

    Home Assistant objects become their dictionaries (so a template can still read
    trigger.to_state.state), and anything else unknown becomes its text.
    """

    def _default(obj: Any) -> Any:
        if hasattr(obj, "as_dict"):
            return obj.as_dict()
        if isinstance(obj, (date, time, datetime)):
            return obj.isoformat()
        if isinstance(obj, (set, tuple)):
            return list(obj)
        return str(obj)

    return json.loads(json.dumps(value, default=_default))


def is_storable(config: Any) -> bool:
    """Return whether a validated trigger configuration can be stored as JSON.

    A trigger's variables or a templated enabled flag are validated into objects
    that can't be stored in a config subentry.
    """
    try:
        json.dumps(config)
    except TypeError:
        return False
    return True


async def async_validate_triggers(
    hass: HomeAssistant, config: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate triggers as automations do; raises vol.Invalid or HomeAssistantError."""
    return await async_validate_trigger_config(hass, cv.TRIGGER_SCHEMA(config))


class TriggerWatcher:
    """Watches an alert's triggers, handing each firing to a callback."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: list[dict[str, Any]],
        name: str,
        on_trigger: TriggerCallback,
        on_failed: Callable[[], None],
    ) -> None:
        """Initialize the watcher; name identifies the alert in log messages."""
        self.hass = hass
        self._config = config
        self._name = name
        self._on_trigger = on_trigger
        self._on_failed = on_failed
        self._unsub_start: CALLBACK_TYPE | None = None
        self._unsub_delay: CALLBACK_TYPE | None = None
        self._unsub_triggers: CALLBACK_TYPE | None = None
        # Counts starts and stops, so that an attach that finishes after a stop (or
        # a restart) is undone rather than kept.
        self._generation = 0

    @callback
    def async_start(self, not_before: datetime | None) -> None:
        """Attach the triggers once HA has started, and not before not_before."""
        self.async_stop()

        @callback
        def _started(_hass: HomeAssistant) -> None:
            self._unsub_start = None
            if not_before is not None and dt_util.utcnow() < not_before:
                self._unsub_delay = async_track_point_in_utc_time(
                    self.hass, _delay_over, not_before
                )
            else:
                self._async_attach()

        @callback
        def _delay_over(_now: datetime) -> None:
            self._unsub_delay = None
            self._async_attach()

        self._unsub_start = async_at_started(self.hass, _started)

    @callback
    def _async_attach(self) -> None:
        self.hass.async_create_task(
            self._async_attach_triggers(self._generation),
            f"{DOMAIN} {self._name} triggers",
        )

    async def _async_attach_triggers(self, generation: int) -> None:
        try:
            config = await async_validate_triggers(self.hass, self._config)
        except (vol.Invalid, HomeAssistantError) as err:
            if generation == self._generation:
                _LOGGER.error("%s: invalid trigger: %s", self._name, err)
                self._on_failed()
            return
        unsub = await async_initialize_triggers(
            self.hass, config, self._async_triggered, DOMAIN, self._name, self._log
        )
        if generation != self._generation:
            # Stopped, or restarted, while attaching.
            if unsub is not None:
                unsub()
            return
        if unsub is None:
            self._on_failed()
            return
        self._unsub_triggers = unsub

    @callback
    def async_stop(self) -> None:
        """Detach the triggers, or stop waiting to attach them."""
        self._generation += 1
        for unsub in (self._unsub_start, self._unsub_delay, self._unsub_triggers):
            if unsub is not None:
                unsub()
        self._unsub_start = self._unsub_delay = self._unsub_triggers = None

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        _LOGGER.log(level, "%s: %s", self._name, message, **kwargs)

    @callback
    def _async_triggered(
        self, run_variables: dict[str, Any], context: Context | None = None
    ) -> None:
        self._on_trigger(json_safe(run_variables.get("trigger", {})), context)
