"""Constants for the Alert Redux integration."""

from __future__ import annotations

from datetime import timedelta
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
DATA_SETTINGS = "settings"
DATA_ADD_ENTITIES = "add_entities"
DATA_ENTITIES = "entities"
DATA_SUBENTRIES = "subentries"
DATA_OPTIONS = "options"
DATA_STARTUP_UNTIL = "startup_until"
DATA_LABEL = "label"
DATA_NOTIFIER = "notifier"
DATA_GROUPS = "groups"

# The label applied to every alert (spec §11.5).
ALERTS_LABEL_NAME = "Alert Redux"
ALERTS_LABEL_ICON = "mdi:alert-rhombus"
ALERTS_LABEL_DESCRIPTION = "Every Alert Redux alert. New alerts get it automatically."

# Persistent alert state (spec §15.1).
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 1
STORAGE_SAVE_DELAY = 1  # seconds
# The notifier module's own store: its retry queue (spec §15.2).
NOTIFIER_STORAGE_KEY = f"{DOMAIN}.notifier"


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
    NO_DATA = "no_data"


class AlertKind(StrEnum):
    """Alert kinds (spec §4); more are added in later phases."""

    MANUAL = "manual"
    STATE = "state"
    ON_OFF = "on_off"
    THRESHOLD = "threshold"
    TEMPLATE = "template"
    TRIGGER = "trigger"
    # A bus event alert: a trigger alert with an event trigger (spec §4.2, F23).
    EVENT = "event"


CONDITION_KINDS = frozenset(
    {AlertKind.STATE, AlertKind.ON_OFF, AlertKind.THRESHOLD, AlertKind.TEMPLATE}
)
EVENT_KINDS = frozenset({AlertKind.TRIGGER, AlertKind.EVENT})


class EndReason(StrEnum):
    """Why a firing ended, carried by the ended event."""

    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    NO_DATA = "no_data"


# Config subentry types.
SUBENTRY_ALERT = "alert"
SUBENTRY_NOTIFIER_GROUP = "notifier_group"

# Alert subentry data keys.
CONF_KIND = "kind"
CONF_PRIORITY = "priority"
CONF_ICON = "icon"
CONF_ACKNOWLEDGEABLE = "acknowledgeable"
CONF_USER_DISMISSABLE = "user_dismissable"
CONF_SUBJECT_ENTITY = "subject_entity"
CONF_ENTITY_ID = "entity_id"
CONF_TARGET_STATE = "target_state"
CONF_TEMPLATE = "template"
CONF_CONDITION = "condition"
CONF_DELAY_ON = "delay_on"
CONF_DELAY_OFF = "delay_off"
CONF_NO_DATA_GRACE = "no_data_grace"
CONF_TRIGGERS = "triggers"
# Threshold alerts: the value (an entity, with an optional attribute, or a
# template), the limits (templates), and the hysteresis.
CONF_ATTRIBUTE = "attribute"
CONF_VALUE_TEMPLATE = "value_template"
CONF_MINIMUM = "minimum"
CONF_MAXIMUM = "maximum"
CONF_HYSTERESIS = "hysteresis"
# On/off alerts: each side is a template, triggers, or both.
CONF_ON_TEMPLATE = "on_template"
CONF_ON_TRIGGERS = "on_triggers"
CONF_OFF_TEMPLATE = "off_template"
CONF_OFF_TRIGGERS = "off_triggers"
CONF_EVENT_TYPE = "event_type"
CONF_EVENT_DATA = "event_data"
CONF_DURATION = "duration"
CONF_MESSAGE = "message"
CONF_DISPLAY_MESSAGE = "display_message"
CONF_REMINDER_MESSAGE = "reminder_message"
CONF_DONE_MESSAGE = "done_message"
# Absent: use the default groups; a list (possibly empty): exactly those groups.
CONF_NOTIFIER_GROUPS = "notifier_groups"
# Absent: use the default schedule; a list (possibly empty): minutes between reminders.
CONF_REMINDER_SCHEDULE = "reminder_schedule"
# Form-only fields: the "use the default" checkboxes, and the notifications section.
CONF_USE_DEFAULT_GROUPS = "use_default_groups"
CONF_USE_DEFAULT_REMINDERS = "use_default_reminders"
SECTION_NOTIFICATIONS = "notifications"

# Notifier group subentry data keys (the notifier module's own keys).
CONF_LOUD = "loud"
CONF_ENTITIES = "entities"
CONF_ACTIONS = "actions"
CONF_PERSISTENT = "persistent"
CONF_ACTION = "action"
CONF_DATA = "data"
CONF_TARGET = "target"

# Messages (spec §9.5).
DEFAULT_ON_MESSAGE = "{{ name }} is firing."
DEFAULT_REMINDER_MESSAGE = "{{ name }} is still firing ({{ duration }})."
DEFAULT_DONE_MESSAGE = "{{ name }} stopped firing after {{ duration }}."
DEFAULT_DONE_NO_DATA_MESSAGE = (
    "{{ name }} lost its data; stopped firing after {{ duration }}."
)

# Config entry options: the global defaults (spec §12.1).
CONF_STARTUP_DELAY = "startup_delay"
DEFAULT_NO_DATA_GRACE = timedelta(minutes=10)
DEFAULT_STARTUP_DELAY = timedelta(0)
CONF_DEFAULT_GROUPS = "default_groups"
CONF_DEFAULT_REMINDER_SCHEDULE = "default_reminder_schedule"
DEFAULT_REMINDER_SCHEDULE: tuple[float, ...] = (10, 20, 30, 60)
CONF_FALLBACK_GROUP = "fallback_group"
CONF_RETRY_TIMEOUT = "retry_timeout"
DEFAULT_RETRY_TIMEOUT = timedelta(minutes=5)
# The snooze-end reminder rule's window (spec §6.2).
CONF_SNOOZE_REMINDER_WINDOW = "snooze_reminder_window"
DEFAULT_SNOOZE_REMINDER_WINDOW = timedelta(minutes=5)
# Event alerts' default durations, by priority (spec §4.2, §5): a mapping of
# priority to a duration selector's dict. The options form shows it as a section.
CONF_EVENT_DURATIONS = "event_durations"
DEFAULT_EVENT_DURATIONS: dict[Priority, timedelta] = {
    Priority.EMERGENCY: timedelta(minutes=60),
    Priority.CRITICAL: timedelta(minutes=30),
    Priority.WARNING: timedelta(minutes=15),
    Priority.NOTICE: timedelta(minutes=10),
    Priority.INFORMATIONAL: timedelta(minutes=5),
}

# Repairs issues.
ISSUE_DEFAULT_GROUPS_UNSET = "default_groups_unset"

# Actions (spec §16).
SERVICE_FIRE = "fire"
SERVICE_DISMISS = "dismiss"
SERVICE_ACK = "ack"
SERVICE_UNACK = "unack"
SERVICE_SNOOZE = "snooze"

ATTR_DATA = "data"

# Events (spec §11.3).
EVENT_FIRED = f"{DOMAIN}_fired"
EVENT_ENDED = f"{DOMAIN}_ended"
EVENT_ACKED = f"{DOMAIN}_acked"
EVENT_UNACKED = f"{DOMAIN}_unacked"
EVENT_SNOOZED = f"{DOMAIN}_snoozed"
EVENT_SNOOZE_EXPIRED = f"{DOMAIN}_snooze_expired"
EVENT_NO_DATA = f"{DOMAIN}_no_data"
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
ATTR_SNOOZED_UNTIL = "snoozed_until"
ATTR_LAST_SNOOZED = "last_snoozed"
ATTR_LAST_SNOOZED_BY = "last_snoozed_by"
ATTR_NAME = "name"
ATTR_OLD_STATE = "old_state"
ATTR_NEW_STATE = "new_state"
ATTR_USER_ID = "user_id"
ATTR_DURATION_SECONDS = "duration_seconds"
ATTR_REASON = "reason"
ATTR_SUBJECT_ENTITY = "subject_entity"
ATTR_SOURCE_ENTITY = "source_entity"
ATTR_TARGET_STATE = "target_state"
ATTR_TEMPLATE = "template"
ATTR_CONDITION = "condition"
ATTR_DELAY_ON = "delay_on"
ATTR_DELAY_OFF = "delay_off"
ATTR_NO_DATA_GRACE = "no_data_grace"
ATTR_NO_DATA_SINCE = "no_data_since"
ATTR_MISSING_INPUTS = "missing_inputs"
ATTR_DELAY_ON_UNTIL = "delay_on_until"
ATTR_DELAY_OFF_UNTIL = "delay_off_until"
ATTR_NO_DATA_GRACE_UNTIL = "no_data_grace_until"
ATTR_MESSAGE = "message"
ATTR_DISPLAY_MESSAGE = "display_message"
ATTR_NOTIFIER_GROUPS = "notifier_groups"
ATTR_REMINDER_SCHEDULE = "reminder_schedule"
ATTR_NEXT_REMINDER = "next_reminder"
ATTR_DURATION = "duration"
ATTR_EVENT_EXPIRES = "event_expires"
ATTR_TRIGGER_DATA = "trigger_data"
ATTR_TRIGGERS = "triggers"
ATTR_EVENT_TYPE = "event_type"
ATTR_EVENT_DATA = "event_data"
ATTR_ATTRIBUTE = "attribute"
ATTR_VALUE_TEMPLATE = "value_template"
ATTR_MINIMUM = "minimum"
ATTR_MAXIMUM = "maximum"
ATTR_HYSTERESIS = "hysteresis"
ATTR_VALUE = "value"
ATTR_ON_TEMPLATE = "on_template"
ATTR_ON_TRIGGERS = "on_triggers"
ATTR_OFF_TEMPLATE = "off_template"
ATTR_OFF_TRIGGERS = "off_triggers"
