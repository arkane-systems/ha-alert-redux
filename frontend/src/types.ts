// Minimal slices of the frontend's objects; they grow as the cards need more of them.

export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
}

export interface HomeAssistant {
  states: Record<string, HassEntity>;
  /**
   * Call an action. With returnResponse, the action's response data comes back as
   * `response`; without notifyOnError, a failure is thrown to the caller only.
   */
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
    target?: Record<string, unknown>,
    notifyOnError?: boolean,
    returnResponse?: boolean,
  ): Promise<{ response?: unknown } | undefined>;
  callWS<T>(message: { type: string; [key: string]: unknown }): Promise<T>;
  /** Call Home Assistant's REST API, e.g. the config flows. */
  callApi<T>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    parameters?: Record<string, unknown>,
  ): Promise<T>;
  /** The frontend's translation of a key, filled in with values. */
  localize?(key: string, values?: Record<string, string | number>): string;
  /** Load an integration's backend translations (config flow strings, say). */
  loadBackendTranslation?(
    category: string,
    integration?: string | string[],
    configFlow?: boolean,
  ): Promise<(key: string, values?: Record<string, string | number>) => string>;
  themes?: { darkMode?: boolean };
  locale?: { language?: string };
  user?: { is_admin: boolean };
  /** The state as the frontend shows it, translated (HA 2023.9 on). */
  formatEntityState?(entity: HassEntity): string;
  /** An attribute's value as the frontend shows it, translated. */
  formatEntityAttributeValue?(entity: HassEntity, attribute: string): string;
}

export interface AlertReduxAdminCardConfig {
  type: string;
  title?: string;
  /** How many alerts a page shows; unset shows them all. */
  page_size?: number | string;
}

export interface AlertReduxCardConfig {
  type: string;
  title?: string;
  /**
   * The snooze menu's durations, in minutes. The visual editor stores them as
   * strings.
   */
  snooze_durations?: (number | string)[];
}

export type Priority = "emergency" | "critical" | "warning" | "notice" | "informational";

/** An alert_redux entity, with the attributes the card uses (spec §11.1). */
export interface Alert {
  entityId: string;
  state: string;
  name: string;
  icon: string;
  priority: Priority;
  kind: string;
  acknowledgeable: boolean;
  userDismissable: boolean;
  message: string | null;
  displayMessage: string | null;
  firingSince: Date | null;
  lastFired: Date | null;
  /** Event alerts: when the current firing's duration runs out (spec §4.2). */
  eventExpires: Date | null;
  noDataSince: Date | null;
  missingInputs: string[];
  /** While snoozed: when the snooze runs out (spec §6.2). */
  snoozedUntil: Date | null;
  /** While suspended: when the alert is enabled again (spec §6.4). */
  disabledUntil: Date | null;
  /** The firing alerts that supersede this one, transitively (spec §8.1). */
  supersededBy: string[];
  /** A generated alert's generator: its sensor's entity ID (spec §12.3). */
  generatedBy: string | null;
}
