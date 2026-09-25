"""Notifications, notifier groups, and their members (spec §9.2, §9.3).

Groups are plain definitions, built from whatever stores them (for Alert Redux, config
subentries) through from_dict; nothing here knows about alerts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# Group definition keys.
KEY_LOUD = "loud"
KEY_ENTITIES = "entities"
KEY_ACTIONS = "actions"
KEY_PERSISTENT = "persistent"
# Legacy action member keys.
KEY_ACTION = "action"
KEY_DATA = "data"
KEY_TARGET = "target"


@dataclass(frozen=True, slots=True)
class Notification:
    """One notification, to be sent to one or more groups.

    The key identifies the notification's lifecycle, so that later notifications can
    replace or clear it; the variables are the context for members' data templates.
    """

    title: str
    message: str
    key: str
    variables: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EntityMember:
    """A notify entity, sent to with notify.send_message."""

    entity_id: str

    def __str__(self) -> str:
        """Return the member as named in logs and issues."""
        return self.entity_id


@dataclass(frozen=True, slots=True)
class ActionMember:
    """A legacy notify.<action>, which can take data and a target."""

    action: str
    data: Mapping[str, Any] | None = None
    target: tuple[str, ...] = ()

    def __str__(self) -> str:
        """Return the member as named in logs and issues."""
        return f"notify.{self.action}"


@dataclass(frozen=True, slots=True)
class PersistentMember:
    """A persistent notification."""

    def __str__(self) -> str:
        """Return the member as named in logs and issues."""
        return "persistent_notification"


type Member = EntityMember | ActionMember | PersistentMember


@dataclass(frozen=True, slots=True)
class GroupConfig:
    """A named set of members, flagged loud or quiet."""

    id: str
    name: str
    members: tuple[Member, ...]
    loud: bool = False

    @classmethod
    def from_dict(
        cls, group_id: str, name: str, data: Mapping[str, Any]
    ) -> GroupConfig:
        """Build a group from its stored definition."""
        members: list[Member] = [
            EntityMember(entity_id) for entity_id in data.get(KEY_ENTITIES, [])
        ]
        members += [
            ActionMember(
                action=_action_name(action[KEY_ACTION]),
                data=action.get(KEY_DATA) or None,
                target=parse_target(action.get(KEY_TARGET)),
            )
            for action in data.get(KEY_ACTIONS, [])
        ]
        if data.get(KEY_PERSISTENT):
            members.append(PersistentMember())
        return cls(group_id, name, tuple(members), bool(data.get(KEY_LOUD, False)))


def _action_name(action: str) -> str:
    """Return a legacy action's name, without any "notify." in front of it."""
    return action.strip().removeprefix("notify.")


def parse_target(value: Any) -> tuple[str, ...]:
    """Return a target from its stored form: a list, or comma-separated text."""
    if not value:
        return ()
    items = value if isinstance(value, list) else str(value).split(",")
    return tuple(item for item in (str(item).strip() for item in items) if item)


# Serialization for the retry queue's store.
KEY_KIND = "kind"
KIND_ENTITY = "entity"
KIND_ACTION = "action"
KIND_PERSISTENT = "persistent"


def member_to_dict(member: Member) -> dict[str, Any]:
    """Return a member in storable form."""
    if isinstance(member, EntityMember):
        return {KEY_KIND: KIND_ENTITY, "entity_id": member.entity_id}
    if isinstance(member, ActionMember):
        return {
            KEY_KIND: KIND_ACTION,
            KEY_ACTION: member.action,
            KEY_DATA: dict(member.data) if member.data else None,
            KEY_TARGET: list(member.target),
        }
    return {KEY_KIND: KIND_PERSISTENT}


def member_from_dict(data: Mapping[str, Any]) -> Member:
    """Return a member from its stored form."""
    if data[KEY_KIND] == KIND_ENTITY:
        return EntityMember(data["entity_id"])
    if data[KEY_KIND] == KIND_ACTION:
        return ActionMember(
            data[KEY_ACTION], data.get(KEY_DATA), tuple(data.get(KEY_TARGET) or ())
        )
    return PersistentMember()


def notification_to_dict(notification: Notification) -> dict[str, Any]:
    """Return a notification in storable form."""
    return {
        "title": notification.title,
        "message": notification.message,
        "key": notification.key,
        "variables": dict(notification.variables),
    }


def notification_from_dict(data: Mapping[str, Any]) -> Notification:
    """Return a notification from its stored form."""
    return Notification(
        data["title"], data["message"], data["key"], data.get("variables") or {}
    )
