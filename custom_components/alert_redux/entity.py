"""The alert entity (spec §7, §11)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACKNOWLEDGEABLE,
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
    ATTR_NAME,
    ATTR_NEW_STATE,
    ATTR_OLD_STATE,
    ATTR_PRIORITY,
    ATTR_REASON,
    ATTR_USER_DISMISSABLE,
    ATTR_USER_ID,
    CONF_ACKNOWLEDGEABLE,
    CONF_ICON,
    CONF_KIND,
    CONF_PRIORITY,
    CONF_USER_DISMISSABLE,
    DEFAULT_PRIORITY_ICONS,
    DOMAIN,
    EVENT_ACKED,
    EVENT_CREATED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_UNACKED,
    AlertKind,
    EndReason,
    Priority,
)
from .model import AlertRuntime, Transition
from .store import AlertStore

_LOGGER = logging.getLogger(__name__)


class AlertEntity(Entity):
    """One configured alert."""

    _attr_should_poll = False
    _attr_translation_key = "alert"
    _unrecorded_attributes = frozenset({ATTR_FIRE_DATA})

    def __init__(self, subentry: ConfigSubentry, store: AlertStore) -> None:
        """Initialize the alert from its subentry."""
        data = subentry.data
        self._store = store
        self._kind = AlertKind(data[CONF_KIND])
        self._priority = Priority(data[CONF_PRIORITY])
        self._acknowledgeable: bool = data[CONF_ACKNOWLEDGEABLE]
        self._user_dismissable: bool = data.get(CONF_USER_DISMISSABLE, False)
        self._runtime = AlertRuntime()
        self._attr_unique_id = subentry.subentry_id
        self._attr_name = subentry.title
        self._attr_icon = data.get(CONF_ICON) or DEFAULT_PRIORITY_ICONS[self._priority]

    @property
    def state(self) -> str:
        """Return the alert's state."""
        return self._runtime.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the alert's state details and configuration (spec §11.1)."""
        runtime = self._runtime
        return {
            ATTR_KIND: self._kind,
            ATTR_PRIORITY: self._priority,
            ATTR_ACKNOWLEDGEABLE: self._acknowledgeable,
            ATTR_USER_DISMISSABLE: self._user_dismissable,
            ATTR_FIRING_SINCE: runtime.firing_since,
            ATTR_LAST_FIRED: runtime.last_fired,
            ATTR_LAST_ENDED: runtime.last_ended,
            ATTR_FIRE_COUNT: runtime.fire_count,
            ATTR_FIRE_DATA: runtime.fire_data,
            ATTR_LAST_ACKED: runtime.last_acked,
            ATTR_LAST_ACKED_BY: runtime.last_acked_by,
            ATTR_LAST_UNACKED: runtime.last_unacked,
            ATTR_LAST_UNACKED_BY: runtime.last_unacked_by,
        }

    async def async_added_to_hass(self) -> None:
        """Restore the persisted state, or announce a new alert."""
        assert self.unique_id is not None
        record = self._store.get_alert(self.unique_id)
        if record is not None:
            self._runtime = AlertRuntime.from_dict(record["runtime"])
        self._persist()
        if record is None:
            self._fire_event(EVENT_CREATED, None)

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
        self._apply(
            EVENT_ENDED,
            transition,
            {
                ATTR_FIRE_COUNT: transition.fire_count,
                ATTR_DURATION_SECONDS: transition.duration_seconds,
                ATTR_REASON: transition.reason,
            },
        )

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
