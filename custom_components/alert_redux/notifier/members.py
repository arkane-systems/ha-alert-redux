"""Delivering a notification to one member, in its kind's way (spec §9.2).

Members that replace notifications (spec §9.10) are sent a tag with each one: the
mobile app's `tag`, or the persistent notification's ID. Clearing removes the
notification with that tag. Members that show buttons (§9.11) get them as mobile
app `actions`, as many as every platform shows.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.template import Template, is_template_string, render_complex

from .model import (
    ActionMember,
    Button,
    EntityMember,
    Member,
    Notification,
    PersistentMember,
)

NOTIFY_DOMAIN = "notify"
SERVICE_SEND_MESSAGE = "send_message"
# The mobile app's message that removes the notification with the data's tag.
CLEAR_NOTIFICATION = "clear_notification"
# Android shows at most three buttons; the ones after that are dropped.
MAX_BUTTONS = 3


class MemberMissing(HomeAssistantError):
    """The member's entity or action doesn't exist (yet)."""


@callback
def member_available(hass: HomeAssistant, member: Member) -> bool:
    """Return whether the member can be sent to now."""
    if isinstance(member, EntityMember):
        state = hass.states.get(member.entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE
    if isinstance(member, ActionMember):
        return hass.services.has_service(NOTIFY_DOMAIN, member.action)
    return True


async def async_deliver(
    hass: HomeAssistant, member: Member, notification: Notification, tag: str
) -> None:
    """Send the notification to the member, raising if it's missing or fails."""
    if not member_available(hass, member):
        raise MemberMissing(f"{member} doesn't exist or is unavailable")
    if isinstance(member, PersistentMember):
        persistent_notification.async_create(
            hass, notification.message, notification.title, notification_id=tag
        )
        return
    if isinstance(member, EntityMember):
        # Home Assistant drops the title itself for entities that can't show one.
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                "entity_id": member.entity_id,
                "message": notification.message,
                "title": notification.title,
            },
            blocking=True,
        )
        return
    assert isinstance(member, ActionMember)
    data: dict[str, Any] = {
        "message": notification.message,
        "title": notification.title,
    }
    extra: dict[str, Any] = {}
    if member.data:
        extra = dict(render_data(hass, member.data, notification.variables))
    # Alert Redux's own keys win over the member's data.
    if member.replaces:
        extra["tag"] = tag
    if member.shows_buttons and notification.buttons and not notification.final:
        extra["actions"] = [
            _mobile_action(button) for button in notification.buttons[:MAX_BUTTONS]
        ]
    if extra:
        data["data"] = extra
    if member.target:
        data["target"] = list(member.target)
    await hass.services.async_call(NOTIFY_DOMAIN, member.action, data, blocking=True)


async def async_clear(hass: HomeAssistant, member: Member, tag: str) -> None:
    """Remove the member's notification with the tag, raising if that fails."""
    if not member_available(hass, member):
        raise MemberMissing(f"{member} doesn't exist or is unavailable")
    if isinstance(member, PersistentMember):
        persistent_notification.async_dismiss(hass, tag)
        return
    assert isinstance(member, ActionMember)
    data: dict[str, Any] = {"message": CLEAR_NOTIFICATION, "data": {"tag": tag}}
    if member.target:
        data["target"] = list(member.target)
    await hass.services.async_call(NOTIFY_DOMAIN, member.action, data, blocking=True)


def _mobile_action(button: Button) -> dict[str, Any]:
    """Return a button as a mobile app notification action."""
    action: dict[str, Any] = {"action": button.id, "title": button.title}
    if button.require_unlock:
        # iOS only runs it from an unlocked device; Android ignores it.
        action["authenticationRequired"] = True
    return action


def render_data(
    hass: HomeAssistant, data: Mapping[str, Any], variables: Mapping[str, Any]
) -> Any:
    """Render a member's data: any string in it can be a template (spec §9.3)."""
    return render_complex(_templates(hass, data), dict(variables))


def _templates(hass: HomeAssistant, value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _templates(hass, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_templates(hass, item) for item in value]
    if isinstance(value, str) and is_template_string(value):
        return Template(value, hass)
    return value
