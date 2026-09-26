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
- is_quiet: whether a group is in quiet hours.

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

Quiet hours (spec §9.9) apply to loud groups while their quiet-hours entity (the
group's own, or the global one) is on, and to notifications less urgent than the
threshold (the group's own, or the global one). Such a notification is held, or,
in a group that softens, sent with the quiet-hours data of the members that have
some and held for the rest. Held notifications are kept in the store. When quiet
hours end, the owner's on_quiet_ended callback is given each key's held
notifications and returns what to send instead; that goes to the members that
held. A key whose held notifications included a final one, and that gets nothing
sent, has its earlier notification cleared from those members.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any

from homeassistant.const import (
    EVENT_SERVICE_REGISTERED,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
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
    QuietBehaviour,
    can_soften,
    member_from_dict,
    member_to_dict,
    notification_from_dict,
    notification_to_dict,
)
from .repairs import (
    async_clear_issue,
    async_raise_action_missing,
    async_raise_quiet_entity_missing,
    issue_id,
)
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
    "QuietBehaviour",
    "QuietEnded",
]

_LOGGER = logging.getLogger(__name__)

# The built-in fallback, used unless another group is chosen.
FALLBACK_GROUP = GroupConfig("fallback", "Fallback", (PersistentMember(),))
DEFAULT_RETRY_TIMEOUT = timedelta(minutes=5)

STORAGE_VERSION = 1
STORAGE_SAVE_DELAY = 1  # seconds

# The owner's say in what's sent when a group's quiet hours end: given the
# group's ID and each key's held notifications, in the order they were held, it
# returns the notifications to send instead.
type QuietEnded = Callable[[str, dict[str, list[Notification]]], list[Notification]]


def _latest_of_each(
    _group_id: str, held: dict[str, list[Notification]]
) -> list[Notification]:
    """Without an owner's say, send the latest held notification of each key."""
    return [notifications[-1] for notifications in held.values()]


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
        self,
        hass: HomeAssistant,
        *,
        store_key: str,
        issue_domain: str,
        on_quiet_ended: QuietEnded | None = None,
    ) -> None:
        """Initialize; the store key, issue domain, and callback are the owner's."""
        self.hass = hass
        self._issue_domain = issue_domain
        self._on_quiet_ended = on_quiet_ended or _latest_of_each
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, store_key, private=True
        )
        self._groups: dict[str, GroupConfig] = {}
        self._fallback_id: str | None = None
        self._retry_timeout = DEFAULT_RETRY_TIMEOUT
        # Quiet hours: the global entity and threshold (an urgency).
        self._quiet_entity: str | None = None
        self._quiet_threshold: int | None = None
        # Held notifications: group ID -> key -> notifications, oldest first.
        self._held: dict[str, dict[str, list[Notification]]] = {}
        self._quiet_unsub: CALLBACK_TYPE | None = None
        # Raised missing quiet-hours entity issues: issue ID -> entity ID.
        self._quiet_issues: dict[str, str] = {}
        # Whether Home Assistant has started, so quiet-hours entities can be read.
        self._started = False
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
        self._held = {
            group_id: {
                key: [notification_from_dict(item) for item in notifications]
                for key, notifications in keys.items()
            }
            for group_id, keys in data.get("held", {}).items()
        }
        self._quiet_issues = dict(data.get("quiet_issues", {}))

    @callback
    def async_configure(
        self,
        *,
        fallback_group: str | None,
        retry_timeout: timedelta,
        quiet_entity: str | None = None,
        quiet_threshold: int | None = None,
    ) -> None:
        """Set the fallback group (None for the built-in one), the retry timeout,
        and the global quiet-hours entity and threshold (None: every urgency)."""
        self._fallback_id = fallback_group
        self._retry_timeout = retry_timeout
        self._quiet_entity = quiet_entity
        self._quiet_threshold = quiet_threshold
        self._async_quiet_config_changed()

    @callback
    def async_set_groups(self, groups: Iterable[GroupConfig]) -> None:
        """Replace the group definitions, e.g. after one is added or edited."""
        self._groups = {group.id: group for group in groups}
        self._async_check_actions(raise_missing=self._checking_actions)
        for group_id in list(self._held):
            if group_id not in self._groups:
                _LOGGER.info(
                    "Notifier group %s was deleted; its held notifications "
                    "are dropped",
                    group_id,
                )
                del self._held[group_id]
                self._async_save()
        self._async_quiet_config_changed()

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
        if self._quiet_unsub is not None:
            self._quiet_unsub()
            self._quiet_unsub = None
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
        """Return whether the group is in quiet hours: it's loud, and its
        quiet-hours entity is on. One that's missing or unavailable isn't on."""
        group = self._groups.get(group_id)
        return group is not None and self._quiet_state(group) is True

    def _quiet_entity_of(self, group: GroupConfig) -> str | None:
        """Return the quiet-hours entity a loud group follows, if any."""
        if not group.loud:
            return None
        return group.quiet_entity or self._quiet_entity

    def _quiet_state(self, group: GroupConfig) -> bool | None:
        """Return whether a group is in quiet hours: True, False, or None when
        its entity is unavailable, or unknown, so that can't be told."""
        if (entity_id := self._quiet_entity_of(group)) is None:
            return False
        if (state := self.hass.states.get(entity_id)) is None:
            # Missing altogether: quiet hours don't apply (and it's raised).
            return False
        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state.state == STATE_ON

    def _affected(self, group: GroupConfig, notification: Notification) -> bool:
        """Return whether quiet hours hold back or soften a notification to a
        group: it's in quiet hours, and the notification is less urgent than
        the threshold."""
        if not self.is_quiet(group.id):
            return False
        threshold = (
            group.quiet_threshold
            if group.quiet_threshold is not None
            else self._quiet_threshold
        )
        return threshold is None or notification.urgency < threshold

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
        """Clear the key's notifications from every member showing them, and
        drop any held for quiet hours."""
        for keys in self._held.values():
            if keys.pop(key, None) is not None:
                self._async_save()
        self._async_clear_live(key, lambda member: member.replaces)

    @callback
    def async_rekey(self, old: str, new: str) -> None:
        """Follow a key being changed.

        What's showing keeps its old tag; the next notification to such a member
        clears it first, and clearing the new key clears it.
        """
        for keys in self._held.values():
            if (held := keys.pop(old, None)) is not None:
                keys.setdefault(new, []).extend(
                    replace(notification, key=new) for notification in held
                )
                self._async_save()
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
        held = False
        for group in groups:
            quiet = self._affected(group, notification)
            soften = quiet and group.quiet_behaviour is QuietBehaviour.SOFTEN
            holding = False
            for member in group.members:
                if member in members:
                    continue
                members.append(member)
                if quiet and not (soften and can_soften(member)):
                    holding = True
                    continue
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
                attempt = Attempt(
                    ulid_now(), group.id, group.name, member, key, soft=quiet
                )
                delivery.attempts[attempt.id] = attempt
            if holding:
                self._async_hold(group, notification)
                held = True
        if key in self._live and not self._live[key]:
            del self._live[key]
        if clears:
            self._async_start_clear(key, clears)
        # A held notification will be dealt with when quiet hours end, so it
        # never goes to the fallback.
        delivery.delivered = held
        if not delivery.attempts:
            # Nothing to send; only a notification that had members to go to and
            # was cleared from them all, or held, isn't undelivered.
            if not clears and not held:
                self._async_undelivered(delivery)
            return
        self._async_start(delivery)

    @callback
    def _async_hold(self, group: GroupConfig, notification: Notification) -> None:
        """Hold a notification for a group until its quiet hours end."""
        _LOGGER.debug(
            "%s: held for group %s; quiet hours", notification.key, group.name
        )
        self._held.setdefault(group.id, {}).setdefault(notification.key, []).append(
            notification
        )
        self._async_save()

    @callback
    def _async_quiet_config_changed(self) -> None:
        """Watch the quiet-hours entities in use, and release groups whose
        quiet hours have ended (or no longer apply)."""
        if self._quiet_unsub is not None:
            self._quiet_unsub()
            self._quiet_unsub = None
        if self._stopped:
            return
        if entities := self._quiet_entities():
            self._quiet_unsub = async_track_state_change_event(
                self.hass, list(entities), self._async_quiet_entity_changed
            )
        self._async_release_ended()
        if self._checking_actions:
            self._async_check_quiet_entities(raise_missing=True)

    def _quiet_entities(self) -> dict[str, list[str]]:
        """Return the quiet-hours entities in use, each with where it's used."""
        entities: dict[str, list[str]] = {}
        for group in self._groups.values():
            if (entity_id := self._quiet_entity_of(group)) is not None:
                entities.setdefault(entity_id, []).append(group.name)
        return entities

    @callback
    def _async_quiet_entity_changed(self, _event: Event[EventStateChangedData]) -> None:
        if self._quiet_issues:
            self._async_check_quiet_entities(raise_missing=False)
        self._async_release_ended()

    @callback
    def _async_release_ended(self) -> None:
        """Release the held notifications of groups no longer in quiet hours.

        Only once Home Assistant has started, so that the entities have their
        states; an unavailable or unknown entity keeps them held.
        """
        if not self._started or self._stopped:
            return
        for group_id in list(self._held):
            group = self._groups.get(group_id)
            if group is not None and self._quiet_state(group) is False:
                self._async_quiet_ended(group)

    @callback
    def _async_quiet_ended(self, group: GroupConfig) -> None:
        """Send what the owner says for a group's held notifications, to the
        members that held them (spec §9.9)."""
        if not (held := self._held.pop(group.id, None)):
            return
        self._async_save()
        holding = group.holding_members()
        _LOGGER.debug(
            "Quiet hours ended for group %s: %d key(s) held", group.name, len(held)
        )
        notifications = self._on_quiet_ended(group.id, held)
        sent = {notification.key for notification in notifications}
        # A key that ended while held, and gets nothing now, is cleared from the
        # members that held it, as its final notification would have done.
        for key, notifications_held in held.items():
            if key not in sent and any(n.final for n in notifications_held):
                self._async_clear_live(
                    key, lambda member: member.replaces and member in holding
                )
        if not holding:
            return
        target = replace(group, members=holding)
        for notification in notifications:
            self._async_deliver([target], notification, is_fallback=False)

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
                    self.hass, member, delivery.notification, attempt.tag, attempt.soft
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
        """Release groups whose quiet hours ended while Home Assistant was down,
        and check the legacy actions and quiet-hours entities once integrations
        have had time to set up."""
        self._started = True
        self._async_release_ended()

        @callback
        def _check(_now: datetime) -> None:
            self._checking_actions = True
            self._async_check_actions(raise_missing=True)
            self._async_check_quiet_entities(raise_missing=True)

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
    def _async_check_quiet_entities(self, raise_missing: bool) -> None:
        """Clear issues for quiet-hours entities that exist or aren't used;
        optionally, raise them for every one in use that doesn't exist."""
        entities = self._quiet_entities()
        for ident, entity_id in list(self._quiet_issues.items()):
            if entity_id not in entities or self.hass.states.get(entity_id):
                async_clear_issue(self.hass, self._issue_domain, ident)
                del self._quiet_issues[ident]
                self._async_save()
        if not raise_missing:
            return
        for entity_id, used_by in entities.items():
            if self.hass.states.get(entity_id) is None:
                ident = async_raise_quiet_entity_missing(
                    self.hass, self._issue_domain, entity_id, ", ".join(used_by)
                )
                if ident not in self._quiet_issues:
                    self._quiet_issues[ident] = entity_id
                    self._async_save()

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
            "held": {
                group_id: {
                    key: [notification_to_dict(n) for n in notifications]
                    for key, notifications in keys.items()
                }
                for group_id, keys in self._held.items()
            },
            "quiet_issues": self._quiet_issues,
        }
