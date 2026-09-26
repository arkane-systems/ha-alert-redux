"""Sending an alert's on, reminder, and done notifications (spec §9.4–§9.7).

This is the alert side of notification: which groups an alert uses, and rendering
its messages. Delivery is the notifier module's job.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

from .const import (
    DATA_NOTIFIER,
    DEFAULT_DONE_DISABLED_MESSAGE,
    DEFAULT_DONE_MESSAGE,
    DEFAULT_DONE_NO_DATA_MESSAGE,
    DEFAULT_ON_MESSAGE,
    DEFAULT_REMINDER_MESSAGE,
    DOMAIN,
    EndReason,
)
from .model import Settings
from .notifier import Notification, Notifier

_LOGGER = logging.getLogger(__name__)

REASON_ON = "on"
REASON_REMINDER = "reminder"
REASON_DONE = "done"


def default_message(reason: str, end_reason: str | None = None) -> str:
    """Return the built-in template for a notification."""
    if reason == REASON_ON:
        return DEFAULT_ON_MESSAGE
    if reason == REASON_REMINDER:
        return DEFAULT_REMINDER_MESSAGE
    if end_reason == EndReason.NO_DATA:
        return DEFAULT_DONE_NO_DATA_MESSAGE
    if end_reason == EndReason.DISABLED:
        return DEFAULT_DONE_DISABLED_MESSAGE
    return DEFAULT_DONE_MESSAGE


def lifecycle_key(entity_id: str) -> str:
    """Return the key shared by all of an alert's notifications (spec §9.10)."""
    return f"{DOMAIN}_{entity_id.split('.', 1)[1]}"


def effective_groups(
    settings: Settings, groups: Sequence[str] | None
) -> tuple[str, ...] | None:
    """Return the groups an alert sends to, or None for the fallback.

    An alert without its own list uses the default groups, and with no default
    groups configured, the fallback. An explicitly empty list means nobody.
    """
    if groups is not None:
        return tuple(groups)
    return settings.default_groups or None


def group_names(hass: HomeAssistant, groups: tuple[str, ...] | None) -> list[str]:
    """Return the names of the groups an alert sends to, for its attributes."""
    notifier: Notifier = hass.data[DOMAIN][DATA_NOTIFIER]
    if groups is None:
        return [notifier.fallback_group.name]
    return [group.name for group_id in groups if (group := notifier.group(group_id))]


def render_message(
    hass: HomeAssistant,
    template: str | None,
    default: str,
    variables: Mapping[str, Any],
    description: str,
) -> str:
    """Render a message, falling back to the default if it fails (spec §9.5)."""
    if template:
        try:
            return str(
                Template(template, hass).async_render(variables, parse_result=False)
            )
        except TemplateError as err:
            _LOGGER.warning(
                "%s: message template failed to render: %s", description, err
            )
    return str(Template(default, hass).async_render(variables, parse_result=False))


@callback
def async_send_notification(
    hass: HomeAssistant,
    *,
    entity_id: str,
    title: str,
    groups: tuple[str, ...] | None,
    template: str | None,
    variables: Mapping[str, Any],
) -> None:
    """Render and send one of an alert's notifications.

    groups comes from effective_groups: None sends to the fallback, and an empty
    tuple sends nothing.
    """
    if groups == ():
        return
    reason = variables["reason"]
    message = render_message(
        hass,
        template,
        default_message(reason, variables.get("end_reason")),
        variables,
        f"{entity_id} {reason} message",
    )
    notification = Notification(
        title=title,
        message=message,
        key=lifecycle_key(entity_id),
        variables=variables,
        final=reason == REASON_DONE,
    )
    notifier: Notifier = hass.data[DOMAIN][DATA_NOTIFIER]
    if groups is None:
        notifier.async_send_fallback(notification)
    else:
        notifier.async_send(groups, notification)


@callback
def async_notifications_acknowledged(hass: HomeAssistant, entity_id: str) -> None:
    """Clear an acknowledged alert's notifications, where set to (spec §9.10)."""
    notifier: Notifier = hass.data[DOMAIN][DATA_NOTIFIER]
    notifier.async_acknowledged(lifecycle_key(entity_id))


@callback
def async_clear_notifications(hass: HomeAssistant, entity_id: str) -> None:
    """Clear all of an alert's notifications, e.g. when it's deleted."""
    notifier: Notifier = hass.data[DOMAIN][DATA_NOTIFIER]
    notifier.async_clear(lifecycle_key(entity_id))


@callback
def async_notifications_renamed(hass: HomeAssistant, old: str, new: str) -> None:
    """Follow an alert's entity ID being renamed: its lifecycle key changes."""
    notifier: Notifier = hass.data[DOMAIN][DATA_NOTIFIER]
    notifier.async_rekey(lifecycle_key(old), lifecycle_key(new))
