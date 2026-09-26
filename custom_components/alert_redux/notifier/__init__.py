"""The notifier module: delivering notifications to notifier groups (spec §9.1).

Self-contained, so that it can later become an integration of its own: it knows
about groups, members, and notifications, and nothing about alerts. Its interface is
narrow:

- async_send: send a notification to some groups;
- async_send_fallback: send a notification to the fallback;
- async_acknowledged: the notifications with a key have been acknowledged, so clear
  them where members are set to;
- async_clear: clear the notifications with a key everywhere;
- async_rekey: a key has changed (e.g. its owner was renamed);
- is_quiet: whether a group is in quiet hours (always False until quiet hours exist).

Behind it, a member that's missing or fails is retried with backoff until a timeout
(spec §15.2); a notification that reaches no member at all goes to the fallback
group (§9.4); and a legacy notify action that doesn't exist is raised as a Repairs
issue (§9.2). The retry queue is kept in the module's own store, so it survives a
restart.

Members that can replace notifications (spec §9.10) are sent each one with its key
as a tag, so it replaces the one before. The notifier remembers which of them are
showing a notification for each key (live records), so that clearing reaches
exactly those, even after a group has been edited or when the notification went to
the fallback. A final notification ends its key's live records: it stays on show,
but there's nothing more to clear. A new notification or clear for a member drops
any earlier one for the same tag still waiting to be retried.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any

from homeassistant.const import EVENT_SERVICE_REGISTERED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.ulid import ulid_now

from .members import (
    NOTIFY_DOMAIN,
    MemberMissing,
    async_clear,
    async_deliver,
    member_available,
)
from .model import (
    ActionMember,
    Button,
    EntityMember,
    GroupConfig,
    Member,
    MobileFeatures,
    Notification,
    PersistentMember,
    member_from_dict,
    member_to_dict,
)
from .repairs import async_clear_issue, async_raise_action_missing, issue_id
from .retry import Attempt, Delivery, backoff

__all__ = [
    "DEFAULT_RETRY_TIMEOUT",
    "FALLBACK_GROUP",
    "ActionMember",
    "Button",
    "EntityMember",
    "GroupConfig",
    "MobileFeatures",
    "Notification",
    "Notifier",
    "PersistentMember",
]

_LOGGER = logging.getLogger(__name__)

# The built-in fallback, used unless another group is chosen.
FALLBACK_GROUP = GroupConfig("fallback", "Fallback", (PersistentMember(),))
DEFAULT_RETRY_TIMEOUT = timedelta(minutes=5)

STORAGE_VERSION = 1
STORAGE_SAVE_DELAY = 1  # seconds


@dataclass(frozen=True, slots=True)
class Shown:
    """A notification showing on a member, which can later be cleared."""

    member: Member
    tag: str
    group_id: str
    group_name: str

    def to_dict(self) -> dict[str, Any]:
        """Return the record in storable form."""
        return {
            "member": member_to_dict(self.member),
            "tag": self.tag,
            "group_id": self.group_id,
            "group_name": self.group_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Shown:
        """Return a record from its stored form."""
        return cls(
            member_from_dict(data["member"]),
            data["tag"],
            data["group_id"],
            data["group_name"],
        )


# A clearing delivery's notification: only its key matters.
def _clearing(key: str) -> Notification:
    return Notification(title="", message="", key=key)


class Notifier:
    """Sends notifications to the configured notifier groups.

    Call async_load, then set the groups and configuration, then async_start;
    async_stop saves the retry queue and stops.
    """

    def __init__(
        self, hass: HomeAssistant, *, store_key: str, issue_domain: str
    ) -> None:
        """Initialize; the store key and issue domain belong to the owner."""
        self.hass = hass
        self._issue_domain = issue_domain
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, store_key, private=True
        )
        self._groups: dict[str, GroupConfig] = {}
        self._fallback_id: str | None = None
        self._retry_timeout = DEFAULT_RETRY_TIMEOUT
        self._deliveries: dict[str, Delivery] = {}
        self._timers: dict[str, CALLBACK_TYPE] = {}
        # Live records: key -> member destination -> what's showing there.
        self._live: dict[str, dict[tuple[str, ...], Shown]] = {}
        # Raised missing-action issues: issue ID -> (group ID, action).
        self._issues: dict[str, tuple[str, str]] = {}
        # Whether legacy actions are checked on every group change, which starts
        # once integrations have had the retry timeout to set up.
        self._checking_actions = False
        self._unsubs: list[Callable[[], None]] = []
        self._stopped = False

    async def async_load(self) -> None:
        """Load the retry queue and the raised issues."""
        data = await self._store.async_load() or {}
        for item in data.get("deliveries", []):
            delivery = Delivery.from_dict(item)
            self._deliveries[delivery.id] = delivery
        self._issues = {
            ident: (group_id, action)
            for ident, (group_id, action) in data.get("issues", {}).items()
        }
        for key, records in data.get("live", {}).items():
            shown = [Shown.from_dict(record) for record in records]
            self._live[key] = {record.member.destination: record for record in shown}

    @callback
    def async_configure(
        self, *, fallback_group: str | None, retry_timeout: timedelta
    ) -> None:
        """Set the fallback group (None for the built-in one) and the retry timeout."""
        self._fallback_id = fallback_group
        self._retry_timeout = retry_timeout

    @callback
    def async_set_groups(self, groups: Iterable[GroupConfig]) -> None:
        """Replace the group definitions, e.g. after one is added or edited."""
        self._groups = {group.id: group for group in groups}
        self._async_check_actions(raise_missing=self._checking_actions)

    @callback
    def async_start(self) -> None:
        """Resume the retry queue and start watching for notify actions."""
        now = dt_util.utcnow()
        for delivery in list(self._deliveries.values()):
            for attempt in list(delivery.attempts.values()):
                if now >= delivery.deadline:
                    self._async_give_up(
                        delivery, attempt, "timed out while Home Assistant was down"
                    )
                else:
                    self._async_schedule(delivery, attempt, attempt.next_try or now)
        self._unsubs.append(
            self.hass.bus.async_listen(
                EVENT_SERVICE_REGISTERED, self._async_service_registered
            )
        )
        self._unsubs.append(async_at_started(self.hass, self._async_started))

    async def async_stop(self) -> None:
        """Stop retrying and save the queue, to resume from it later."""
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()
        await self._store.async_save(self._data())

    def group(self, group_id: str) -> GroupConfig | None:
        """Return a group's definition, if it exists."""
        return self._groups.get(group_id)

    @property
    def fallback_group(self) -> GroupConfig:
        """Return the fallback: the chosen group if it exists, or the built-in one."""
        if self._fallback_id is not None and (
            group := self._groups.get(self._fallback_id)
        ):
            return group
        return FALLBACK_GROUP

    def is_quiet(self, group_id: str) -> bool:
        """Return whether the group is in quiet hours."""
        return False

    @callback
    def async_send(self, group_ids: Iterable[str], notification: Notification) -> None:
        """Send a notification to each of the groups, in the background.

        A group that doesn't exist is skipped. If no member of any group receives
        the notification, it goes to the fallback.
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
        self._async_deliver(groups, notification, is_fallback=False)

    @callback
    def async_send_fallback(self, notification: Notification) -> None:
        """Send a notification to the fallback."""
        self._async_deliver([self.fallback_group], notification, is_fallback=True)

    @callback
    def async_acknowledged(self, key: str) -> None:
        """Clear the key's notifications from the members set to clear them when
        they're acknowledged."""
        self._async_clear_live(key, lambda member: member.clear_on_ack)

    @callback
    def async_clear(self, key: str) -> None:
        """Clear the key's notifications from every member showing them."""
        self._async_clear_live(key, lambda member: member.replaces)

    @callback
    def async_rekey(self, old: str, new: str) -> None:
        """Follow a key being changed.

        What's showing keeps its old tag; the next notification to such a member
        clears it first, and clearing the new key clears it.
        """
        if (records := self._live.pop(old, None)) is None:
            return
        self._live.setdefault(new, {}).update(records)
        self._async_save()

    @callback
    def _async_clear_live(self, key: str, which: Callable[[Member], bool]) -> None:
        """Clear the key's notifications from the chosen members showing them.

        Ones still waiting to be retried to those members are dropped, so that
        they can't arrive after the clear; a final one is left to arrive.
        """
        for delivery in list(self._deliveries.values()):
            notification = delivery.notification
            if delivery.clear or notification.final or notification.key != key:
                continue
            for attempt in list(delivery.attempts.values()):
                if which(attempt.member) and attempt.id in self._timers:
                    _LOGGER.debug(
                        "%s: dropped a retry for %s; cleared", key, attempt.member
                    )
                    delivery.delivered = True
                    self._async_done(delivery, attempt)
        records = self._live.get(key, {})
        chosen = [shown for shown in records.values() if which(shown.member)]
        if not chosen:
            return
        for shown in chosen:
            del records[shown.member.destination]
        if not records:
            del self._live[key]
        self._async_start_clear(key, chosen)

    @callback
    def _async_start_clear(self, key: str, shown: list[Shown]) -> None:
        """Clear a notification from some members, retrying as for sending."""
        delivery = Delivery(
            ulid_now(),
            _clearing(key),
            dt_util.utcnow() + self._retry_timeout,
            clear=True,
        )
        for record in shown:
            attempt = Attempt(
                ulid_now(),
                record.group_id,
                record.group_name,
                record.member,
                record.tag,
            )
            delivery.attempts[attempt.id] = attempt
        self._async_start(delivery)
        self._async_save()

    @callback
    def _async_deliver(
        self, groups: list[GroupConfig], notification: Notification, is_fallback: bool
    ) -> None:
        key = notification.key
        delivery = Delivery(
            ulid_now(),
            notification,
            dt_util.utcnow() + self._retry_timeout,
            is_fallback=is_fallback,
        )
        clears: list[Shown] = []
        records = self._live.get(key, {})
        # A member in several of the groups is sent the notification only once.
        # (Members with data aren't hashable, so they're compared, not keyed.)
        members: list[Member] = []
        for group in groups:
            for member in group.members:
                if member in members:
                    continue
                members.append(member)
                if member.replaces:
                    shown = records.pop(member.destination, None)
                    if notification.final and member.clear_when_ended:
                        # Cleared instead of replaced with the final notification.
                        tag = shown.tag if shown else key
                        clears.append(Shown(member, tag, group.id, group.name))
                        continue
                    if shown is not None and shown.tag != key:
                        # Shown under an old key: clear it, since this won't
                        # replace it.
                        clears.append(shown)
                    elif shown is not None:
                        records[member.destination] = shown
                attempt = Attempt(ulid_now(), group.id, group.name, member, key)
                delivery.attempts[attempt.id] = attempt
        if key in self._live and not self._live[key]:
            del self._live[key]
        if clears:
            self._async_start_clear(key, clears)
        if not delivery.attempts:
            # Nothing to send; only a notification that had members to go to and
            # was cleared from them all isn't undelivered.
            if not clears:
                self._async_undelivered(delivery)
            return
        self._async_start(delivery)

    @callback
    def _async_start(self, delivery: Delivery) -> None:
        """Start a delivery's attempts, dropping what they replace."""
        self._deliveries[delivery.id] = delivery
        for attempt in list(delivery.attempts.values()):
            self._async_supersede(delivery, attempt)
        for attempt in list(delivery.attempts.values()):
            self._async_try(delivery, attempt)

    @callback
    def _async_supersede(self, newer: Delivery, attempt: Attempt) -> None:
        """Drop earlier attempts, waiting to be retried, that this one replaces.

        A member that replaces notifications only ever shows the latest for a tag,
        so an earlier one still waiting would only arrive out of order. A dropped
        attempt counts as delivered: the newer one goes in its place.
        """
        member = attempt.member
        if not member.replaces:
            return
        for delivery in list(self._deliveries.values()):
            if delivery is newer:
                continue
            for other in list(delivery.attempts.values()):
                if (
                    other.member.destination == member.destination
                    and other.tag == attempt.tag
                    and other.id in self._timers
                ):
                    _LOGGER.debug(
                        "%s: dropped a retry for %s; replaced",
                        delivery.notification.key,
                        member,
                    )
                    delivery.delivered = True
                    self._async_done(delivery, other)

    @callback
    def _async_try(self, delivery: Delivery, attempt: Attempt) -> None:
        self.hass.async_create_task(
            self._async_attempt(delivery, attempt),
            f"notify {attempt.member}",
            eager_start=True,
        )

    async def _async_attempt(self, delivery: Delivery, attempt: Attempt) -> None:
        attempt.tries += 1
        attempt.next_try = None
        member = attempt.member
        try:
            if delivery.clear:
                await async_clear(self.hass, member, attempt.tag)
            else:
                await async_deliver(
                    self.hass, member, delivery.notification, attempt.tag
                )
        except MemberMissing as err:
            error = str(err)
        except Exception as err:  # noqa: BLE001 - any failure is retried
            _LOGGER.debug(
                "%s: sending to %s failed", delivery.id, member, exc_info=True
            )
            error = str(err) or type(err).__name__
        else:
            _LOGGER.debug(
                "%s: %s %s",
                delivery.notification.key,
                "cleared" if delivery.clear else "notified",
                member,
            )
            delivery.delivered = True
            if not delivery.clear and member.replaces:
                self._async_record(delivery, attempt)
            self._async_done(delivery, attempt)
            return

        if self._stopped or delivery.id not in self._deliveries:
            # Kept in the saved queue, to be retried when the notifier restarts.
            return
        now = dt_util.utcnow()
        if now >= delivery.deadline:
            self._async_give_up(delivery, attempt, error)
            return
        if attempt.tries == 1:
            _LOGGER.info(
                "%s: couldn't notify %s in group %s (%s); retrying until %s",
                delivery.notification.key,
                member,
                attempt.group_name,
                error,
                dt_util.as_local(delivery.deadline).isoformat(timespec="seconds"),
            )
        # The last try is at the deadline itself.
        self._async_schedule(
            delivery, attempt, min(now + backoff(attempt.tries), delivery.deadline)
        )
        self._async_save()

    @callback
    def _async_record(self, delivery: Delivery, attempt: Attempt) -> None:
        """Remember what a member is showing now, until it's cleared."""
        key = delivery.notification.key
        records = self._live.setdefault(key, {})
        destination = attempt.member.destination
        if delivery.notification.final:
            records.pop(destination, None)
        else:
            records[destination] = Shown(
                attempt.member, attempt.tag, attempt.group_id, attempt.group_name
            )
        if not records:
            del self._live[key]

    @callback
    def _async_schedule(
        self, delivery: Delivery, attempt: Attempt, when: datetime
    ) -> None:
        attempt.next_try = when
        delay = max((when - dt_util.utcnow()).total_seconds(), 0)
        self._timers[attempt.id] = async_call_later(
            self.hass, delay, partial(self._async_retry, delivery, attempt)
        )

    @callback
    def _async_retry(
        self, delivery: Delivery, attempt: Attempt, _now: datetime
    ) -> None:
        self._timers.pop(attempt.id, None)
        self._async_try(delivery, attempt)

    @callback
    def _async_give_up(self, delivery: Delivery, attempt: Attempt, error: str) -> None:
        member = attempt.member
        _LOGGER.warning(
            "%s: gave up notifying %s in group %s after %d tries: %s",
            delivery.notification.key,
            member,
            attempt.group_name,
            attempt.tries,
            error,
        )
        # Only for a member its group still has: the group may have been edited or
        # deleted while the notification was waiting.
        group = self._groups.get(attempt.group_id)
        if (
            isinstance(member, ActionMember)
            and group is not None
            and member in group.members
            and not member_available(self.hass, member)
        ):
            self._async_raise(group, member)
        self._async_done(delivery, attempt)

    @callback
    def _async_done(self, delivery: Delivery, attempt: Attempt) -> None:
        """Finish an attempt; once they're all finished, finish the delivery."""
        if (cancel := self._timers.pop(attempt.id, None)) is not None:
            cancel()
        delivery.attempts.pop(attempt.id, None)
        if delivery.attempts:
            self._async_save()
            return
        finished = self._deliveries.pop(delivery.id, None) is not None
        if finished and not delivery.delivered and not delivery.clear:
            self._async_undelivered(delivery)
        self._async_save()

    @callback
    def _async_undelivered(self, delivery: Delivery) -> None:
        """Deal with a notification that reached nobody: fall back, or log."""
        key = delivery.notification.key
        if delivery.is_fallback:
            _LOGGER.error("%s: the fallback couldn't be notified either", key)
            return
        _LOGGER.warning("%s: no one could be notified; sending to the fallback", key)
        self.async_send_fallback(delivery.notification)

    @callback
    def _async_service_registered(self, event: Event) -> None:
        """Retry a legacy action as soon as it appears, and clear its issue."""
        if event.data.get("domain") != NOTIFY_DOMAIN:
            return
        service = event.data.get("service")
        for delivery in list(self._deliveries.values()):
            for attempt in list(delivery.attempts.values()):
                member = attempt.member
                if (
                    isinstance(member, ActionMember)
                    and member.action == service
                    and (cancel := self._timers.pop(attempt.id, None)) is not None
                ):
                    cancel()
                    self._async_try(delivery, attempt)
        self._async_check_actions(raise_missing=False)

    @callback
    def _async_started(self, _hass: HomeAssistant) -> None:
        """Check the legacy actions once integrations have had time to set up."""

        @callback
        def _check(_now: datetime) -> None:
            self._checking_actions = True
            self._async_check_actions(raise_missing=True)

        self._unsubs.append(
            async_call_later(self.hass, self._retry_timeout.total_seconds(), _check)
        )

    @callback
    def _async_check_actions(self, raise_missing: bool) -> None:
        """Clear issues for actions that exist now or were removed; optionally,
        raise them for every missing action."""
        current: dict[str, tuple[GroupConfig, ActionMember]] = {
            issue_id(group.id, member): (group, member)
            for group in self._groups.values()
            for member in group.members
            if isinstance(member, ActionMember)
        }
        for ident in list(self._issues):
            entry = current.get(ident)
            if entry is None or member_available(self.hass, entry[1]):
                async_clear_issue(self.hass, self._issue_domain, ident)
                del self._issues[ident]
                self._async_save()
        if raise_missing:
            for group, member in current.values():
                if not member_available(self.hass, member):
                    self._async_raise(group, member)

    @callback
    def _async_raise(self, group: GroupConfig, member: ActionMember) -> None:
        ident = async_raise_action_missing(self.hass, self._issue_domain, group, member)
        if ident not in self._issues:
            self._issues[ident] = (group.id, member.action)
            self._async_save()

    @callback
    def _async_save(self) -> None:
        self._store.async_delay_save(self._data, STORAGE_SAVE_DELAY)

    @callback
    def _data(self) -> dict[str, Any]:
        return {
            "deliveries": [
                delivery.to_dict() for delivery in self._deliveries.values()
            ],
            "issues": {
                ident: [group_id, action]
                for ident, (group_id, action) in self._issues.items()
            },
            "live": {
                key: [shown.to_dict() for shown in records.values()]
                for key, records in self._live.items()
            },
        }
