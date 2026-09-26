"""Sending an alert's on, reminder, and done notifications (spec §9.4–§9.7).

This is the alert side of notification: which groups an alert uses, and rendering
its messages. Delivery is the notifier module's job.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util

from .const import (
    DATA_ENTITIES,
    DATA_NOTIFIER,
    DEFAULT_DONE_DISABLED_MESSAGE,
    DEFAULT_DONE_MESSAGE,
    DEFAULT_DONE_NO_DATA_MESSAGE,
    DEFAULT_ON_MESSAGE,
    DEFAULT_REMINDER_MESSAGE,
    DOMAIN,
    QUIET_SUMMARY_HEADING,
    QUIET_SUMMARY_TITLE,
    THROTTLE_ENDS_MARKER,
    AlertState,
    EndReason,
)
from .messages import readable_duration
from .model import Settings, ThrottleSummary
from .notifier import Button, Notification, Notifier

if TYPE_CHECKING:
    from .entity import AlertEntity

_LOGGER = logging.getLogger(__name__)

REASON_ON = "on"
REASON_REMINDER = "reminder"
REASON_DONE = "done"
# The summary sent when throttling ends (spec §9.8).
REASON_THROTTLE_SUMMARY = "throttle_summary"


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


def throttle_summary_message(
    summary: ThrottleSummary, now: datetime, *, firing: bool
) -> str:
    """Return the summary of what was held while an alert was throttled (§9.8).

    E.g. "[Throttling ends] Fired 7× while throttled, most recently 12 minutes
    ago; stopped firing 3 minutes ago after 40 seconds."
    """
    parts: list[str] = []
    if summary.held_fires and summary.last_held is not None:
        parts.append(
            f"Fired {summary.held_fires}× while throttled, most recently "
            f"{_ago(summary.last_held, now)}"
        )
    if firing:
        parts.append("still firing")
    elif summary.ended is not None:
        ended = f"stopped firing {_ago(summary.ended, now)}"
        if summary.duration_seconds is not None:
            ended += f" after {readable_duration(summary.duration_seconds)}"
        if summary.end_reason == EndReason.NO_DATA:
            ended += " (lost its data)"
        elif summary.end_reason == EndReason.DISABLED:
            ended += " (disabled)"
        parts.append(ended)
    text = "; ".join(parts)
    return f"{THROTTLE_ENDS_MARKER} {text[:1].upper()}{text[1:]}."


def _ago(when: datetime, now: datetime) -> str:
    """Return how long ago something was, e.g. "12 minutes ago"; "just now"."""
    seconds = (now - when).total_seconds()
    if seconds < 1:
        return "just now"
    return f"{readable_duration(seconds)} ago"


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
    groups: tuple[str, ...] | None,
    **details: Any,
) -> None:
    """Render and send one of an alert's notifications (see build_notification).

    groups comes from effective_groups: None sends to the fallback, and an empty
    tuple sends nothing.
    """
    if groups == ():
        return
    notification = build_notification(hass, **details)
    notifier: Notifier = hass.data[DOMAIN][DATA_NOTIFIER]
    if groups is None:
        notifier.async_send_fallback(notification)
    else:
        notifier.async_send(groups, notification)


def build_notification(
    hass: HomeAssistant,
    *,
    entity_id: str,
    title: str,
    template: str | None,
    variables: Mapping[str, Any],
    buttons: tuple[Button, ...] = (),
    prefix: str | None = None,
    message: str | None = None,
    final: bool | None = None,
    urgency: int = 0,
) -> Notification:
    """Render one of an alert's notifications.

    A final notification (by default, the done notification) carries no
    buttons (spec §9.11). A message given ready-made isn't rendered; a prefix
    goes in front of the message. The urgency is the alert's priority's, for
    quiet hours (§9.9).
    """
    reason = variables["reason"]
    if final is None:
        final = reason == REASON_DONE
    if message is None:
        message = render_message(
            hass,
            template,
            default_message(reason, variables.get("end_reason")),
            variables,
            f"{entity_id} {reason} message",
        )
    if prefix:
        message = f"{prefix} {message}"
    return Notification(
        title=title,
        message=message,
        key=lifecycle_key(entity_id),
        variables=variables,
        buttons=() if final else buttons,
        final=final,
        urgency=urgency,
    )


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


@dataclass(slots=True)
class _Ended:
    """What an alert's firings that ended during quiet hours add up to."""

    name: str
    started: datetime | None
    stopped: datetime | None
    seconds: float = 0
    times: int = 0


@callback
def async_quiet_hours_ended(
    hass: HomeAssistant, group_id: str, held: dict[str, list[Notification]]
) -> list[Notification]:
    """Say what a group gets when its quiet hours end (spec §9.9).

    An alert still firing and unacknowledged gets one reminder, with the real
    firing duration; one acknowledged in the meantime gets nothing more. The
    firings that ended are listed in one summary: each alert with when it first
    started, when it last stopped, how long it fired, and how many times.
    Throttling summaries held for ended firings are listed as they are.
    """
    entities: dict[str, AlertEntity] = hass.data[DOMAIN][DATA_ENTITIES]
    by_key = {
        lifecycle_key(entity.entity_id): entity
        for entity in entities.values()
        if entity.hass is not None
    }
    notifications: list[Notification] = []
    ended: dict[str, _Ended] = {}
    lines: list[str] = []
    for key, notifications_held in held.items():
        entity = by_key.get(key)
        if (
            entity is not None
            and entity.state == AlertState.ACTIVE
            and (reminder := entity.quiet_hours_reminder()) is not None
        ):
            notifications.append(reminder)
        for notification in notifications_held:
            variables = notification.variables
            if variables.get("reason") == REASON_DONE:
                row = ended.setdefault(
                    key, _Ended(variables.get("name") or notification.title, None, None)
                )
                started = _parse_time(variables.get("started"))
                stopped = _parse_time(variables.get("ended"))
                if started and (row.started is None or started < row.started):
                    row.started = started
                if stopped and (row.stopped is None or stopped > row.stopped):
                    row.stopped = stopped
                row.seconds += variables.get("duration_seconds") or 0
                row.times += 1
            elif notification.final:
                lines.append(f"{notification.title}: {notification.message}")
    now = dt_util.utcnow()
    lines = [_summary_line(row, now) for row in ended.values()] + lines
    if lines:
        notifications.append(
            Notification(
                title=QUIET_SUMMARY_TITLE,
                message="\n".join([QUIET_SUMMARY_HEADING, *lines]),
                key=f"{DOMAIN}_quiet_hours_{group_id}",
                final=True,
            )
        )
    return notifications


def _parse_time(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


def _summary_line(row: _Ended, now: datetime) -> str:
    """Return a summary's line for an alert, e.g. "Back Door Open: started
    01:12, stopped 01:20, fired for 8 minutes"."""
    duration = readable_duration(row.seconds)
    if row.times == 1:
        return (
            f"{row.name}: started {_clock(row.started, now)}, stopped "
            f"{_clock(row.stopped, now)}, fired for {duration}."
        )
    return (
        f"{row.name}: first started {_clock(row.started, now)}, last stopped "
        f"{_clock(row.stopped, now)}, fired {row.times} times for {duration} in all."
    )


def _clock(when: datetime | None, now: datetime) -> str:
    """Return a time as the local clock, with the day if it isn't today."""
    if when is None:
        return "at an unknown time"
    local = dt_util.as_local(when)
    if local.date() != dt_util.as_local(now).date():
        return local.strftime("%a %H:%M")
    return local.strftime("%H:%M")
