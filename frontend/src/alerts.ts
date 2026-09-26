import type { Alert, HassEntity, HomeAssistant, Priority } from "./types";

export const DOMAIN = "alert_redux";

/** Priorities, highest first (spec §5). */
export const PRIORITIES: readonly Priority[] = [
  "emergency",
  "critical",
  "warning",
  "notice",
  "informational",
];

export const PRIORITY_NAMES: Record<Priority, string> = {
  emergency: "Emergency",
  critical: "Critical",
  warning: "Warning",
  notice: "Notice",
  informational: "Informational",
};

const DEFAULT_ICONS: Record<Priority, string> = {
  emergency: "mdi:alarm-light",
  critical: "mdi:alert-octagon",
  warning: "mdi:alert",
  notice: "mdi:alert-circle-outline",
  informational: "mdi:information-outline",
};

/** Firing means active or acknowledged (spec §3). */
export const isFiring = (alert: Alert): boolean =>
  alert.state === "active" || alert.state === "ack";

export const isAlertEntity = (entityId: string): boolean =>
  entityId.startsWith(`${DOMAIN}.`);

const toDate = (value: unknown): Date | null => {
  if (typeof value !== "string" || !value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

const toText = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

export function toAlert(entity: HassEntity): Alert {
  const attributes = entity.attributes;
  const priority = PRIORITIES.includes(attributes.priority as Priority)
    ? (attributes.priority as Priority)
    : "informational";
  return {
    entityId: entity.entity_id,
    state: entity.state,
    name: toText(attributes.friendly_name) ?? entity.entity_id,
    icon: toText(attributes.icon) ?? DEFAULT_ICONS[priority],
    priority,
    kind: toText(attributes.kind) ?? "",
    acknowledgeable: attributes.acknowledgeable !== false,
    userDismissable: attributes.user_dismissable === true,
    message: toText(attributes.message),
    displayMessage: toText(attributes.display_message),
    firingSince: toDate(attributes.firing_since),
    lastFired: toDate(attributes.last_fired),
    eventExpires: toDate(attributes.event_expires),
    noDataSince: toDate(attributes.no_data_since),
    missingInputs: Array.isArray(attributes.missing_inputs)
      ? attributes.missing_inputs.map(String)
      : [],
    snoozedUntil: toDate(attributes.snoozed_until),
    disabledUntil: toDate(attributes.disabled_until),
  };
}

/** Every alert entity, in no particular order. */
export const collectAlerts = (hass: HomeAssistant): Alert[] =>
  Object.values(hass.states)
    .filter((entity) => isAlertEntity(entity.entity_id))
    .map(toAlert);

const time = (date: Date | null): number => date?.getTime() ?? 0;

/**
 * Card order (spec §13.1): by priority, then unacknowledged before acknowledged,
 * then the most recent firing first.
 */
export function compareFiring(a: Alert, b: Alert): number {
  return (
    PRIORITIES.indexOf(a.priority) - PRIORITIES.indexOf(b.priority) ||
    Number(a.state === "ack") - Number(b.state === "ack") ||
    time(b.firingSince) - time(a.firingSince) ||
    a.name.localeCompare(b.name)
  );
}

/** No-data alerts: by priority, then name. */
export function compareNoData(a: Alert, b: Alert): number {
  return (
    PRIORITIES.indexOf(a.priority) - PRIORITIES.indexOf(b.priority) ||
    a.name.localeCompare(b.name)
  );
}

/** State names, for a frontend too old to translate them. */
export const STATE_NAMES: Record<string, string> = {
  idle: "Idle",
  active: "Active",
  ack: "Acknowledged",
  no_data: "No data",
  disabled: "Disabled",
};

/** Kind names, for a frontend too old to translate them. */
export const KIND_NAMES: Record<string, string> = {
  manual: "Manual",
  state: "State",
  on_off: "On/off",
  threshold: "Threshold",
  template: "Template",
  trigger: "Trigger",
  event: "Bus event",
};

/** Alerts by name. */
export const compareName = (a: Alert, b: Alert): number => a.name.localeCompare(b.name);

/** The snooze menu's durations, in minutes, unless the card sets its own. */
export const DEFAULT_SNOOZE_DURATIONS: readonly number[] = [15, 30, 60, 120, 240];

/** The card's snooze durations: positive numbers of minutes, or else the defaults. */
export function snoozeDurations(configured: unknown): readonly number[] {
  if (!Array.isArray(configured)) return DEFAULT_SNOOZE_DURATIONS;
  const minutes = configured.map(Number).filter((value) => value > 0);
  return minutes.length ? minutes : DEFAULT_SNOOZE_DURATIONS;
}

/** The text the card shows: the display message, or else the on message (F22). */
export const cardMessage = (alert: Alert): string | null =>
  alert.displayMessage ?? alert.message;

/**
 * How much of an event alert's duration is left, from 1 when it last fired to 0
 * when it runs out; null for an alert without a duration running.
 */
export function remainingFraction(alert: Alert, now: number = Date.now()): number | null {
  if (!alert.eventExpires || !alert.lastFired) return null;
  const total = alert.eventExpires.getTime() - alert.lastFired.getTime();
  if (total <= 0) return null;
  return Math.min(1, Math.max(0, (alert.eventExpires.getTime() - now) / total));
}
