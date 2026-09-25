"""The notifier module: delivering notifications to notifier groups (spec §9.1).

Self-contained, so that it can later become an integration of its own: it knows
about groups, members, and notifications, and nothing about alerts. Its interface is
narrow:

- async_send: send a notification to some groups;
- async_send_fallback: send a notification to the fallback;
- is_quiet: whether a group is in quiet hours (always False until quiet hours exist).
"""

from __future__ import annotations

from collections.abc import Iterable
import logging

from homeassistant.core import HomeAssistant, callback

from .members import MemberMissing, async_deliver
from .model import (
    ActionMember,
    EntityMember,
    GroupConfig,
    Member,
    Notification,
    PersistentMember,
)

__all__ = [
    "ActionMember",
    "EntityMember",
    "FALLBACK_GROUP",
    "GroupConfig",
    "Notification",
    "Notifier",
    "PersistentMember",
]

_LOGGER = logging.getLogger(__name__)

FALLBACK_GROUP = GroupConfig("fallback", "Fallback", (PersistentMember(),))


class Notifier:
    """Sends notifications to the configured notifier groups."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize with no groups; call async_set_groups to add them."""
        self.hass = hass
        self._groups: dict[str, GroupConfig] = {}

    @callback
    def async_set_groups(self, groups: Iterable[GroupConfig]) -> None:
        """Replace the group definitions, e.g. after one is added or edited."""
        self._groups = {group.id: group for group in groups}

    def group(self, group_id: str) -> GroupConfig | None:
        """Return a group's definition, if it exists."""
        return self._groups.get(group_id)

    def is_quiet(self, group_id: str) -> bool:
        """Return whether the group is in quiet hours."""
        return False

    @callback
    def async_send(self, group_ids: Iterable[str], notification: Notification) -> None:
        """Send a notification to each of the groups, in the background.

        A group that doesn't exist is skipped. Each member is sent to independently,
        so one failing member doesn't affect the rest.
        """
        groups: list[GroupConfig] = []
        for group_id in group_ids:
            if (group := self._groups.get(group_id)) is None:
                _LOGGER.warning(
                    "%s: notifier group %s doesn't exist; skipped",
                    notification.key,
                    group_id,
                )
                continue
            groups.append(group)
        self._async_send_to_groups(groups, notification)

    @callback
    def async_send_fallback(self, notification: Notification) -> None:
        """Send a notification to the fallback."""
        self._async_send_to_groups([FALLBACK_GROUP], notification)

    @callback
    def _async_send_to_groups(
        self, groups: list[GroupConfig], notification: Notification
    ) -> None:
        # A member in several of the groups is sent the notification only once.
        # (Members with data aren't hashable, so they're compared, not keyed.)
        members: list[tuple[Member, GroupConfig]] = []
        for group in groups:
            for member in group.members:
                if all(member != seen for seen, _ in members):
                    members.append((member, group))
        for member, group in members:
            self.hass.async_create_task(
                self._async_deliver(group, member, notification),
                f"alert_redux notify {member}",
                eager_start=True,
            )

    async def _async_deliver(
        self, group: GroupConfig, member: Member, notification: Notification
    ) -> None:
        try:
            await async_deliver(self.hass, member, notification)
        except MemberMissing as err:
            _LOGGER.warning(
                "%s: couldn't notify %s in group %s: %s",
                notification.key,
                member,
                group.name,
                err,
            )
        except Exception:
            _LOGGER.exception(
                "%s: notifying %s in group %s failed",
                notification.key,
                member,
                group.name,
            )
        else:
            _LOGGER.debug("%s: notified %s", notification.key, member)
