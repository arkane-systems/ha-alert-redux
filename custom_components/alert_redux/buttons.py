"""Notification buttons: building an alert's, and handling taps (spec §9.11).

Each button is sent with an action ID, ALERT_REDUX_<alert's unique ID>_<button>.
The unique ID survives renames. <button> is ACK, SNOOZE, or, for a custom
button, B and a hash of its label and action, so an edited or removed button's
old taps match nothing rather than another button. Tapping a button makes the
mobile app fire mobile_app_notification_action with the ID; Alert Redux matches
it and runs only what's configured for that button. Nothing from the event
itself is executed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback

from .const import CONF_ACTION, CONF_LABEL, CONF_REQUIRE_UNLOCK, DATA_ENTITIES, DOMAIN
from .messages import readable_duration
from .notifier import Button

if TYPE_CHECKING:
    from .entity import AlertEntity

_LOGGER = logging.getLogger(__name__)

EVENT_NOTIFICATION_ACTION = "mobile_app_notification_action"
ACTION_PREFIX = "ALERT_REDUX_"
BUTTON_ACK = "ACK"
BUTTON_SNOOZE = "SNOOZE"
CUSTOM_PREFIX = "B"


def custom_button_key(button: Mapping[str, Any]) -> str:
    """Return a custom button's part of its action ID."""
    identity = json.dumps(
        [button.get(CONF_LABEL), button.get(CONF_ACTION)],
        sort_keys=True,
        default=str,
    )
    return CUSTOM_PREFIX + hashlib.sha256(identity.encode()).hexdigest()[:8]


def alert_buttons(
    unique_id: str,
    custom: Sequence[Mapping[str, Any]],
    *,
    acknowledgeable: bool,
    snooze: timedelta,
) -> tuple[Button, ...]:
    """Return an alert's buttons: its own, then Acknowledge and Snooze.

    The built-in buttons aren't offered on unacknowledgeable alerts.
    """
    buttons = [
        Button(
            _action_id(unique_id, custom_button_key(button)),
            str(button[CONF_LABEL]),
            bool(button.get(CONF_REQUIRE_UNLOCK, False)),
        )
        for button in custom
    ]
    if acknowledgeable:
        buttons += [
            Button(_action_id(unique_id, BUTTON_ACK), "Acknowledge"),
            Button(
                _action_id(unique_id, BUTTON_SNOOZE),
                f"Snooze {readable_duration(snooze.total_seconds())}",
            ),
        ]
    return tuple(buttons)


def _action_id(unique_id: str, key: str) -> str:
    return f"{ACTION_PREFIX}{unique_id}_{key}"


def parse_action_id(action: Any) -> tuple[str, str] | None:
    """Return the alert's unique ID and the button from an action ID, if it's ours."""
    if not isinstance(action, str) or not action.startswith(ACTION_PREFIX):
        return None
    unique_id, sep, key = action.removeprefix(ACTION_PREFIX).rpartition("_")
    if not sep or not unique_id or not key:
        return None
    return unique_id, key


@callback
def async_setup_buttons(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Handle taps on alerts' notification buttons; return the unsubscriber."""

    @callback
    def _async_tapped(event: Event) -> None:
        if (parsed := parse_action_id(event.data.get("action"))) is None:
            return
        unique_id, key = parsed
        entities: dict[str, AlertEntity] = hass.data[DOMAIN][DATA_ENTITIES]
        if (entity := entities.get(unique_id)) is None or entity.hass is None:
            _LOGGER.info(
                "Notification button %s tapped for an alert that no longer exists",
                event.data["action"],
            )
            return
        hass.async_create_task(
            entity.async_button_tapped(key, event.context),
            f"{DOMAIN} button {key}",
        )

    return hass.bus.async_listen(EVENT_NOTIFICATION_ACTION, _async_tapped)
