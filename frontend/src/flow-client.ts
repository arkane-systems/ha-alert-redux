// A client for Home Assistant's config subentry flows, which are the same flows
// the integration page uses (spec §13.2). They are driven over the REST API, so
// every check the forms make still runs on the server.
import type { HomeAssistant } from "./types";

export type SubentryType = "alert" | "generator";

/** One field of a form step, as the server serialises its schema. */
export interface SchemaItem {
  name: string;
  type?: string;
  required?: boolean;
  default?: unknown;
  description?: { suggested_value?: unknown };
  /** For a section (type "expandable"): the fields inside it. */
  schema?: SchemaItem[];
  selector?: unknown;
  [key: string]: unknown;
}

export interface FlowStep {
  type: "form" | "menu" | "create_entry" | "abort" | "progress" | "external";
  flow_id: string;
  step_id?: string;
  data_schema?: SchemaItem[];
  errors?: Record<string, string> | null;
  description_placeholders?: Record<string, string> | null;
  menu_options?: string[] | Record<string, string>;
  reason?: string;
}

const PATH = "config/config_entries/subentries/flow";

/** Start a flow: to add a subentry, or (with subentryId) to reconfigure one. */
export function startFlow(
  hass: HomeAssistant,
  entryId: string,
  type: SubentryType,
  subentryId?: string,
): Promise<FlowStep> {
  return hass.callApi<FlowStep>("POST", PATH, {
    handler: [entryId, type],
    ...(subentryId ? { subentry_id: subentryId } : {}),
  });
}

/** Send a step's data (a menu's choice is {next_step_id}). */
export function stepFlow(
  hass: HomeAssistant,
  flowId: string,
  data: Record<string, unknown>,
): Promise<FlowStep> {
  return hass.callApi<FlowStep>("POST", `${PATH}/${flowId}`, data);
}

/** Abandon a flow that hasn't finished. */
export function cancelFlow(hass: HomeAssistant, flowId: string): Promise<unknown> {
  return hass.callApi("DELETE", `${PATH}/${flowId}`);
}

/** The values a form starts with: suggested values, then defaults; sections nested. */
export function initialData(schema: SchemaItem[]): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const item of schema) {
    if (item.type === "expandable") {
      data[item.name] = initialData(item.schema ?? []);
      continue;
    }
    const value = item.description?.suggested_value ?? item.default;
    if (value !== undefined && value !== null) data[item.name] = value;
  }
  return data;
}

/** The data to send: without the fields left empty, sections included. */
export function dataToSend(data: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (value === undefined || value === null || value === "") continue;
    // A section's fields are nested; an object value (event data, say) is a value
    // whose own keys are kept as they are, so only empty strings inside it go.
    result[key] =
      typeof value === "object" && !Array.isArray(value)
        ? dataToSend(value as Record<string, unknown>)
        : value;
  }
  return result;
}

/** The config entry's ID, and a subentry's from an alert's or generator's entity. */
export async function entryId(hass: HomeAssistant): Promise<string | undefined> {
  const entries = await hass.callWS<{ entry_id: string }[]>({
    type: "config_entries/get",
    domain: "alert_redux",
  });
  return entries[0]?.entry_id;
}

export async function subentryOf(
  hass: HomeAssistant,
  entityId: string,
): Promise<{ entryId: string; subentryId: string } | undefined> {
  const entry = await hass.callWS<{
    config_entry_id: string | null;
    config_subentry_id: string | null;
  }>({ type: "config/entity_registry/get", entity_id: entityId });
  return entry.config_entry_id && entry.config_subentry_id
    ? { entryId: entry.config_entry_id, subentryId: entry.config_subentry_id }
    : undefined;
}

export function deleteSubentry(
  hass: HomeAssistant,
  entryId: string,
  subentryId: string,
): Promise<unknown> {
  return hass.callWS({
    type: "config_entries/subentries/delete",
    entry_id: entryId,
    subentry_id: subentryId,
  });
}
