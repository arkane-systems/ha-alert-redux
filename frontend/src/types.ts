// Minimal slices of the frontend's objects; they grow as the cards need more of them.

export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
}

export interface HomeAssistant {
  states: Record<string, HassEntity>;
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
  ): Promise<unknown>;
  callWS<T>(message: { type: string; [key: string]: unknown }): Promise<T>;
  themes?: { darkMode?: boolean };
  locale?: { language?: string };
}

export interface AlertReduxCardConfig {
  type: string;
  title?: string;
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
}
