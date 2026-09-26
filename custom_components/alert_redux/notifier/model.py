"""Notifications, notifier groups, and their members (spec §9.2, §9.3).

Groups are plain definitions, built from whatever stores them (for Alert Redux, config
subentries) through from_dict; nothing here knows about alerts.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# Group definition keys.
KEY_LOUD = "loud"
KEY_ENTITIES = "entities"
KEY_ACTIONS = "actions"
KEY_PERSISTENT = "persistent"
KEY_PERSISTENT_CLEAR_ON_ACK = "persistent_clear_on_ack"
KEY_PERSISTENT_CLEAR_WHEN_ENDED = "persistent_clear_when_ended"
# Quiet hours (spec §9.9): a loud group's own entity, threshold, and behaviour.
KEY_QUIET_ENTITY = "quiet_entity"
KEY_QUIET_THRESHOLD = "quiet_threshold"
KEY_QUIET_BEHAVIOUR = "quiet_behaviour"
# Legacy action member keys.
KEY_ACTION = "action"
KEY_DATA = "data"
KEY_TARGET = "target"
KEY_MOBILE = "mobile"
KEY_KEEP_ON_ACK = "keep_on_ack"
KEY_CLEAR_WHEN_ENDED = "clear_when_ended"
KEY_QUIET_DATA = "quiet_data"

# Legacy actions whose name starts with this are mobile apps.
MOBILE_APP_PREFIX = "mobile_app_"


class MobileFeatures(StrEnum):
    """Which mobile app features a legacy action member uses (spec §9.10, §9.11)."""

    # Replacing, clearing, and buttons for notify.mobile_app_* actions; none for
    # others.
    AUTOMATIC = "automatic"
    ALL = "all"
    NO_BUTTONS = "no_buttons"
    NONE = "none"


class QuietBehaviour(StrEnum):
    """What a loud group does with notifications during quiet hours (§9.9)."""

    # Hold them until quiet hours end.
    HOLD = "hold"
    # Send them with each member's quiet-hours data; members without hold.
    SOFTEN = "soften"


@dataclass(frozen=True, slots=True)
class Button:
    """A button on a notification: its action ID is sent back when it's tapped.

    require_unlock asks for the device to be unlocked before the tap counts.
    """

    id: str
    title: str
    require_unlock: bool = False


@dataclass(frozen=True, slots=True)
class Notification:
    """One notification, to be sent to one or more groups.

    The key identifies the notification's lifecycle, so that later notifications can
    replace or clear it; the variables are the context for members' data templates.
    A final notification is the last of its lifecycle (e.g. "resolved"): members can
    be set to clear the earlier ones instead of showing it, and it has no buttons.
    Quiet hours affect notifications whose urgency is below a threshold (§9.9).
    """

    title: str
    message: str
    key: str
    variables: Mapping[str, Any] = field(default_factory=dict)
    buttons: tuple[Button, ...] = ()
    final: bool = False
    urgency: int = 0


@dataclass(frozen=True, slots=True)
class EntityMember:
    """A notify entity, sent to with notify.send_message."""

    entity_id: str

    # Each notification arrives as a separate message.
    replaces = False
    shows_buttons = False
    clear_on_ack = False
    clear_when_ended = False

    def __str__(self) -> str:
        """Return the member as named in logs and issues."""
        return self.entity_id

    @property
    def destination(self) -> tuple[str, ...]:
        """Return where the member sends to, whatever its settings."""
        return (KIND_ENTITY, self.entity_id)


@dataclass(frozen=True, slots=True)
class ActionMember:
    """A legacy notify.<action>, which can take data and a target."""

    action: str
    data: Mapping[str, Any] | None = None
    target: tuple[str, ...] = ()
    mobile: MobileFeatures = MobileFeatures.AUTOMATIC
    clear_on_ack: bool = True
    clear_when_ended: bool = False
    # Used instead of data when a softening group is in quiet hours (§9.9).
    quiet_data: Mapping[str, Any] | None = None

    def __str__(self) -> str:
        """Return the member as named in logs and issues."""
        return f"notify.{self.action}"

    @property
    def destination(self) -> tuple[str, ...]:
        """Return where the member sends to, whatever its settings."""
        return (KIND_ACTION, self.action, *self.target)

    @property
    def replaces(self) -> bool:
        """Return whether notifications carry a tag, to replace and clear them."""
        if self.mobile is MobileFeatures.AUTOMATIC:
            return self.action.startswith(MOBILE_APP_PREFIX)
        return self.mobile is not MobileFeatures.NONE

    @property
    def shows_buttons(self) -> bool:
        """Return whether notifications carry buttons."""
        if self.mobile is MobileFeatures.AUTOMATIC:
            return self.action.startswith(MOBILE_APP_PREFIX)
        return self.mobile is MobileFeatures.ALL


@dataclass(frozen=True, slots=True)
class PersistentMember:
    """A persistent notification, whose ID is the notification's key."""

    clear_on_ack: bool = True
    clear_when_ended: bool = False

    replaces = True
    shows_buttons = False

    def __str__(self) -> str:
        """Return the member as named in logs and issues."""
        return "persistent_notification"

    @property
    def destination(self) -> tuple[str, ...]:
        """Return where the member sends to, whatever its settings."""
        return (KIND_PERSISTENT,)


type Member = EntityMember | ActionMember | PersistentMember


def can_soften(member: Member) -> bool:
    """Return whether a member can be sent softened notifications (§9.9)."""
    return isinstance(member, ActionMember) and bool(member.quiet_data)


@dataclass(frozen=True, slots=True)
class GroupConfig:
    """A named set of members, flagged loud or quiet.

    A loud group can have its own quiet-hours entity and threshold (an urgency),
    instead of the global ones, and holds or softens during quiet hours.
    """

    id: str
    name: str
    members: tuple[Member, ...]
    loud: bool = False
    quiet_entity: str | None = None
    quiet_threshold: int | None = None
    quiet_behaviour: QuietBehaviour = QuietBehaviour.HOLD

    def holding_members(self) -> tuple[Member, ...]:
        """Return the members that hold notifications during quiet hours: all of
        them, unless the group softens, when those that can soften don't."""
        if self.quiet_behaviour is QuietBehaviour.SOFTEN:
            return tuple(m for m in self.members if not can_soften(m))
        return self.members

    @classmethod
    def from_dict(
        cls,
        group_id: str,
        name: str,
        data: Mapping[str, Any],
        urgency: Callable[[str], int] | None = None,
    ) -> GroupConfig:
        """Build a group from its stored definition.

        urgency turns the stored quiet-hours threshold into an urgency; without
        it, the threshold is stored as one.
        """
        members: list[Member] = [
            EntityMember(entity_id) for entity_id in data.get(KEY_ENTITIES, [])
        ]
        members += [
            ActionMember(
                action=_action_name(action[KEY_ACTION]),
                data=action.get(KEY_DATA) or None,
                target=parse_target(action.get(KEY_TARGET)),
                mobile=MobileFeatures(
                    action.get(KEY_MOBILE) or MobileFeatures.AUTOMATIC
                ),
                clear_on_ack=not action.get(KEY_KEEP_ON_ACK, False),
                clear_when_ended=bool(action.get(KEY_CLEAR_WHEN_ENDED, False)),
                quiet_data=action.get(KEY_QUIET_DATA) or None,
            )
            for action in data.get(KEY_ACTIONS, [])
        ]
        if data.get(KEY_PERSISTENT):
            members.append(
                PersistentMember(
                    clear_on_ack=bool(data.get(KEY_PERSISTENT_CLEAR_ON_ACK, True)),
                    clear_when_ended=bool(
                        data.get(KEY_PERSISTENT_CLEAR_WHEN_ENDED, False)
                    ),
                )
            )
        threshold = data.get(KEY_QUIET_THRESHOLD)
        if threshold is not None:
            threshold = urgency(threshold) if urgency else int(threshold)
        return cls(
            group_id,
            name,
            tuple(members),
            bool(data.get(KEY_LOUD, False)),
            data.get(KEY_QUIET_ENTITY) or None,
            threshold,
            QuietBehaviour(data.get(KEY_QUIET_BEHAVIOUR) or QuietBehaviour.HOLD),
        )


def _action_name(action: str) -> str:
    """Return a legacy action's name, without any "notify." in front of it."""
    return action.strip().removeprefix("notify.")


def parse_target(value: Any) -> tuple[str, ...]:
    """Return a target from its stored form: a list, or comma-separated text."""
    if not value:
        return ()
    items = value if isinstance(value, list) else str(value).split(",")
    return tuple(item for item in (str(item).strip() for item in items) if item)


# Serialization for the notifier's store. Settings added since the first version
# are read with their defaults when they're missing.
KEY_KIND = "kind"
KIND_ENTITY = "entity"
KIND_ACTION = "action"
KIND_PERSISTENT = "persistent"
KEY_CLEAR_ON_ACK = "clear_on_ack"


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
            KEY_MOBILE: member.mobile.value,
            KEY_CLEAR_ON_ACK: member.clear_on_ack,
            KEY_CLEAR_WHEN_ENDED: member.clear_when_ended,
            KEY_QUIET_DATA: dict(member.quiet_data) if member.quiet_data else None,
        }
    return {
        KEY_KIND: KIND_PERSISTENT,
        KEY_CLEAR_ON_ACK: member.clear_on_ack,
        KEY_CLEAR_WHEN_ENDED: member.clear_when_ended,
    }


def member_from_dict(data: Mapping[str, Any]) -> Member:
    """Return a member from its stored form."""
    if data[KEY_KIND] == KIND_ENTITY:
        return EntityMember(data["entity_id"])
    if data[KEY_KIND] == KIND_ACTION:
        return ActionMember(
            data[KEY_ACTION],
            data.get(KEY_DATA),
            tuple(data.get(KEY_TARGET) or ()),
            MobileFeatures(data.get(KEY_MOBILE, MobileFeatures.AUTOMATIC)),
            data.get(KEY_CLEAR_ON_ACK, True),
            data.get(KEY_CLEAR_WHEN_ENDED, False),
            data.get(KEY_QUIET_DATA),
        )
    return PersistentMember(
        data.get(KEY_CLEAR_ON_ACK, True), data.get(KEY_CLEAR_WHEN_ENDED, False)
    )


def notification_to_dict(notification: Notification) -> dict[str, Any]:
    """Return a notification in storable form."""
    return {
        "title": notification.title,
        "message": notification.message,
        "key": notification.key,
        "variables": dict(notification.variables),
        "buttons": [
            {"id": button.id, "title": button.title, "unlock": button.require_unlock}
            for button in notification.buttons
        ],
        "final": notification.final,
        "urgency": notification.urgency,
    }


def notification_from_dict(data: Mapping[str, Any]) -> Notification:
    """Return a notification from its stored form."""
    return Notification(
        data["title"],
        data["message"],
        data["key"],
        data.get("variables") or {},
        tuple(
            Button(button["id"], button["title"], button.get("unlock", False))
            for button in data.get("buttons") or []
        ),
        data.get("final", False),
        data.get("urgency", 0),
    )
