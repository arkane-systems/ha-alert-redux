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
DATA_SUPERSESSION = "supersession"
DATA_SUMMARY = "summary"

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
    DISABLED = "disabled"


class AlertKind(StrEnum):
    """Alert kinds (spec §4); more are added in later phases."""

    MANUAL = "manual"
    STATE = "state"
    ON_OFF = "on_off"
    THRESHOLD = "threshold"
    TEMPLATE = "template"
    # Another alert has been in a given state for a while (spec §4.1, F24).
    ALERT_STATE = "alert_state"
    TRIGGER = "trigger"
    # A bus event alert: a trigger alert with an event trigger (spec §4.2, F23).
    EVENT = "event"


CONDITION_KINDS = frozenset(
    {
        AlertKind.STATE,
        AlertKind.ON_OFF,
        AlertKind.THRESHOLD,
        AlertKind.TEMPLATE,
        AlertKind.ALERT_STATE,
    }
)
EVENT_KINDS = frozenset({AlertKind.TRIGGER, AlertKind.EVENT})


class EndReason(StrEnum):
    """Why a firing ended, carried by the ended event."""

    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    NO_DATA = "no_data"
    DISABLED = "disabled"


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
# Alert state alerts: the watched alert's entity ID, and the states that count.
CONF_ALERT = "alert"
CONF_ALERT_STATES = "alert_states"
# The alerts this one supersedes (spec §8): a list of relationships, each a
# mapping with the superseded alert's entity ID under CONF_ALERT.
CONF_SUPERSEDES = "supersedes"
# Each relationship's propagation (spec §8.2), and the snooze's duration.
CONF_PROPAGATION = "propagation"
CONF_SNOOZE_DURATION = "snooze_duration"


class Propagation(StrEnum):
    """What acknowledging a superseded alert does to its superseder (spec §8.2)."""

    NONE = "none"
    ACKNOWLEDGE = "acknowledge"
    SNOOZE = "snooze"


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
SECTION_SUPERSESSION = "supersession"

# Notifier group subentry data keys (the notifier module's own keys).
CONF_LOUD = "loud"
CONF_ENTITIES = "entities"
CONF_ACTIONS = "actions"
CONF_PERSISTENT = "persistent"
CONF_ACTION = "action"
CONF_DATA = "data"
CONF_TARGET = "target"
# Replacing and clearing (spec §9.10): a legacy action's mobile features, whether
# it keeps its notification when acknowledged, and whether it clears it rather
# than show the done message; and the same for the persistent member.
CONF_MOBILE = "mobile"
CONF_KEEP_ON_ACK = "keep_on_ack"
CONF_CLEAR_WHEN_ENDED = "clear_when_ended"
CONF_PERSISTENT_CLEAR_ON_ACK = "persistent_clear_on_ack"
CONF_PERSISTENT_CLEAR_WHEN_ENDED = "persistent_clear_when_ended"

# Messages (spec §9.5).
DEFAULT_ON_MESSAGE = "{{ name }} is firing."
DEFAULT_REMINDER_MESSAGE = "{{ name }} is still firing ({{ duration }})."
DEFAULT_DONE_MESSAGE = "{{ name }} stopped firing after {{ duration }}."
DEFAULT_DONE_NO_DATA_MESSAGE = (
    "{{ name }} lost its data; stopped firing after {{ duration }}."
)
DEFAULT_DONE_DISABLED_MESSAGE = (
    "{{ name }} was disabled; stopped firing after {{ duration }}."
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
# Supersession (spec §8.1, §9.7): how long a superseded alert's on notification
# waits for a superseding alert to fire, and how long its done notification waits
# for one to end. Stored as seconds.
CONF_SUPERSESSION_DEBOUNCE = "supersession_debounce"
DEFAULT_SUPERSESSION_DEBOUNCE = timedelta(seconds=0.5)
CONF_DONE_WINDOW = "done_window"
DEFAULT_DONE_WINDOW = timedelta(seconds=5)
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
# One per (referring alert, missing alert): the prefix, then the referring
# alert's subentry ID and the missing alert's object ID (spec §12.4).
ISSUE_BROKEN_REFERENCE = "broken_reference"

# Actions (spec §16).
SERVICE_FIRE = "fire"
SERVICE_DISMISS = "dismiss"
SERVICE_ACK = "ack"
SERVICE_UNACK = "unack"
SERVICE_SNOOZE = "snooze"
SERVICE_DISABLE = "disable"
SERVICE_ENABLE = "enable"
SERVICE_SUSPEND = "suspend"

ATTR_DATA = "data"
ATTR_UNTIL = "until"

# Events (spec §11.3).
EVENT_FIRED = f"{DOMAIN}_fired"
EVENT_ENDED = f"{DOMAIN}_ended"
EVENT_ACKED = f"{DOMAIN}_acked"
EVENT_UNACKED = f"{DOMAIN}_unacked"
EVENT_SNOOZED = f"{DOMAIN}_snoozed"
EVENT_SNOOZE_EXPIRED = f"{DOMAIN}_snooze_expired"
EVENT_DISABLED = f"{DOMAIN}_disabled"
EVENT_ENABLED = f"{DOMAIN}_enabled"
EVENT_NO_DATA = f"{DOMAIN}_no_data"
EVENT_DATA_RESTORED = f"{DOMAIN}_data_restored"
EVENT_SUPERSEDED = f"{DOMAIN}_superseded"
EVENT_CREATED = f"{DOMAIN}_created"
EVENT_DELETED = f"{DOMAIN}_deleted"
# Every event type, in the spec's order (§11.3).
EVENT_TYPES = (
    EVENT_FIRED,
    EVENT_ENDED,
    EVENT_ACKED,
    EVENT_UNACKED,
    EVENT_SNOOZED,
    EVENT_SNOOZE_EXPIRED,
    EVENT_DISABLED,
    EVENT_ENABLED,
    EVENT_NO_DATA,
    EVENT_DATA_RESTORED,
    EVENT_SUPERSEDED,
    EVENT_CREATED,
    EVENT_DELETED,
)

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
ATTR_DISABLED_UNTIL = "disabled_until"
ATTR_LAST_DISABLED = "last_disabled"
ATTR_LAST_DISABLED_BY = "last_disabled_by"
ATTR_LAST_ENABLED = "last_enabled"
ATTR_LAST_ENABLED_BY = "last_enabled_by"
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
ATTR_TARGET_STATES = "target_states"
ATTR_SUPERSEDES = "supersedes"
ATTR_SUPERSEDED_BY = "superseded_by"
ATTR_PRE_ACKED_BY = "pre_acked_by"
ATTR_PRE_SNOOZED_UNTIL = "pre_snoozed_until"
ATTR_BROKEN_REFERENCES = "broken_references"
