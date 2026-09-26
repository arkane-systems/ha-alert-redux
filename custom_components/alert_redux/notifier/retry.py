"""The retry queue's records: deliveries and their per-member attempts (spec §15.2).

A delivery is one notification on its way to the members of some groups. Each member
is an attempt of its own, retried with backoff until it succeeds or the delivery's
deadline passes, so one broken member never holds up the others. The delivery has
been delivered once any member succeeds; if none has by the time the last attempt
gives up, the notification goes to the fallback.

A clearing delivery removes a notification rather than sending one (spec §9.10); it
never goes to the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .model import (
    Member,
    Notification,
    member_from_dict,
    member_to_dict,
    notification_from_dict,
    notification_to_dict,
)

FIRST_RETRY = timedelta(seconds=5)
MAX_RETRY = timedelta(seconds=60)


def backoff(tries: int) -> timedelta:
    """Return the wait before the next try, after the given number of tries."""
    return min(FIRST_RETRY * 2 ** max(tries - 1, 0), MAX_RETRY)


@dataclass(slots=True)
class Attempt:
    """Sending a delivery's notification to one member, with the tag to use."""

    id: str
    group_id: str
    group_name: str
    member: Member
    tag: str
    tries: int = 0
    next_try: datetime | None = None
    # Softened for quiet hours: sent with the member's quiet-hours data (§9.9).
    soft: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the attempt in storable form."""
        return {
            "id": self.id,
            "group_id": self.group_id,
            "group_name": self.group_name,
            "member": member_to_dict(self.member),
            "tag": self.tag,
            "tries": self.tries,
            "next_try": self.next_try.isoformat() if self.next_try else None,
            "soft": self.soft,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], key: str) -> Attempt:
        """Return an attempt from its stored form; its tag defaults to the key."""
        return cls(
            data["id"],
            data["group_id"],
            data["group_name"],
            member_from_dict(data["member"]),
            data.get("tag") or key,
            data.get("tries", 0),
            datetime.fromisoformat(data["next_try"]) if data.get("next_try") else None,
            data.get("soft", False),
        )


@dataclass(slots=True)
class Delivery:
    """A notification on its way to some members.

    A fallback delivery is itself the fallback: if it fails, that's only logged.
    """

    id: str
    notification: Notification
    deadline: datetime
    is_fallback: bool = False
    delivered: bool = False
    attempts: dict[str, Attempt] = field(default_factory=dict)
    clear: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the delivery in storable form."""
        return {
            "id": self.id,
            "notification": notification_to_dict(self.notification),
            "deadline": self.deadline.isoformat(),
            "is_fallback": self.is_fallback,
            "delivered": self.delivered,
            "attempts": [attempt.to_dict() for attempt in self.attempts.values()],
            "clear": self.clear,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Delivery:
        """Return a delivery from its stored form."""
        notification = notification_from_dict(data["notification"])
        attempts = [
            Attempt.from_dict(item, notification.key)
            for item in data.get("attempts", [])
        ]
        return cls(
            data["id"],
            notification,
            datetime.fromisoformat(data["deadline"]),
            data.get("is_fallback", False),
            data.get("delivered", False),
            {attempt.id: attempt for attempt in attempts},
            data.get("clear", False),
        )
