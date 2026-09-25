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
    noDataSince: toDate(attributes.no_data_since),
    missingInputs: Array.isArray(attributes.missing_inputs)
      ? attributes.missing_inputs.map(String)
      : [],
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

/** The text the card shows: the display message, or else the on message (F22). */
export const cardMessage = (alert: Alert): string | null =>
  alert.displayMessage ?? alert.message;
