"""Constants for the Alert Redux integration."""

from __future__ import annotations

from enum import StrEnum

DOMAIN = "alert_redux"

# The bundled Lovelace card(s). The bundle is built from frontend/ at the repo root
# and committed under custom_components/alert_redux/frontend/ so that a plain HACS
# install ships it; the integration serves it and registers it as a resource.
CARD_FILENAME = "alert-redux-card.js"
CARD_URL_BASE = f"/{DOMAIN}/frontend"
CARD_URL = f"{CARD_URL_BASE}/{CARD_FILENAME}"

# hass.data[DOMAIN] keys.
DATA_COMPONENT = "component"
DATA_STORE = "store"

# Persistent alert state (spec §15.1).
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 1
STORAGE_SAVE_DELAY = 1  # seconds


class Priority(StrEnum):
    """Alert priority, highest first (spec §5)."""

    EMERGENCY = "emergency"
    CRITICAL = "critical"
    WARNING = "warning"
    NOTICE = "notice"
    INFORMATIONAL = "informational"

    @property
    def rank(self) -> int:
        """Return 0 for the highest priority, increasing as priority falls."""
        return list(Priority).index(self)


DEFAULT_PRIORITY_ICONS: dict[Priority, str] = {
    Priority.EMERGENCY: "mdi:alarm-light",
    Priority.CRITICAL: "mdi:alert-octagon",
    Priority.WARNING: "mdi:alert",
    Priority.NOTICE: "mdi:alert-circle-outline",
    Priority.INFORMATIONAL: "mdi:information-outline",
}


class AlertState(StrEnum):
    """Alert entity states (spec §7.1)."""

    IDLE = "idle"
    ACTIVE = "active"
    ACK = "ack"


class AlertKind(StrEnum):
    """Alert kinds (spec §4); more are added in later phases."""

    MANUAL = "manual"


# Config subentry types.
SUBENTRY_ALERT = "alert"

# Alert subentry data keys.
CONF_KIND = "kind"
CONF_PRIORITY = "priority"
CONF_ICON = "icon"
CONF_ACKNOWLEDGEABLE = "acknowledgeable"
CONF_USER_DISMISSABLE = "user_dismissable"

# Actions (spec §16).
SERVICE_FIRE = "fire"
SERVICE_DISMISS = "dismiss"
SERVICE_ACK = "ack"
SERVICE_UNACK = "unack"

ATTR_DATA = "data"

# Events (spec §11.3).
EVENT_FIRED = f"{DOMAIN}_fired"
EVENT_ENDED = f"{DOMAIN}_ended"
EVENT_ACKED = f"{DOMAIN}_acked"
EVENT_UNACKED = f"{DOMAIN}_unacked"
EVENT_CREATED = f"{DOMAIN}_created"
EVENT_DELETED = f"{DOMAIN}_deleted"

# Entity attributes and event data (spec §11.1, §11.3).
ATTR_KIND = "kind"
ATTR_PRIORITY = "priority"
ATTR_ACKNOWLEDGEABLE = "acknowledgeable"
ATTR_USER_DISMISSABLE = "user_dismissable"
ATTR_FIRING_SINCE = "firing_since"
ATTR_LAST_FIRED = "last_fired"
ATTR_LAST_ENDED = "last_ended"
ATTR_FIRE_COUNT = "fire_count"
ATTR_FIRE_DATA = "fire_data"
ATTR_LAST_ACKED = "last_acked"
ATTR_LAST_ACKED_BY = "last_acked_by"
ATTR_LAST_UNACKED = "last_unacked"
ATTR_LAST_UNACKED_BY = "last_unacked_by"
ATTR_NAME = "name"
ATTR_OLD_STATE = "old_state"
ATTR_NEW_STATE = "new_state"
ATTR_USER_ID = "user_id"
ATTR_DURATION_SECONDS = "duration_seconds"
