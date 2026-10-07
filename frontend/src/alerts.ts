import type { Alert, EntityRegistryDisplay, HassEntity, HomeAssistant, Priority } from "./types";

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

/** Latched: stopped firing without being acknowledged, kept until it is (spec §10). */
export const isLatched = (alert: Alert): boolean => alert.state === "latched";

/** The alerts in the card's main list: firing, or latched. */
export const isListed = (alert: Alert): boolean => isFiring(alert) || isLatched(alert);

export const isAlertEntity = (entityId: string): boolean =>
  entityId.startsWith(`${DOMAIN}.`);

const toDate = (value: unknown): Date | null => {
  if (typeof value !== "string" || !value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

const toText = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const textList = (value: unknown): string[] =>
  Array.isArray(value) ? value.map(String) : [];

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
    latching: attributes.latching === true,
    userDismissable: attributes.user_dismissable === true,
    message: toText(attributes.message),
    displayMessage: toText(attributes.display_message),
    firingSince: toDate(attributes.firing_since),
    lastFired: toDate(attributes.last_fired),
    lastEnded: toDate(attributes.last_ended),
    fireCount: typeof attributes.fire_count === "number" ? attributes.fire_count : 0,
    eventExpires: toDate(attributes.event_expires),
    noDataSince: toDate(attributes.no_data_since),
    missingInputs: Array.isArray(attributes.missing_inputs)
      ? attributes.missing_inputs.map(String)
      : [],
    snoozedUntil: toDate(attributes.snoozed_until),
    disabledUntil: toDate(attributes.disabled_until),
    supersededBy: textList(attributes.superseded_by),
    buttons: textList(attributes.buttons),
    unlockButtons: textList(attributes.buttons_require_unlock),
    generatedBy: toText(attributes.generated_by),
  };
}

/** A generator, from its sensor (spec §12.3). */
export interface Generator {
  /** The generator's sensor. */
  entityId: string;
  name: string;
  /** The alerts it has made now. */
  alerts: string[];
}

const GENERATOR_PREFIX = "Alert Redux generator ";

/**
 * Whether an entity is a generator's sensor: one of ours with the targets and
 * alerts attributes, which the summary sensors don't have.
 */
export function isGeneratorSensor(hass: HomeAssistant, entity: HassEntity | undefined): boolean {
  if (!entity || !entity.entity_id.startsWith("sensor.")) return false;
  const platform = hass.entities?.[entity.entity_id]?.platform;
  return (
    (platform === undefined || platform === DOMAIN) &&
    "targets" in entity.attributes &&
    Array.isArray(entity.attributes.alerts)
  );
}

/** Every generator, by its sensor, in no particular order. */
export const collectGenerators = (hass: HomeAssistant): Generator[] =>
  Object.values(hass.states)
    .filter((entity) => isGeneratorSensor(hass, entity))
    .map((entity) => ({
      entityId: entity.entity_id,
      name: (toText(entity.attributes.friendly_name) ?? entity.entity_id).replace(
        GENERATOR_PREFIX,
        "",
      ),
      alerts: textList(entity.attributes.alerts),
    }));

/** Every alert entity, in no particular order. */
export const collectAlerts = (hass: HomeAssistant): Alert[] =>
  Object.values(hass.states)
    .filter((entity) => isAlertEntity(entity.entity_id))
    .map(toAlert);

const time = (date: Date | null): number => date?.getTime() ?? 0;

/** Within a priority: active, then latched, then acknowledged. */
const STATE_ORDER: Record<string, number> = { active: 0, latched: 1, ack: 2 };

/**
 * Card order (spec §13.1, §10): by priority, then active, latched, and
 * acknowledged, then the most recent first (firing, or for a latched alert,
 * ending).
 */
export function compareFiring(a: Alert, b: Alert): number {
  return (
    PRIORITIES.indexOf(a.priority) - PRIORITIES.indexOf(b.priority) ||
    (STATE_ORDER[a.state] ?? 0) - (STATE_ORDER[b.state] ?? 0) ||
    time(b.firingSince ?? b.lastEnded) - time(a.firingSince ?? a.lastEnded) ||
    a.name.localeCompare(b.name)
  );
}

/** A listed alert shown on the card, with the listed alerts it supersedes. */
export interface AlertGroup {
  alert: Alert;
  superseded: Alert[];
}

/**
 * The firing alerts, in card order, with each superseded alert tucked under its
 * root: the first alert in card order that supersedes it and isn't superseded
 * itself (spec §8.1, §13.1). A chain is flattened under its root.
 */
export function groupSuperseded(firing: Alert[]): AlertGroup[] {
  const shown = new Set(firing.map((alert) => alert.entityId));
  const isRoot = (alert: Alert) => !alert.supersededBy.some((id) => shown.has(id));
  const roots = new Map<string, AlertGroup>();
  const groups: AlertGroup[] = [];
  for (const alert of firing) {
    if (!isRoot(alert)) continue;
    const group = { alert, superseded: [] };
    roots.set(alert.entityId, group);
    groups.push(group);
  }
  for (const alert of firing) {
    if (isRoot(alert)) continue;
    const root = firing.find(
      (other) => roots.has(other.entityId) && alert.supersededBy.includes(other.entityId),
    );
    if (root) roots.get(root.entityId)!.superseded.push(alert);
    // Only a supersession cycle leaves an alert without a root; show it anyway.
    else groups.push({ alert, superseded: [] });
  }
  return groups;
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
  latched: "Latched",
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
  alert_state: "Alert state",
  trigger: "Trigger",
  event: "Bus event",
};

/** Alerts by name. */
export const compareName = (a: { name: string }, b: { name: string }): number =>
  a.name.localeCompare(b.name);

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

/** A card option that takes one value or a list, as a list of non-empty text. */
export function asList(value: unknown): string[] {
  const items = Array.isArray(value) ? value : value === undefined || value === null ? [] : [value];
  return items.map(String).filter((item) => item !== "");
}

/**
 * Whether an alert is in the card's scope (spec §13.1): in one of the areas and
 * with one of the labels, for each of the two that is set. Alerts have no device,
 * so the registry entry's own area is the area. With no registry (a frontend too
 * old to give it), or nothing set, everything is in scope.
 */
export function inScope(
  entry: EntityRegistryDisplay | undefined,
  areas: string[],
  labels: string[],
): boolean {
  if (!areas.length && !labels.length) return true;
  if (!entry) return false;
  if (areas.length && !(entry.area_id && areas.includes(entry.area_id))) return false;
  if (labels.length && !(entry.labels ?? []).some((label) => labels.includes(label))) {
    return false;
  }
  return true;
}

/** The priorities a card option names, or all of them. */
export function viewPriorities(value: unknown): Set<Priority> {
  const named = asList(value).filter((item): item is Priority =>
    PRIORITIES.includes(item as Priority),
  );
  return new Set(named.length ? named : PRIORITIES);
}
