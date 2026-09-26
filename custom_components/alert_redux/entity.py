"""The alert entities (spec §7, §11)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACKNOWLEDGEABLE,
    ATTR_ATTRIBUTE,
    ATTR_BROKEN_REFERENCES,
    ATTR_CONDITION,
    ATTR_DELAY_OFF,
    ATTR_DELAY_OFF_UNTIL,
    ATTR_DELAY_ON,
    ATTR_DELAY_ON_UNTIL,
    ATTR_DISABLED_UNTIL,
    ATTR_DISPLAY_MESSAGE,
    ATTR_DURATION,
    ATTR_DURATION_SECONDS,
    ATTR_EVENT_DATA,
    ATTR_EVENT_EXPIRES,
    ATTR_EVENT_TYPE,
    ATTR_FIRE_COUNT,
    ATTR_FIRE_DATA,
    ATTR_FIRING_SINCE,
    ATTR_HYSTERESIS,
    ATTR_KIND,
    ATTR_LAST_ACKED,
    ATTR_LAST_ACKED_BY,
    ATTR_LAST_DISABLED,
    ATTR_LAST_DISABLED_BY,
    ATTR_LAST_ENABLED,
    ATTR_LAST_ENABLED_BY,
    ATTR_LAST_ENDED,
    ATTR_LAST_FIRED,
    ATTR_LAST_SNOOZED,
    ATTR_LAST_SNOOZED_BY,
    ATTR_LAST_UNACKED,
    ATTR_LAST_UNACKED_BY,
    ATTR_MAXIMUM,
    ATTR_MESSAGE,
    ATTR_MINIMUM,
    ATTR_MISSING_INPUTS,
    ATTR_NAME,
    ATTR_NEW_STATE,
    ATTR_NEXT_REMINDER,
    ATTR_NOTIFIER_GROUPS,
    ATTR_NO_DATA_GRACE,
    ATTR_NO_DATA_GRACE_UNTIL,
    ATTR_NO_DATA_SINCE,
    ATTR_OFF_TEMPLATE,
    ATTR_OFF_TRIGGERS,
    ATTR_OLD_STATE,
    ATTR_ON_TEMPLATE,
    ATTR_ON_TRIGGERS,
    ATTR_PRE_ACKED_BY,
    ATTR_PRE_SNOOZED_UNTIL,
    ATTR_PRIORITY,
    ATTR_REASON,
    ATTR_REMINDER_SCHEDULE,
    ATTR_SNOOZED_UNTIL,
    ATTR_SOURCE_ENTITY,
    ATTR_SUBJECT_ENTITY,
    ATTR_SUPERSEDED_BY,
    ATTR_SUPERSEDES,
    ATTR_TARGET_STATE,
    ATTR_TARGET_STATES,
    ATTR_TEMPLATE,
    ATTR_TRIGGERS,
    ATTR_TRIGGER_DATA,
    ATTR_USER_DISMISSABLE,
    ATTR_USER_ID,
    ATTR_VALUE,
    ATTR_VALUE_TEMPLATE,
    CONDITION_KINDS,
    CONF_ACKNOWLEDGEABLE,
    CONF_ALERT,
    CONF_ALERT_STATES,
    CONF_ATTRIBUTE,
    CONF_CONDITION,
    CONF_DELAY_OFF,
    CONF_DELAY_ON,
    CONF_DISPLAY_MESSAGE,
    CONF_DONE_MESSAGE,
    CONF_DURATION,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_EVENT_TYPE,
    CONF_HYSTERESIS,
    CONF_ICON,
    CONF_KIND,
    CONF_MAXIMUM,
    CONF_MESSAGE,
    CONF_MINIMUM,
    CONF_NOTIFIER_GROUPS,
    CONF_NO_DATA_GRACE,
    CONF_OFF_TEMPLATE,
    CONF_OFF_TRIGGERS,
    CONF_ON_TEMPLATE,
    CONF_ON_TRIGGERS,
    CONF_PRIORITY,
    CONF_REMINDER_MESSAGE,
    CONF_REMINDER_SCHEDULE,
    CONF_SUBJECT_ENTITY,
    CONF_SUPERSEDES,
    CONF_TARGET_STATE,
    CONF_TEMPLATE,
    CONF_TRIGGERS,
    CONF_USER_DISMISSABLE,
    CONF_VALUE_TEMPLATE,
    DATA_LABEL,
    DATA_STARTUP_UNTIL,
    DATA_SUMMARY,
    DATA_SUPERSESSION,
    DEFAULT_PRIORITY_ICONS,
    DOMAIN,
    EVENT_ACKED,
    EVENT_CREATED,
    EVENT_DATA_RESTORED,
    EVENT_DISABLED,
    EVENT_ENABLED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_KINDS,
    EVENT_NO_DATA,
    EVENT_SNOOZE_EXPIRED,
    EVENT_SNOOZED,
    EVENT_SUPERSEDED,
    EVENT_UNACKED,
    AlertKind,
    AlertState,
    EndReason,
    Priority,
)
from .labels import async_apply_label
from .messages import Messages, MessageTracker, message_context
from .model import (
    AlertRuntime,
    Change,
    OnOffSides,
    Reading,
    Settings,
    Timing,
    Transition,
    snooze_end_reminder,
    threshold_holds,
    to_timedelta,
)
from .notifications import (
    REASON_DONE,
    REASON_ON,
    REASON_REMINDER,
    async_send_notification,
    effective_groups,
    group_names,
)
from .sources import (
    Source,
    SourceSet,
    StateSource,
    TemplateSource,
    ThresholdSource,
    template_truth,
    value_template,
)
from .store import AlertStore
from .summary import AlertReport, SummaryCoordinator
from .supersession import DoneDecision, Supersession, relationship_targets
from .triggers import TriggerWatcher, bus_event_trigger

_LOGGER = logging.getLogger(__name__)

# The event announcing each kind of change (spec §11.3).
_CHANGE_EVENTS = {
    Change.FIRED: EVENT_FIRED,
    Change.ENDED: EVENT_ENDED,
    Change.NO_DATA: EVENT_NO_DATA,
    Change.ACKED: EVENT_ACKED,
    Change.UNACKED: EVENT_UNACKED,
    Change.SNOOZED: EVENT_SNOOZED,
    Change.SNOOZE_EXPIRED: EVENT_SNOOZE_EXPIRED,
    Change.DISABLED: EVENT_DISABLED,
    Change.ENABLED: EVENT_ENABLED,
    Change.DATA_RESTORED: EVENT_DATA_RESTORED,
}


class PointTimer:
    """A one-shot timer that runs an action at a point in time."""

    def __init__(self, action: Callable[[datetime], None]) -> None:
        """Initialize the timer, unset."""
        self._action = action
        self._unsub: CALLBACK_TYPE | None = None
        self.when: datetime | None = None

    @property
    def pending(self) -> bool:
        """Return whether the timer is set."""
        return self._unsub is not None

    @callback
    def at(self, hass: HomeAssistant, when: datetime | None) -> None:
        """Run the action at when, or never for None; the same time isn't re-set."""
        if when == self.when and (when is None or self.pending):
            return
        self.cancel()
        if when is not None:
            self.when = when
            self._unsub = async_track_point_in_utc_time(hass, self._run, when)

    @callback
    def cancel(self) -> None:
        """Unset the timer."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        self.when = None

    @callback
    def _run(self, now: datetime) -> None:
        self._unsub = None
        self.when = None
        self._action(now)


def create_alert_entity(
    subentry: ConfigSubentry, store: AlertStore, settings: Settings
) -> AlertEntity:
    """Return the entity for an alert subentry, according to its kind."""
    kind = AlertKind(subentry.data[CONF_KIND])
    if kind in CONDITION_KINDS:
        return ConditionAlertEntity(subentry, store, settings)
    if kind in EVENT_KINDS:
        return EventAlertEntity(subentry, store, settings)
    return AlertEntity(subentry, store, settings)


class AlertEntity(Entity):
    """One configured alert; on its own, a manual alert (spec §4.3)."""

    _attr_should_poll = False
    _attr_translation_key = "alert"
    # Whether the alert has inputs to wait for when it's enabled (spec §6.3).
    _awaits_data = False
    _unrecorded_attributes = frozenset(
        {ATTR_FIRE_DATA, ATTR_MESSAGE, ATTR_DISPLAY_MESSAGE}
    )

    def __init__(
        self, subentry: ConfigSubentry, store: AlertStore, settings: Settings
    ) -> None:
        """Initialize the alert from its subentry."""
        self._store = store
        self._settings = settings
        self._kind = AlertKind(subentry.data[CONF_KIND])
        self._runtime = AlertRuntime()
        self._messages: Messages | None = None
        self._message_tracker: MessageTracker | None = None
        self._message_key: tuple[Any, ...] | None = None
        # Whether this alert has been given the alerts label (spec §11.5).
        self._labelled = False
        self._reminder_timer = PointTimer(self._async_reminder_due)
        self._snooze_timer = PointTimer(self._async_snooze_due)
        self._suspension_timer = PointTimer(self._async_suspension_due)
        # Supersession (spec §8): the on notification waiting out the debounce,
        # and done notifications held for the done window (§9.7).
        self._on_debounce_timer = PointTimer(self._async_on_debounce_due)
        self._done_timer = PointTimer(self._async_done_due)
        self._held_dones: list[Transition] = []
        self._superseded_by: list[str] = []
        self._broken_references: list[str] = []
        self._pre_ack_timer = PointTimer(self._async_pre_ack_due)
        # Whether the alert was firing, and acknowledged, at the last write; None
        # before the first.
        self._was_firing: bool | None = None
        self._was_acked: bool | None = None
        self._attr_unique_id = subentry.subentry_id
        self._configure(subentry)

    def _configure(self, subentry: ConfigSubentry) -> None:
        """Take the alert's configuration from its subentry."""
        data = subentry.data
        self._priority = Priority(data[CONF_PRIORITY])
        self._acknowledgeable: bool = data[CONF_ACKNOWLEDGEABLE]
        self._user_dismissable: bool = data.get(CONF_USER_DISMISSABLE, False)
        self._explicit_subject: str | None = data.get(CONF_SUBJECT_ENTITY) or None
        self._message: str | None = data.get(CONF_MESSAGE) or None
        self._display_message: str | None = data.get(CONF_DISPLAY_MESSAGE) or None
        self._reminder_message: str | None = data.get(CONF_REMINDER_MESSAGE) or None
        self._done_message: str | None = data.get(CONF_DONE_MESSAGE) or None
        # None means the defaults; a list, even an empty one, is the alert's own.
        self._notifier_groups: list[str] | None = data.get(CONF_NOTIFIER_GROUPS)
        self._own_schedule: list[float] | None = data.get(CONF_REMINDER_SCHEDULE)
        self._supersedes: list[dict[str, Any]] = [
            dict(rel) for rel in data.get(CONF_SUPERSEDES) or []
        ]
        # The alert state kind's watched alert.
        self._watched_alert: str | None = data.get(CONF_ALERT) or None
        self._attr_name = subentry.title
        self._attr_icon = data.get(CONF_ICON) or DEFAULT_PRIORITY_ICONS[self._priority]

    @property
    def subject_entity(self) -> str | None:
        """Return the entity the alert is about, if any (spec §9.5)."""
        return self._explicit_subject

    @property
    def priority(self) -> Priority:
        """Return the alert's priority."""
        return self._priority

    @property
    def firing(self) -> bool:
        """Return whether the alert is firing (spec §3)."""
        return self._runtime.firing

    @property
    def last_ended(self) -> datetime | None:
        """Return when the alert last stopped firing."""
        return self._runtime.last_ended

    @property
    def supersedes(self) -> list[dict[str, Any]]:
        """Return the alert's supersession relationships, as configured (§8)."""
        return self._supersedes

    @property
    def references(self) -> list[str]:
        """Return the alerts this one refers to: superseded, or watched (§12.4)."""
        targets = relationship_targets(self._supersedes)
        if self._watched_alert:
            targets.append(self._watched_alert)
        return targets

    @property
    def context(self) -> Context | None:
        """Return the context of the change being handled, if any."""
        return self._context

    @property
    def _supersession(self) -> Supersession:
        return self.hass.data[DOMAIN][DATA_SUPERSESSION]

    @property
    def _summary(self) -> SummaryCoordinator:
        return self.hass.data[DOMAIN][DATA_SUMMARY]

    @property
    def _reminder_schedule(self) -> tuple[float, ...]:
        """Return the reminder schedule: the alert's own, or else the default."""
        if self._own_schedule is not None:
            return tuple(self._own_schedule)
        return self._settings.reminder_schedule

    @property
    def state(self) -> str:
        """Return the alert's state."""
        return self._runtime.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the alert's state details and configuration (spec §11.1)."""
        runtime = self._runtime
        now = dt_util.utcnow()
        attributes: dict[str, Any] = {
            ATTR_KIND: self._kind,
            ATTR_PRIORITY: self._priority,
            ATTR_ACKNOWLEDGEABLE: self._acknowledgeable,
            ATTR_SUBJECT_ENTITY: self.subject_entity,
            ATTR_FIRING_SINCE: runtime.firing_since,
            ATTR_LAST_FIRED: runtime.last_fired,
            ATTR_LAST_ENDED: runtime.last_ended,
            ATTR_FIRE_COUNT: runtime.fire_count,
            ATTR_LAST_ACKED: runtime.last_acked,
            ATTR_LAST_ACKED_BY: runtime.last_acked_by,
            ATTR_LAST_UNACKED: runtime.last_unacked,
            ATTR_LAST_UNACKED_BY: runtime.last_unacked_by,
            ATTR_SNOOZED_UNTIL: runtime.snoozed_until,
            ATTR_LAST_SNOOZED: runtime.last_snoozed,
            ATTR_LAST_SNOOZED_BY: runtime.last_snoozed_by,
            ATTR_DISABLED_UNTIL: runtime.disabled_until,
            ATTR_LAST_DISABLED: runtime.last_disabled,
            ATTR_LAST_DISABLED_BY: runtime.last_disabled_by,
            ATTR_LAST_ENABLED: runtime.last_enabled,
            ATTR_LAST_ENABLED_BY: runtime.last_enabled_by,
            ATTR_MESSAGE: self._messages.message if self._messages else None,
            ATTR_DISPLAY_MESSAGE: (
                self._messages.display_message if self._messages else None
            ),
            ATTR_NOTIFIER_GROUPS: group_names(
                self.hass, effective_groups(self._settings, self._notifier_groups)
            ),
            ATTR_REMINDER_SCHEDULE: list(self._reminder_schedule),
            ATTR_NEXT_REMINDER: runtime.next_reminder,
            ATTR_SUPERSEDES: relationship_targets(self._supersedes),
            ATTR_SUPERSEDED_BY: self._superseded_by,
            ATTR_PRE_ACKED_BY: self._supersession.entity_ids(
                runtime.live_pre_acks(now)
            ),
            ATTR_PRE_SNOOZED_UNTIL: runtime.pre_ack_deadline(now),
            ATTR_BROKEN_REFERENCES: self._broken_references,
        }
        if self._kind is AlertKind.MANUAL:
            attributes[ATTR_USER_DISMISSABLE] = self._user_dismissable
            attributes[ATTR_FIRE_DATA] = runtime.fire_data
        return attributes

    async def async_added_to_hass(self) -> None:
        """Restore the persisted state, or announce a new alert.

        An alert that hasn't been given the alerts label yet gets it now, whether
        it's new or existed before the label did. That happens once per alert, so
        removing the label from an alert is left alone.
        """
        assert self.unique_id is not None
        record = self._store.get_alert(self.unique_id)
        if record is not None:
            self._runtime = AlertRuntime.from_dict(record["runtime"])
            self._labelled = record.get("labelled", False)
        if not self._labelled:
            self._labelled = True
            if (label_id := self.hass.data[DOMAIN].get(DATA_LABEL)) is not None:
                async_apply_label(self.hass, self.entity_id, label_id)
        self._async_restored()
        if self._runtime.state is AlertState.ACTIVE and not self._runtime.next_reminder:
            # E.g. an alert that was firing before reminders existed.
            self._runtime.plan_reminder(self._reminder_schedule, dt_util.utcnow())
        # A reminder that fell due, or a snooze that ran out, while Home Assistant
        # was down is dealt with now (spec §15.1).
        self._async_update_timers()
        self._persist()
        if record is None:
            self._fire_event(EVENT_CREATED, None)

    async def async_will_remove_from_hass(self) -> None:
        """Stop rendering the messages, and the timers.

        Held done notifications are sent rather than lost (fail loud).
        """
        self._async_done_due(dt_util.utcnow())
        self._async_stop_messages()
        self._async_cancel_timers()
        assert self.unique_id is not None
        self._summary.async_withdraw(self.unique_id)

    @callback
    def async_write_ha_state(self) -> None:
        """Bring the rendered messages and supersession up to date, then write.

        A change in whether the alert is firing is passed on to the alerts it
        supersedes, and every write is reported to the summary (spec §11.2).
        """
        supersession = self._supersession
        self._async_sync_messages()
        self._superseded_by = supersession.superseded_by(self.entity_id)
        self._broken_references = supersession.broken_references(self)
        super().async_write_ha_state()
        assert self.unique_id is not None
        self._summary.async_report(
            self.unique_id,
            AlertReport(
                self.entity_id,
                self._runtime.state,
                self._priority,
                self._runtime.no_data_since is not None,
            ),
        )
        firing = self._runtime.firing
        if firing != self._was_firing:
            started = firing and self._was_firing is False
            self._was_firing = firing
            supersession.async_firing_changed(self, started=started)
        # Acknowledgements propagate (spec §8.2), but not when restored.
        acked = self._runtime.state is AlertState.ACK
        if acked != self._was_acked:
            was_acked, self._was_acked = self._was_acked, acked
            if was_acked is not None:
                supersession.async_ack_changed(self, acked=acked)

    @callback
    def async_superseders_changed(self, *, announce: bool) -> None:
        """Show which firing alerts supersede this one, now (spec §8.1).

        With announce, a firing alert that has just become superseded says so
        with the superseded event (§11.3).
        """
        if self.hass is None:
            return
        old = self._superseded_by
        supersession = self._supersession
        if (
            supersession.superseded_by(self.entity_id) == old
            and supersession.broken_references(self) == self._broken_references
        ):
            return
        self.async_write_ha_state()
        if announce and self._runtime.firing and not old and self._superseded_by:
            self._context = None
            self._fire_event(
                EVENT_SUPERSEDED,
                self.state,
                {ATTR_SUPERSEDED_BY: self._superseded_by},
            )

    @callback
    def async_add_pre_ack(
        self, source: str, until: datetime | None, context: Context | None
    ) -> None:
        """Take a pre-acknowledgement propagated from a superseded alert (§8.3).

        source is that alert's unique ID, which survives renames; until makes
        it a pre-snooze. An active alert is acknowledged, or
        snoozed until then, at once; the pre-acknowledgement also covers a
        later firing while the source stays acknowledged.
        """
        if not self._acknowledgeable:
            return
        runtime = self._runtime
        runtime.pre_acks[source] = until
        self._context = context
        if runtime.state is not AlertState.ACTIVE:
            self._async_update_timers()
            self.async_write_ha_state()
            self._persist()
            return
        now = dt_util.utcnow()
        pre_acked = {ATTR_PRE_ACKED_BY: self._supersession.entity_ids([source])}
        if until is None:
            transition = runtime.ack(now, self._user_id)
            assert transition is not None
            self._apply(EVENT_ACKED, transition, pre_acked)
        else:
            self._apply_changes(
                runtime.snooze(now, until, self._user_id),
                {Change.SNOOZED: {ATTR_SNOOZED_UNTIL: until}, Change.ACKED: pre_acked},
            )

    @callback
    def async_remove_pre_ack(self, source: str) -> None:
        """Cancel a pre-acknowledgement: its source is no longer acknowledged."""
        if source not in self._runtime.pre_acks:
            return
        del self._runtime.pre_acks[source]
        self._async_update_timers()
        self.async_write_ha_state()
        self._persist()

    @callback
    def async_drop_pre_acks(self, is_stale: Callable[[str], bool]) -> None:
        """Drop the pre-acknowledgements whose source is stale."""
        pre_acks = self._runtime.pre_acks
        if stale := [source for source in pre_acks if is_stale(source)]:
            for source in stale:
                del pre_acks[source]
            self._async_update_timers()
            self.async_write_ha_state()
            self._persist()

    @callback
    def _async_pre_ack_due(self, _now: datetime) -> None:
        """Forget pre-snoozes that have run out, so the attributes stay right."""
        if self._runtime.prune_pre_acks(dt_util.utcnow()):
            self._async_update_timers()
            self.async_write_ha_state()
            self._persist()

    def _pre_ack_new_firing(self, now: datetime) -> list[str] | None:
        """Start a new firing acknowledged, if it's been pre-acknowledged (§8.3)."""
        if not self._acknowledgeable:
            return None
        return self._runtime.apply_pre_ack(now, self._supersession.acknowledged())

    @callback
    def async_superseder_ended(self) -> None:
        """Drop held done notifications: a superseding alert's covers them (§9.7)."""
        if self._held_dones:
            _LOGGER.debug(
                "%s: done notification dropped; a superseding alert ended too",
                self.entity_id,
            )
            self._held_dones = []
            self._done_timer.cancel()

    @callback
    def _async_sync_messages(self) -> None:
        """Render the messages while firing, restarting when their inputs change.

        The context is the on notification's (spec §9.5), so the card shows the on
        message as it would be sent.
        """
        runtime = self._runtime
        key = (
            (
                self.name,
                self._priority,
                self.subject_entity,
                self._message,
                self._display_message,
                runtime.fire_count,
                runtime.fire_data,
            )
            if runtime.firing
            else None
        )
        if key == self._message_key:
            return
        self._async_stop_messages()
        self._message_key = key
        if key is None:
            return
        self._message_tracker = MessageTracker(
            self.hass,
            self._message,
            self._display_message,
            self._message_context(REASON_ON),
            f"{self.entity_id} message",
            self._async_messages_updated,
        )
        self._messages = self._message_tracker.async_start()

    def _message_context(
        self,
        reason: str,
        *,
        transition: Transition | None = None,
        duration_seconds: float = 0,
    ) -> dict[str, Any]:
        """Return the message template variables, for a notification or the card.

        An ending transition supplies the details of the firing that ended.
        """
        runtime = self._runtime
        data = transition.fire_data if transition else runtime.fire_data
        # An event alert's fire data is its trigger's variables (spec §9.5).
        is_event = self._kind in EVENT_KINDS
        return message_context(
            self.hass,
            name=str(self.name),
            entity_id=self.entity_id,
            priority=self._priority,
            subject_entity=self.subject_entity,
            fire_count=transition.fire_count if transition else runtime.fire_count,
            fire_data=None if is_event else data,
            trigger=(data or {}) if is_event else None,
            reason=reason,
            duration_seconds=(
                transition.duration_seconds or 0 if transition else duration_seconds
            ),
            end_reason=transition.reason if transition else None,
        )

    @callback
    def _async_notify(
        self, reason: str, template: str | None, variables: dict[str, Any]
    ) -> None:
        async_send_notification(
            self.hass,
            entity_id=self.entity_id,
            title=str(self.name),
            groups=effective_groups(self._settings, self._notifier_groups),
            template=template,
            variables=variables,
        )

    @callback
    def _async_notify_on(self) -> None:
        """Send the on notification of a new firing, or of firing again.

        An alert that something supersedes waits out the debounce first, to see
        whether a superseding alert fires too (spec §8.1).
        """
        if not self._supersession.has_superseders(self.entity_id):
            self._async_send_on()
            return
        now = dt_util.utcnow()
        debounce = self._settings.supersession_debounce
        if debounce <= timedelta(0):
            self._async_on_debounce_due(now)
        else:
            self._on_debounce_timer.at(self.hass, now + debounce)

    @callback
    def _async_on_debounce_due(self, _now: datetime) -> None:
        """Send the on notification, unless superseded or no longer active.

        A dropped on notification isn't sent later.
        """
        if self._runtime.state is not AlertState.ACTIVE:
            return
        if self._supersession.superseded_by(self.entity_id):
            _LOGGER.debug("%s: on notification superseded", self.entity_id)
            return
        self._async_send_on()

    @callback
    def _async_send_on(self) -> None:
        self._async_notify(REASON_ON, self._message, self._message_context(REASON_ON))

    @callback
    def _async_notify_done(self, transition: Transition) -> None:
        """Send the done notification of an ended firing (spec §9.7).

        A superseded alert's is dropped if a superseding alert ends within the
        done window of it, before or after.
        """
        if self._supersession.has_superseders(self.entity_id):
            now = dt_util.utcnow()
            decision = self._supersession.done_decision(self.entity_id, now)
            if decision is DoneDecision.DROP:
                _LOGGER.debug(
                    "%s: done notification dropped; a superseding alert ended too",
                    self.entity_id,
                )
                return
            if decision is DoneDecision.HOLD:
                self._held_dones.append(transition)
                self._done_timer.at(self.hass, now + self._settings.done_window)
                return
        self._async_send_done(transition)

    @callback
    def _async_done_due(self, _now: datetime) -> None:
        """Send the held done notifications: no superseding alert ended in time."""
        held, self._held_dones = self._held_dones, []
        self._done_timer.cancel()
        for transition in held:
            self._async_send_done(transition)

    @callback
    def _async_send_done(self, transition: Transition) -> None:
        self._async_notify(
            REASON_DONE,
            self._done_message,
            self._message_context(REASON_DONE, transition=transition),
        )

    @callback
    def _async_update_timers(self) -> None:
        """Set the timers to the runtime's deadlines: reminder, snooze, suspension."""
        self._reminder_timer.at(self.hass, self._runtime.next_reminder)
        self._snooze_timer.at(self.hass, self._runtime.snoozed_until)
        self._suspension_timer.at(self.hass, self._runtime.disabled_until)
        self._pre_ack_timer.at(self.hass, self._runtime.next_pre_ack_expiry())

    @callback
    def _async_cancel_timers(self) -> None:
        self._reminder_timer.cancel()
        self._snooze_timer.cancel()
        self._suspension_timer.cancel()
        self._on_debounce_timer.cancel()
        self._done_timer.cancel()
        self._pre_ack_timer.cancel()

    @callback
    def _async_reminder_due(self, _now: datetime) -> None:
        """Send a reminder, and plan the next one."""
        runtime = self._runtime
        if runtime.state is not AlertState.ACTIVE or runtime.next_reminder is None:
            return
        # The reminder is the alert's own doing, not the last user action's.
        self._context = None
        now = dt_util.utcnow()
        self._async_send_reminder(now)
        runtime.plan_reminder(self._reminder_schedule, now)
        self._async_update_timers()
        self.async_write_ha_state()
        self._persist()

    @callback
    def _async_send_reminder(self, now: datetime) -> None:
        """Send a reminder, giving the real firing duration.

        A superseded alert's reminder is skipped; its schedule carries on (§8.1).
        """
        if self._superseded_by:
            _LOGGER.debug("%s: reminder superseded", self.entity_id)
            return
        runtime = self._runtime
        duration = (
            (now - runtime.firing_since).total_seconds() if runtime.firing_since else 0
        )
        self._async_notify(
            REASON_REMINDER,
            self._reminder_message,
            self._message_context(REASON_REMINDER, duration_seconds=duration),
        )

    @callback
    def _async_snooze_due(self, _now: datetime) -> None:
        """End the snooze: active again, with the snooze-end reminder rule (§6.2)."""
        runtime = self._runtime
        if runtime.snoozed_until is None:
            return
        self._context = None
        # The timer may run a moment early; the snooze ends at its deadline.
        now = max(dt_util.utcnow(), runtime.snoozed_until)
        if not (changes := runtime.snooze_expire(now)):
            return
        remind = False
        if runtime.firing_since is not None:
            remind, runtime.next_reminder = snooze_end_reminder(
                runtime.firing_since,
                self._reminder_schedule,
                now,
                self._settings.snooze_reminder_window,
            )
        self._apply_changes(changes)
        if remind:
            self._async_send_reminder(now)

    @callback
    def _async_suspension_due(self, _now: datetime) -> None:
        """Enable a suspended alert: its time is up (spec §6.4)."""
        runtime = self._runtime
        if runtime.disabled_until is None:
            return
        self._context = None
        # The timer may run a moment early; the suspension ends at its time.
        now = max(dt_util.utcnow(), runtime.disabled_until)
        if changes := runtime.suspension_ended(now, awaits_data=self._awaits_data):
            self._apply_changes(changes)
            self._async_inputs_started()

    @callback
    def _async_inputs_started(self) -> None:
        """Start watching the alert's inputs, e.g. when it's enabled."""

    @callback
    def _async_inputs_stopped(self) -> None:
        """Stop watching the alert's inputs, e.g. when it's disabled."""

    @callback
    def _async_replan_reminder(self) -> None:
        """Plan the next reminder afresh, e.g. after the schedule changed."""
        self._runtime.plan_reminder(self._reminder_schedule, dt_util.utcnow())
        self._async_update_timers()

    @callback
    def _async_stop_messages(self) -> None:
        if self._message_tracker is not None:
            self._message_tracker.async_stop()
            self._message_tracker = None
        self._messages = None
        self._message_key = None

    @callback
    def _async_messages_updated(self, messages: Messages) -> None:
        self._messages = messages
        self.async_write_ha_state()

    @callback
    def _async_restored(self) -> None:
        """Prepare the restored (or new) runtime state, before it is saved."""

    @callback
    def _async_trigger_failed(self) -> None:
        """Show the alert as broken: its triggers couldn't be attached (§7.1)."""
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def async_update_config(self, subentry: ConfigSubentry) -> None:
        """Apply an edited subentry in place, keeping the alert's state."""
        self._configure(subentry)
        self._async_replan_reminder()
        self.async_write_ha_state()
        self._persist()

    @callback
    def async_settings_changed(self) -> None:
        """React to a change in the global defaults: groups and reminders."""
        self._async_replan_reminder()
        self.async_write_ha_state()
        self._persist()

    async def async_fire(self, data: dict[str, Any] | None = None) -> None:
        """Fire a manual alert, or fire it again if it is already firing."""
        self._require_manual()
        if self._runtime.disabled:
            # A disabled alert can't fire (spec §6.3).
            _LOGGER.debug("%s: fire ignored; disabled", self.entity_id)
            return
        now = dt_util.utcnow()
        transition = self._runtime.fire(now, data)
        pre_acked = None
        if transition.fire_count == 1:
            pre_acked = self._pre_ack_new_firing(now)
            self._runtime.plan_reminder(self._reminder_schedule, now)
        self._apply(
            EVENT_FIRED,
            transition,
            {ATTR_FIRE_COUNT: transition.fire_count, ATTR_FIRE_DATA: data},
        )
        self._announce_pre_ack(pre_acked)
        # Firing again sends the on message again, unless it's been acknowledged:
        # the acknowledgement is kept so that repeats don't nag (spec §4.2). A
        # pre-acknowledged firing sends none either (§8.3).
        if self._runtime.state is AlertState.ACTIVE:
            self._async_notify_on()

    async def async_dismiss(self) -> None:
        """Dismiss a firing manual alert."""
        self._require_manual()
        if (
            transition := self._runtime.end(dt_util.utcnow(), EndReason.DISMISSED)
        ) is None:
            _LOGGER.debug("%s: dismiss ignored; not firing", self.entity_id)
            return
        self._apply(EVENT_ENDED, transition, _ended_data(transition))
        self._async_notify_done(transition)

    async def async_ack(self) -> None:
        """Acknowledge the alert, or make a snooze a lasting acknowledgement."""
        self._require_acknowledgeable()
        if (transition := self._runtime.ack(dt_util.utcnow(), self._user_id)) is None:
            _LOGGER.debug("%s: ack ignored; not active or snoozed", self.entity_id)
            return
        self._apply(EVENT_ACKED, transition)

    async def async_snooze(self, duration: timedelta) -> None:
        """Acknowledge the alert for a while (spec §6.2)."""
        self._require_acknowledgeable()
        now = dt_util.utcnow()
        if not (changes := self._runtime.snooze(now, now + duration, self._user_id)):
            _LOGGER.debug("%s: snooze ignored; not firing", self.entity_id)
            return
        self._apply_changes(
            changes, {Change.SNOOZED: {ATTR_SNOOZED_UNTIL: self._runtime.snoozed_until}}
        )

    async def async_unack(self) -> None:
        """Remove the alert's acknowledgement."""
        if (transition := self._runtime.unack(dt_util.utcnow(), self._user_id)) is None:
            _LOGGER.debug("%s: unack ignored; not acknowledged", self.entity_id)
            return
        # Reminders resume on the firing's original schedule (spec §6.1, §6.2).
        self._runtime.plan_reminder(self._reminder_schedule, dt_util.utcnow())
        self._apply(EVENT_UNACKED, transition)

    async def async_disable(self) -> None:
        """Disable the alert until it's enabled again (spec §6.3)."""
        self._async_disable(None)

    async def async_suspend(
        self, duration: timedelta | None = None, until: datetime | None = None
    ) -> None:
        """Disable the alert for a while, or until a time (spec §6.4).

        A time without a time zone is local time.
        """
        now = dt_util.utcnow()
        end = now + duration if duration is not None else dt_util.as_utc(until)
        if end <= now:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="suspend_in_past",
                translation_placeholders={"entity_id": self.entity_id},
            )
        self._async_disable(end)

    @callback
    def _async_disable(self, until: datetime | None) -> None:
        """Disable or suspend: end any firing, and stop watching the inputs."""
        now = dt_util.utcnow()
        if not (changes := self._runtime.disable(now, self._user_id, until)):
            _LOGGER.debug("%s: disable ignored; already disabled", self.entity_id)
            return
        self._async_inputs_stopped()
        extra = {
            Change.ENDED: next(
                (_ended_data(t) for change, t in changes if change is Change.ENDED),
                {},
            ),
            Change.DISABLED: {ATTR_DISABLED_UNTIL: until},
        }
        self._apply_changes(changes, extra)
        for change, transition in changes:
            if change is Change.ENDED:
                # The done message says it was disabled, not resolved (§6.3).
                self._async_notify_done(transition)

    async def async_enable(self) -> None:
        """Enable a disabled or suspended alert, starting from scratch (§6.3)."""
        now = dt_util.utcnow()
        if not (
            changes := self._runtime.enable(
                now, self._user_id, awaits_data=self._awaits_data
            )
        ):
            _LOGGER.debug("%s: enable ignored; not disabled", self.entity_id)
            return
        self._apply_changes(changes)
        self._async_inputs_started()

    def _announce_pre_ack(self, pre_acked: list[str] | None) -> None:
        """Fire _acked for a firing that started pre-acknowledged (spec §11.3)."""
        if pre_acked:
            self._fire_event(
                EVENT_ACKED,
                AlertState.ACTIVE,
                {ATTR_PRE_ACKED_BY: self._supersession.entity_ids(pre_acked)},
            )

    @property
    def _user_id(self) -> str | None:
        """Return the user behind the action being handled, if any."""
        return self._context.user_id if self._context else None

    def _require_acknowledgeable(self) -> None:
        if not self._acknowledgeable:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_acknowledgeable",
                translation_placeholders={"entity_id": self.entity_id},
            )

    def _require_manual(self) -> None:
        if self._kind is not AlertKind.MANUAL:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_manual",
                translation_placeholders={"entity_id": self.entity_id},
            )

    def _apply(
        self,
        event_type: str,
        transition: Transition,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Publish an applied transition: state, storage, and event."""
        self._async_update_timers()
        self.async_write_ha_state()
        self._persist()
        self._fire_event(event_type, transition.old_state, extra)

    def _apply_changes(
        self,
        changes: list[tuple[Change, Transition]],
        extra: dict[Change, dict[str, Any]] | None = None,
    ) -> None:
        """Publish applied changes: state and storage once, then each event."""
        self._async_update_timers()
        self.async_write_ha_state()
        self._persist()
        for change, transition in changes:
            self._fire_event(
                _CHANGE_EVENTS[change], transition.old_state, (extra or {}).get(change)
            )

    def _persist(self) -> None:
        assert self.unique_id is not None
        self._store.set_alert(
            self.unique_id,
            {
                "entity_id": self.entity_id,
                ATTR_NAME: self.name,
                ATTR_KIND: self._kind,
                ATTR_PRIORITY: self._priority,
                "runtime": self._runtime.to_dict(),
                "labelled": self._labelled,
            },
        )

    def _fire_event(
        self,
        event_type: str,
        old_state: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Fire an Alert Redux event carrying the common data (spec §11.3)."""
        self.hass.bus.async_fire(
            event_type,
            {
                "entity_id": self.entity_id,
                ATTR_NAME: self.name,
                ATTR_PRIORITY: self._priority,
                ATTR_KIND: self._kind,
                ATTR_OLD_STATE: old_state,
                ATTR_NEW_STATE: self.state,
                ATTR_USER_ID: self._user_id,
                **(extra or {}),
            },
            context=self._context,
        )


class ConditionAlertEntity(AlertEntity):
    """An alert that fires while its condition holds (spec §4.1).

    Sources report the inputs, or that they have no data; each kind's rule turns
    them into the condition (_judge), the runtime applies the delays and the
    no-data grace period, and this entity keeps one timer for the runtime's next
    deadline.
    """

    _unrecorded_attributes = AlertEntity._unrecorded_attributes | frozenset(
        {
            ATTR_TEMPLATE,
            ATTR_CONDITION,
            ATTR_VALUE_TEMPLATE,
            ATTR_MINIMUM,
            ATTR_MAXIMUM,
            ATTR_VALUE,
            ATTR_ON_TEMPLATE,
            ATTR_ON_TRIGGERS,
            ATTR_OFF_TEMPLATE,
            ATTR_OFF_TRIGGERS,
        }
    )

    _awaits_data = True

    def __init__(
        self, subentry: ConfigSubentry, store: AlertStore, settings: Settings
    ) -> None:
        """Initialize the alert from its subentry."""
        self._sources: SourceSet | None = None
        self._results: dict[str, tuple[Any, list[str]]] | None = None
        self._watchers: list[TriggerWatcher] = []
        self._deadline_timer = PointTimer(self._async_timer)
        self._startup_timer = PointTimer(self._async_startup_done)
        super().__init__(subentry, store, settings)

    def _configure(self, subentry: ConfigSubentry) -> None:
        super()._configure(subentry)
        data = subentry.data
        # The state kind's entity, the threshold kind's value entity, or the
        # alert state kind's alert.
        self._source_entity: str | None = (
            data.get(CONF_ENTITY_ID) or data.get(CONF_ALERT) or None
        )
        self._target_state: str | None = data.get(CONF_TARGET_STATE)
        self._alert_states: list[str] = list(data.get(CONF_ALERT_STATES) or [])
        self._template: str | None = data.get(CONF_TEMPLATE)
        self._attribute: str | None = data.get(CONF_ATTRIBUTE) or None
        self._value_template: str | None = data.get(CONF_VALUE_TEMPLATE) or None
        self._minimum: str | None = data.get(CONF_MINIMUM) or None
        self._maximum: str | None = data.get(CONF_MAXIMUM) or None
        self._hysteresis = float(data.get(CONF_HYSTERESIS) or 0)
        self._on_template: str | None = data.get(CONF_ON_TEMPLATE) or None
        self._on_triggers: list[dict[str, Any]] = list(data.get(CONF_ON_TRIGGERS) or [])
        self._off_template: str | None = data.get(CONF_OFF_TEMPLATE) or None
        self._off_triggers: list[dict[str, Any]] = list(
            data.get(CONF_OFF_TRIGGERS) or []
        )
        self._sides = OnOffSides(
            on_template=self._on_template is not None,
            on_trigger=bool(self._on_triggers),
            off_template=self._off_template is not None,
            off_trigger=bool(self._off_triggers),
        )
        self._condition: str | None = data.get(CONF_CONDITION) or None
        self._delay_on = to_timedelta(data.get(CONF_DELAY_ON))
        self._delay_off = to_timedelta(data.get(CONF_DELAY_OFF))
        self._no_data_grace = to_timedelta(data.get(CONF_NO_DATA_GRACE))

    @property
    def subject_entity(self) -> str | None:
        """Return the explicit subject, or else the state, value, or alert entity."""
        return self._explicit_subject or self._source_entity

    @property
    def _timing(self) -> Timing:
        grace = self._no_data_grace
        return Timing(
            delay_on=self._delay_on or timedelta(0),
            delay_off=self._delay_off or timedelta(0),
            no_data_grace=self._settings.no_data_grace if grace is None else grace,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Add the condition's configuration and current evaluation."""
        runtime = self._runtime
        timing = self._timing
        attributes = super().extra_state_attributes
        if self._kind is AlertKind.STATE:
            attributes[ATTR_SOURCE_ENTITY] = self._source_entity
            attributes[ATTR_TARGET_STATE] = self._target_state
        elif self._kind is AlertKind.ALERT_STATE:
            attributes[ATTR_SOURCE_ENTITY] = self._source_entity
            attributes[ATTR_TARGET_STATES] = self._alert_states
        elif self._kind is AlertKind.THRESHOLD:
            reading = (
                self._results.get("main", (None, []))[0] if self._results else None
            )
            attributes |= {
                ATTR_SOURCE_ENTITY: self._source_entity,
                ATTR_ATTRIBUTE: self._attribute,
                ATTR_VALUE_TEMPLATE: self._value_template,
                ATTR_MINIMUM: self._minimum,
                ATTR_MAXIMUM: self._maximum,
                ATTR_HYSTERESIS: self._hysteresis,
                ATTR_VALUE: reading.value if isinstance(reading, Reading) else None,
            }
        elif self._kind is AlertKind.ON_OFF:
            attributes |= {
                ATTR_ON_TEMPLATE: self._on_template,
                ATTR_ON_TRIGGERS: self._on_triggers,
                ATTR_OFF_TEMPLATE: self._off_template,
                ATTR_OFF_TRIGGERS: self._off_triggers,
            }
        else:
            attributes[ATTR_TEMPLATE] = self._template
        attributes |= {
            ATTR_CONDITION: self._condition,
            ATTR_DELAY_ON: timing.delay_on.total_seconds(),
            ATTR_DELAY_OFF: timing.delay_off.total_seconds(),
            ATTR_NO_DATA_GRACE: timing.no_data_grace.total_seconds(),
            ATTR_NO_DATA_SINCE: runtime.no_data_since,
            ATTR_MISSING_INPUTS: runtime.missing_inputs,
            ATTR_DELAY_ON_UNTIL: runtime.delay_on_until,
            ATTR_DELAY_OFF_UNTIL: runtime.delay_off_until,
            ATTR_NO_DATA_GRACE_UNTIL: runtime.no_data_grace_until(timing),
        }
        return attributes

    @callback
    def _async_restored(self) -> None:
        """Count as having no data until the inputs report (spec §15.3).

        A disabled alert has nothing to wait for.
        """
        if not self._runtime.disabled:
            self._runtime.await_data(dt_util.utcnow())

    async def async_added_to_hass(self) -> None:
        """Start watching, after the startup delay if HA is starting."""
        await super().async_added_to_hass()
        startup_until: datetime | None = self.hass.data[DOMAIN].get(DATA_STARTUP_UNTIL)
        if startup_until is not None and dt_util.utcnow() < startup_until:
            self._startup_timer.at(self.hass, startup_until)
        else:
            self._async_inputs_started()

    @callback
    def _async_startup_done(self, _now: datetime) -> None:
        self._async_inputs_started()

    @callback
    def _async_inputs_started(self) -> None:
        """Start watching the condition, unless disabled or still starting up."""
        if not self._runtime.disabled and not self._startup_timer.pending:
            self._async_start_source()

    @callback
    def _async_inputs_stopped(self) -> None:
        self._async_stop_source()
        self._results = None

    async def async_will_remove_from_hass(self) -> None:
        """Stop watching the condition."""
        await super().async_will_remove_from_hass()
        self._startup_timer.cancel()
        self._async_stop_source()

    @callback
    def async_update_config(self, subentry: ConfigSubentry) -> None:
        """Apply an edited subentry: re-subscribe, and restart pending delays.

        The firing (if any) carries on if the new condition holds; otherwise
        delay_off runs from now.
        """
        self._async_stop_source()
        self._configure(subentry)
        self._runtime.delay_on_until = None
        self._runtime.delay_off_until = None
        super().async_update_config(subentry)
        self._async_inputs_started()

    @callback
    def async_settings_changed(self) -> None:
        """Re-evaluate: the default grace period may have changed."""
        super().async_settings_changed()
        self._async_evaluate()

    def _build_sources(self) -> dict[str, Source]:
        """Return the kind's sources, by name, plus the extra condition's."""
        sources: dict[str, Source] = {}
        if self._kind is AlertKind.STATE:
            assert self._source_entity is not None
            assert self._target_state is not None
            sources["main"] = StateSource(
                self.hass, self._source_entity, [self._target_state]
            )
        elif self._kind is AlertKind.ALERT_STATE:
            assert self._source_entity is not None
            sources["main"] = StateSource(
                self.hass, self._source_entity, self._alert_states
            )
        elif self._kind is AlertKind.THRESHOLD:
            value = self._value_template or value_template(
                str(self._source_entity), self._attribute
            )
            sources["main"] = ThresholdSource(
                self.hass,
                value,
                self._minimum,
                self._maximum,
                f"{self.entity_id} threshold",
            )
        elif self._kind is AlertKind.ON_OFF:
            for side, template in (
                ("on", self._on_template),
                ("off", self._off_template),
            ):
                if template is not None:
                    sources[side] = TemplateSource(
                        self.hass, template, f"{self.entity_id} {side} template"
                    )
        else:
            assert self._template is not None
            sources["main"] = TemplateSource(
                self.hass, self._template, f"{self.entity_id} template"
            )
        if self._condition:
            sources["condition"] = TemplateSource(
                self.hass, self._condition, f"{self.entity_id} condition"
            )
        return sources

    @callback
    def _async_start_source(self) -> None:
        sources = self._build_sources()
        self._sources = SourceSet(sources)
        self._results = None
        if self._kind is AlertKind.ON_OFF:
            for side, triggers in (
                ("on", self._on_triggers),
                ("off", self._off_triggers),
            ):
                if triggers:
                    watcher = TriggerWatcher(
                        self.hass,
                        triggers,
                        f"{self.entity_id} {side} trigger",
                        self._make_pulse(side),
                        self._async_trigger_failed,
                    )
                    self._watchers.append(watcher)
                    watcher.async_start(None)
        if sources:
            self._sources.async_start(self._async_sources_updated)
        else:
            # Triggers alone: there's nothing to wait for.
            self._async_sources_updated({})

    @callback
    def _async_stop_source(self) -> None:
        if self._sources is not None:
            self._sources.async_stop()
            self._sources = None
        for watcher in self._watchers:
            watcher.async_stop()
        self._watchers = []
        self._deadline_timer.cancel()

    @callback
    def _async_sources_updated(self, results: dict[str, tuple[Any, list[str]]]) -> None:
        # A threshold alert shows its value, which can change without the state.
        value_changed = self._kind is AlertKind.THRESHOLD and (
            self._results or {}
        ).get("main") != results.get("main")
        self._results = results
        self._async_evaluate(write=value_changed)

    def _make_pulse(
        self, side: str
    ) -> Callable[[dict[str, Any], Context | None], None]:
        @callback
        def _pulse(_trigger: dict[str, Any], _context: Context | None) -> None:
            """An on/off side's trigger fired: it counts if its template is true."""
            template = self._on_template if side == "on" else self._off_template
            results = self._results or {}
            if template is not None and results.get(side, (None, []))[0] is not True:
                return
            self._runtime.on_off_pulse(side)
            self._async_evaluate()

        return _pulse

    def _judge(
        self, results: dict[str, tuple[Any, list[str]]]
    ) -> tuple[bool | None, list[str]]:
        """Return the condition from the sources' results, and the missing inputs.

        The extra condition is ANDed in; either having no data means no data
        (spec §4.1, §4.4).
        """
        runtime = self._runtime
        if self._kind is AlertKind.ON_OFF:
            on, on_missing = results.get("on", (None, []))
            off, off_missing = results.get("off", (None, []))
            main = runtime.on_off_condition(self._sides, on, off)
            missing = off_missing if runtime.firing else on_missing
        elif self._kind is AlertKind.THRESHOLD:
            reading, missing = results["main"]
            main = (
                None
                if reading is None
                else threshold_holds(reading, self._hysteresis, runtime.firing)
            )
        else:
            main, missing = results["main"]
        if "condition" not in results:
            return main, missing if main is None else []
        condition, condition_missing = results["condition"]
        if main is None or condition is None:
            return None, sorted(
                set(missing if main is None else [])
                | set(condition_missing if condition is None else [])
            )
        return main and condition, []

    @callback
    def _async_timer(self, _now: datetime) -> None:
        self._async_evaluate()

    @callback
    def _async_evaluate(self, write: bool = False) -> None:
        """Apply the latest results, publish any changes, and set the next timer.

        write forces the state to be written, e.g. for a changed attribute.
        """
        if self._results is None or self._runtime.disabled:
            return
        # Changes here are the alert's own, not those of the last user action.
        self._context = None
        timing = self._timing
        before = self._runtime.to_dict()
        now = dt_util.utcnow()
        condition, missing = self._judge(self._results)
        was_missing = list(self._runtime.missing_inputs)
        changes = self._runtime.evaluate(condition, missing, now, timing)
        pre_acked = None
        if any(change is Change.FIRED for change, _ in changes):
            pre_acked = self._pre_ack_new_firing(now)
            self._runtime.plan_reminder(self._reminder_schedule, now)
            if self._kind is AlertKind.ON_OFF:
                self._runtime.on_off_fired()
        if self._kind is AlertKind.ON_OFF and any(
            change is Change.ENDED for change, _ in changes
        ):
            self._runtime.on_off_ended()

        self._deadline_timer.at(self.hass, self._runtime.next_deadline(timing))

        if changes or self._runtime.to_dict() != before:
            self._async_update_timers()
            self.async_write_ha_state()
            self._persist()
        elif write:
            self.async_write_ha_state()
        for change, transition in changes:
            if change is Change.FIRED:
                self._fire_event(
                    EVENT_FIRED,
                    transition.old_state,
                    {ATTR_FIRE_COUNT: transition.fire_count},
                )
                self._announce_pre_ack(pre_acked)
                if self._runtime.state is AlertState.ACTIVE:
                    self._async_notify_on()
            elif change is Change.ENDED:
                self._fire_event(
                    EVENT_ENDED, transition.old_state, _ended_data(transition)
                )
                self._async_notify_done(transition)
            elif change is Change.DATA_RESTORED:
                self._fire_event(
                    EVENT_DATA_RESTORED,
                    transition.old_state,
                    {ATTR_MISSING_INPUTS: was_missing},
                )
            else:
                self._fire_event(
                    EVENT_NO_DATA,
                    transition.old_state,
                    {ATTR_MISSING_INPUTS: self._runtime.missing_inputs},
                )


class EventAlertEntity(AlertEntity):
    """An alert fired by a trigger or a bus event, for a duration (spec §4.2).

    Both kinds share this engine: a bus event alert is a trigger alert with an event
    trigger (F23). The trigger's variables are the firing's fire data, available
    to message templates as trigger.
    """

    _unrecorded_attributes = AlertEntity._unrecorded_attributes | frozenset(
        {ATTR_TRIGGER_DATA, ATTR_TRIGGERS, ATTR_EVENT_DATA, ATTR_CONDITION}
    )

    def __init__(
        self, subentry: ConfigSubentry, store: AlertStore, settings: Settings
    ) -> None:
        """Initialize the alert from its subentry."""
        self._watcher: TriggerWatcher | None = None
        self._expiry_timer = PointTimer(self._async_expired)
        super().__init__(subentry, store, settings)

    def _configure(self, subentry: ConfigSubentry) -> None:
        super()._configure(subentry)
        data = subentry.data
        self._event_type: str | None = data.get(CONF_EVENT_TYPE)
        self._event_data: dict[str, Any] | None = data.get(CONF_EVENT_DATA) or None
        if self._kind is AlertKind.EVENT:
            assert self._event_type is not None
            self._triggers = bus_event_trigger(self._event_type, self._event_data)
        else:
            self._triggers = list(data[CONF_TRIGGERS])
        self._condition: str | None = data.get(CONF_CONDITION) or None
        self._own_duration = to_timedelta(data.get(CONF_DURATION))

    @property
    def _duration(self) -> timedelta:
        """Return the alert's duration: its own, or its priority's default."""
        if self._own_duration:
            return self._own_duration
        return self._settings.event_durations[self._priority]

    @property
    def _reminder_schedule(self) -> tuple[float, ...]:
        """Return no reminders unless the duration outlasts the first interval.

        Short event alerts just fire and expire (spec §9.6).
        """
        schedule = super()._reminder_schedule
        if schedule and self._duration <= timedelta(minutes=schedule[0]):
            return ()
        return schedule

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Add the trigger configuration, the duration, and the latest trigger."""
        attributes = super().extra_state_attributes
        if self._kind is AlertKind.EVENT:
            attributes[ATTR_EVENT_TYPE] = self._event_type
            attributes[ATTR_EVENT_DATA] = self._event_data
        else:
            attributes[ATTR_TRIGGERS] = self._triggers
        attributes |= {
            ATTR_CONDITION: self._condition,
            ATTR_DURATION: self._duration.total_seconds(),
            ATTR_EVENT_EXPIRES: self._runtime.event_expires,
            ATTR_TRIGGER_DATA: self._runtime.fire_data,
        }
        return attributes

    async def async_added_to_hass(self) -> None:
        """Resume or end a restored firing, and start watching the triggers."""
        await super().async_added_to_hass()
        runtime = self._runtime
        if runtime.firing and runtime.event_expires is None:
            # Shouldn't happen, but a firing must always run out.
            runtime.event_expires = (
                runtime.last_fired or dt_util.utcnow()
            ) + self._duration
        # A duration that ran out while Home Assistant was down ends now, with the
        # done notification (spec §15.1).
        now = dt_util.utcnow()
        if runtime.event_expires is not None and runtime.event_expires <= now:
            self._async_expired(now)
        else:
            self._async_update_timers()
        self._async_inputs_started()

    async def async_will_remove_from_hass(self) -> None:
        """Stop watching the triggers, and the duration."""
        await super().async_will_remove_from_hass()
        self._async_stop_watcher()

    @callback
    def async_update_config(self, subentry: ConfigSubentry) -> None:
        """Apply an edited subentry, re-attaching the triggers.

        A running firing keeps its expiry: a new duration applies from the next
        fire.
        """
        self._async_stop_watcher()
        super().async_update_config(subentry)
        self._async_inputs_started()

    @callback
    def _async_inputs_started(self) -> None:
        """Attach the triggers, unless disabled."""
        if not self._runtime.disabled:
            self._async_start_watcher()

    @callback
    def _async_inputs_stopped(self) -> None:
        self._async_stop_watcher()

    @callback
    def _async_start_watcher(self) -> None:
        self._attr_available = True
        self._watcher = TriggerWatcher(
            self.hass,
            self._triggers,
            f"{self.entity_id} trigger",
            self._async_triggered,
            self._async_trigger_failed,
        )
        self._watcher.async_start(self.hass.data[DOMAIN].get(DATA_STARTUP_UNTIL))

    @callback
    def _async_stop_watcher(self) -> None:
        if self._watcher is not None:
            self._watcher.async_stop()
            self._watcher = None

    @callback
    def _async_triggered(
        self, trigger: dict[str, Any], context: Context | None
    ) -> None:
        """Fire, or fire again, if the condition allows."""
        if self._runtime.disabled:
            return
        if self._condition and not self._condition_allows(trigger):
            _LOGGER.debug("%s: triggered, but the condition is false", self.entity_id)
            return
        # The firing is the alert's own doing, not the last user action's.
        self._context = None
        now = dt_util.utcnow()
        transition = self._runtime.fire_event(now, trigger, self._duration)
        pre_acked = None
        if transition.fire_count == 1:
            pre_acked = self._pre_ack_new_firing(now)
            self._runtime.plan_reminder(self._reminder_schedule, now)
        self._apply(
            EVENT_FIRED,
            transition,
            {ATTR_FIRE_COUNT: transition.fire_count, ATTR_TRIGGER_DATA: trigger},
        )
        self._announce_pre_ack(pre_acked)
        # As for manual alerts, firing again only speaks up while unacknowledged.
        if self._runtime.state is AlertState.ACTIVE:
            self._async_notify_on()

    def _condition_allows(self, trigger: dict[str, Any]) -> bool:
        """Judge the condition at the moment of the trigger.

        A condition with no data doesn't stop the alert: a broken condition must
        never silence it (spec §4.2).
        """
        assert self._condition is not None
        try:
            result: Any = Template(self._condition, self.hass).async_render(
                {"trigger": trigger}
            )
        except TemplateError as err:
            result = err
        value = template_truth(result)
        if value is None:
            _LOGGER.warning(
                "%s: condition has no data (result: %r); firing anyway",
                self.entity_id,
                result,
            )
            return True
        return value

    @callback
    def _async_update_timers(self) -> None:
        """Add the duration's timer."""
        super()._async_update_timers()
        self._expiry_timer.at(self.hass, self._runtime.event_expires)

    @callback
    def _async_cancel_timers(self) -> None:
        super()._async_cancel_timers()
        self._expiry_timer.cancel()

    @callback
    def _async_expired(self, _now: datetime) -> None:
        """End the firing: its duration has run out.

        It ended at its expiry, even if that passed while Home Assistant was down.
        """
        self._context = None
        ended = self._runtime.event_expires or dt_util.utcnow()
        if (transition := self._runtime.end(ended, EndReason.RESOLVED)) is None:
            return
        self._apply(EVENT_ENDED, transition, _ended_data(transition))
        self._async_notify_done(transition)


def _ended_data(transition: Transition) -> dict[str, Any]:
    return {
        ATTR_FIRE_COUNT: transition.fire_count,
        ATTR_DURATION_SECONDS: transition.duration_seconds,
        ATTR_REASON: transition.reason,
    }
