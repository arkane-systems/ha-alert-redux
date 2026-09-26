"""Describe Alert Redux events in the logbook (spec §11.4).

The logbook already shows every state change of an alert, with its translated
state and the user who caused it. So only the events that say more than a state
change can get a row of their own; describing the others (fired, acked, unacked,
enabled, ended) would show each of those changes twice. A describer can't drop a
row, so the choice is made by which event types are registered.

The user comes from the event's context, as for the state rows. Messages are
English, as the cards are (spec §13.1).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LazyEventPartialState,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DISABLED_UNTIL,
    ATTR_MISSING_INPUTS,
    ATTR_NAME,
    ATTR_SNOOZED_UNTIL,
    ATTR_SUPERSEDED_BY,
    DOMAIN,
    EVENT_CREATED,
    EVENT_DATA_RESTORED,
    EVENT_DELETED,
    EVENT_DISABLED,
    EVENT_NO_DATA,
    EVENT_SNOOZE_EXPIRED,
    EVENT_SNOOZED,
    EVENT_SUPERSEDED,
)

type Describe = Callable[[LazyEventPartialState], dict[str, Any]]


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Describe], None],
) -> None:
    """Describe the events that add something to the alerts' state rows."""

    def describer(message: Callable[[dict[str, Any]], str]) -> Describe:
        @callback
        def describe(event: LazyEventPartialState) -> dict[str, Any]:
            data = event.data
            return {
                LOGBOOK_ENTRY_NAME: data.get(ATTR_NAME),
                LOGBOOK_ENTRY_ENTITY_ID: data.get(ATTR_ENTITY_ID),
                LOGBOOK_ENTRY_MESSAGE: message(data),
            }

        return describe

    def superseded(data: dict[str, Any]) -> str:
        return f"superseded by {_names(hass, data.get(ATTR_SUPERSEDED_BY))}"

    messages: dict[str, Callable[[dict[str, Any]], str]] = {
        EVENT_SNOOZED: lambda data: (
            f"snoozed until {_when(data.get(ATTR_SNOOZED_UNTIL))}"
        ),
        EVENT_SNOOZE_EXPIRED: lambda data: "snooze ran out",
        EVENT_DISABLED: _disabled,
        EVENT_SUPERSEDED: superseded,
        EVENT_NO_DATA: lambda data: (
            f"lost data from {_list(data.get(ATTR_MISSING_INPUTS))}"
        ),
        EVENT_DATA_RESTORED: lambda data: "data restored",
        EVENT_CREATED: lambda data: "created",
        EVENT_DELETED: lambda data: "deleted",
    }
    for event_type, message in messages.items():
        async_describe_event(DOMAIN, event_type, describer(message))


def _disabled(data: dict[str, Any]) -> str:
    if (until := data.get(ATTR_DISABLED_UNTIL)) is None:
        return "disabled"
    return f"suspended until {_when(until)}"


def _when(value: datetime | str | None) -> str:
    """Return a time in the local time zone, with the date unless it's today.

    Event data read back from the database has its times as strings.
    """
    if isinstance(value, str):
        value = dt_util.parse_datetime(value)
    if value is None:
        return "unknown"
    local = dt_util.as_local(value)
    if local.date() == dt_util.now().date():
        return local.strftime("%H:%M")
    return local.strftime("%a %d %b %H:%M")


def _list(items: list[str] | None) -> str:
    return ", ".join(items) if items else "unknown inputs"


def _names(hass: HomeAssistant, entity_ids: list[str] | None) -> str:
    """Return the alerts' names, falling back to their entity IDs."""
    names = []
    for entity_id in entity_ids or []:
        state = hass.states.get(entity_id)
        name = state.attributes.get(ATTR_FRIENDLY_NAME) if state else None
        names.append(name or entity_id)
    return ", ".join(names) if names else "another alert"
