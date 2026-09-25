"""The alert entities (spec §7, §11)."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACKNOWLEDGEABLE,
    ATTR_CONDITION,
    ATTR_DELAY_OFF,
    ATTR_DELAY_OFF_UNTIL,
    ATTR_DELAY_ON,
    ATTR_DELAY_ON_UNTIL,
    ATTR_DISPLAY_MESSAGE,
    ATTR_DURATION_SECONDS,
    ATTR_FIRE_COUNT,
    ATTR_FIRE_DATA,
    ATTR_FIRING_SINCE,
    ATTR_KIND,
    ATTR_LAST_ACKED,
    ATTR_LAST_ACKED_BY,
    ATTR_LAST_ENDED,
    ATTR_LAST_FIRED,
    ATTR_LAST_UNACKED,
    ATTR_LAST_UNACKED_BY,
    ATTR_MESSAGE,
    ATTR_MISSING_INPUTS,
    ATTR_NAME,
    ATTR_NEW_STATE,
    ATTR_NO_DATA_GRACE,
    ATTR_NO_DATA_GRACE_UNTIL,
    ATTR_NO_DATA_SINCE,
    ATTR_OLD_STATE,
    ATTR_PRIORITY,
    ATTR_REASON,
    ATTR_SOURCE_ENTITY,
    ATTR_SUBJECT_ENTITY,
    ATTR_TARGET_STATE,
    ATTR_TEMPLATE,
    ATTR_USER_DISMISSABLE,
    ATTR_USER_ID,
    CONDITION_KINDS,
    CONF_ACKNOWLEDGEABLE,
    CONF_CONDITION,
    CONF_DELAY_OFF,
    CONF_DELAY_ON,
    CONF_DISPLAY_MESSAGE,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_KIND,
    CONF_MESSAGE,
    CONF_NO_DATA_GRACE,
    CONF_PRIORITY,
    CONF_SUBJECT_ENTITY,
    CONF_TARGET_STATE,
    CONF_TEMPLATE,
    CONF_USER_DISMISSABLE,
    DATA_LABEL,
    DATA_STARTUP_UNTIL,
    DEFAULT_PRIORITY_ICONS,
    DOMAIN,
    EVENT_ACKED,
    EVENT_CREATED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_NO_DATA,
    EVENT_UNACKED,
    AlertKind,
    EndReason,
    Priority,
)
from .labels import async_apply_label
from .messages import Messages, MessageTracker, message_context
from .model import AlertRuntime, Change, Settings, Timing, Transition, to_timedelta
from .sources import AndSource, Source, StateSource, TemplateSource
from .store import AlertStore

_LOGGER = logging.getLogger(__name__)


def create_alert_entity(
    subentry: ConfigSubentry, store: AlertStore, settings: Settings
) -> AlertEntity:
    """Return the entity for an alert subentry, according to its kind."""
    if AlertKind(subentry.data[CONF_KIND]) in CONDITION_KINDS:
        return ConditionAlertEntity(subentry, store, settings)
    return AlertEntity(subentry, store, settings)


class AlertEntity(Entity):
    """One configured alert; on its own, a manual alert (spec §4.3)."""

    _attr_should_poll = False
    _attr_translation_key = "alert"
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
        self._attr_name = subentry.title
        self._attr_icon = data.get(CONF_ICON) or DEFAULT_PRIORITY_ICONS[self._priority]

    @property
    def subject_entity(self) -> str | None:
        """Return the entity the alert is about, if any (spec §9.5)."""
        return self._explicit_subject

    @property
    def state(self) -> str:
        """Return the alert's state."""
        return self._runtime.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the alert's state details and configuration (spec §11.1)."""
        runtime = self._runtime
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
            ATTR_MESSAGE: self._messages.message if self._messages else None,
            ATTR_DISPLAY_MESSAGE: (
                self._messages.display_message if self._messages else None
            ),
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
        self._persist()
        if record is None:
            self._fire_event(EVENT_CREATED, None)

    async def async_will_remove_from_hass(self) -> None:
        """Stop rendering the messages."""
        self._async_stop_messages()

    @callback
    def async_write_ha_state(self) -> None:
        """Bring the rendered messages up to date, then write the state."""
        self._async_sync_messages()
        super().async_write_ha_state()

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
            message_context(
                self.hass,
                name=str(self.name),
                entity_id=self.entity_id,
                priority=self._priority,
                subject_entity=self.subject_entity,
                fire_count=runtime.fire_count,
                fire_data=runtime.fire_data,
                reason="on",
            ),
            f"{self.entity_id} message",
            self._async_messages_updated,
        )
        self._messages = self._message_tracker.async_start()

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
    def async_update_config(self, subentry: ConfigSubentry) -> None:
        """Apply an edited subentry in place, keeping the alert's state."""
        self._configure(subentry)
        self.async_write_ha_state()
        self._persist()

    @callback
    def async_settings_changed(self) -> None:
        """React to a change in the global defaults."""

    async def async_fire(self, data: dict[str, Any] | None = None) -> None:
        """Fire a manual alert, or fire it again if it is already firing."""
        self._require_manual()
        transition = self._runtime.fire(dt_util.utcnow(), data)
        self._apply(
            EVENT_FIRED,
            transition,
            {ATTR_FIRE_COUNT: transition.fire_count, ATTR_FIRE_DATA: data},
        )

    async def async_dismiss(self) -> None:
        """Dismiss a firing manual alert."""
        self._require_manual()
        if (
            transition := self._runtime.end(dt_util.utcnow(), EndReason.DISMISSED)
        ) is None:
            _LOGGER.debug("%s: dismiss ignored; not firing", self.entity_id)
            return
        self._apply(EVENT_ENDED, transition, _ended_data(transition))

    async def async_ack(self) -> None:
        """Acknowledge the alert."""
        if not self._acknowledgeable:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_acknowledgeable",
                translation_placeholders={"entity_id": self.entity_id},
            )
        if (transition := self._runtime.ack(dt_util.utcnow(), self._user_id)) is None:
            _LOGGER.debug("%s: ack ignored; not active", self.entity_id)
            return
        self._apply(EVENT_ACKED, transition)

    async def async_unack(self) -> None:
        """Remove the alert's acknowledgement."""
        if (
            transition := self._runtime.unack(dt_util.utcnow(), self._user_id)
        ) is None:
            _LOGGER.debug("%s: unack ignored; not acknowledged", self.entity_id)
            return
        self._apply(EVENT_UNACKED, transition)

    @property
    def _user_id(self) -> str | None:
        """Return the user behind the action being handled, if any."""
        return self._context.user_id if self._context else None

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
        self.async_write_ha_state()
        self._persist()
        self._fire_event(event_type, transition.old_state, extra)

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

    A source reports the condition, or that it has no data; the runtime applies the
    delays and the no-data grace period, and this entity keeps one timer for the
    runtime's next deadline.
    """

    _unrecorded_attributes = AlertEntity._unrecorded_attributes | frozenset(
        {ATTR_TEMPLATE, ATTR_CONDITION}
    )

    def __init__(
        self, subentry: ConfigSubentry, store: AlertStore, settings: Settings
    ) -> None:
        """Initialize the alert from its subentry."""
        self._source: Source | None = None
        self._result: tuple[bool | None, list[str]] | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._unsub_startup: CALLBACK_TYPE | None = None
        super().__init__(subentry, store, settings)

    def _configure(self, subentry: ConfigSubentry) -> None:
        super()._configure(subentry)
        data = subentry.data
        self._source_entity: str | None = data.get(CONF_ENTITY_ID)
        self._target_state: str | None = data.get(CONF_TARGET_STATE)
        self._template: str | None = data.get(CONF_TEMPLATE)
        self._condition: str | None = data.get(CONF_CONDITION) or None
        self._delay_on = to_timedelta(data.get(CONF_DELAY_ON))
        self._delay_off = to_timedelta(data.get(CONF_DELAY_OFF))
        self._no_data_grace = to_timedelta(data.get(CONF_NO_DATA_GRACE))

    @property
    def subject_entity(self) -> str | None:
        """Return the explicit subject, or else the state kind's entity."""
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
        """Count as having no data until the inputs report (spec §15.3)."""
        self._runtime.await_data(dt_util.utcnow())

    async def async_added_to_hass(self) -> None:
        """Start watching, after the startup delay if HA is starting."""
        await super().async_added_to_hass()
        startup_until: datetime | None = self.hass.data[DOMAIN].get(DATA_STARTUP_UNTIL)
        if startup_until is not None and dt_util.utcnow() < startup_until:
            self._unsub_startup = async_track_point_in_utc_time(
                self.hass, self._async_startup_done, startup_until
            )
        else:
            self._async_start_source()

    @callback
    def _async_startup_done(self, _now: datetime) -> None:
        self._unsub_startup = None
        self._async_start_source()

    async def async_will_remove_from_hass(self) -> None:
        """Stop watching the condition."""
        await super().async_will_remove_from_hass()
        if self._unsub_startup is not None:
            self._unsub_startup()
            self._unsub_startup = None
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
        if self._unsub_startup is None:
            self._async_start_source()

    @callback
    def async_settings_changed(self) -> None:
        """Re-evaluate: the default grace period may have changed."""
        self._async_evaluate()
        self.async_write_ha_state()

    @callback
    def _async_start_source(self) -> None:
        main: Source
        if self._kind is AlertKind.STATE:
            assert self._source_entity is not None
            assert self._target_state is not None
            main = StateSource(self.hass, self._source_entity, self._target_state)
        else:
            assert self._template is not None
            main = TemplateSource(
                self.hass, self._template, f"{self.entity_id} template"
            )
        if self._condition:
            main = AndSource(
                self.hass,
                main,
                TemplateSource(
                    self.hass, self._condition, f"{self.entity_id} condition"
                ),
            )
        self._source = main
        self._result = None
        main.async_start(self._async_source_updated)

    @callback
    def _async_stop_source(self) -> None:
        if self._source is not None:
            self._source.async_stop()
            self._source = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_source_updated(
        self, result: bool | None, missing_inputs: list[str]
    ) -> None:
        self._result = (result, missing_inputs)
        self._async_evaluate()

    @callback
    def _async_timer(self, _now: datetime) -> None:
        self._unsub_timer = None
        self._async_evaluate()

    @callback
    def _async_evaluate(self) -> None:
        """Apply the latest result, publish any changes, and set the next timer."""
        if self._result is None:
            return
        # Changes here are the alert's own, not those of the last user action.
        self._context = None
        timing = self._timing
        before = self._runtime.to_dict()
        changes = self._runtime.evaluate(*self._result, dt_util.utcnow(), timing)

        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        if (deadline := self._runtime.next_deadline(timing)) is not None:
            self._unsub_timer = async_track_point_in_utc_time(
                self.hass, self._async_timer, deadline
            )

        if changes or self._runtime.to_dict() != before:
            self.async_write_ha_state()
            self._persist()
        for change, transition in changes:
            if change is Change.FIRED:
                self._fire_event(
                    EVENT_FIRED,
                    transition.old_state,
                    {ATTR_FIRE_COUNT: transition.fire_count},
                )
            elif change is Change.ENDED:
                self._fire_event(
                    EVENT_ENDED, transition.old_state, _ended_data(transition)
                )
            else:
                self._fire_event(
                    EVENT_NO_DATA,
                    transition.old_state,
                    {ATTR_MISSING_INPUTS: self._runtime.missing_inputs},
                )


def _ended_data(transition: Transition) -> dict[str, Any]:
    return {
        ATTR_FIRE_COUNT: transition.fire_count,
        ATTR_DURATION_SECONDS: transition.duration_seconds,
        ATTR_REASON: transition.reason,
    }
