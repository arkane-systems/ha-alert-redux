// The card against a mock hass, in light and dark themes, for working on its looks
// without Home Assistant. Build with `npm run preview`, then open dev/preview.html.
import * as mdi from "@mdi/js";

import "../src/main";
import en from "../../custom_components/alert_redux/translations/en.json";
import { collectAlerts } from "../src/alerts";
import type { HassEntity, HomeAssistant } from "../src/types";

// --- Stand-ins for the frontend's own elements ------------------------------------

class StubCard extends HTMLElement {
  set header(value: string | undefined) {
    this._header = value;
    this._render();
  }
  private _header?: string;
  connectedCallback() {
    this._render();
  }
  private _render() {
    const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; background: var(--card-background-color);
          border-radius: 12px; border: 1px solid var(--divider-color);
          color: var(--primary-text-color); }
        h1 { margin: 0; padding: 16px 16px 12px; font-size: 24px; font-weight: 400; }
      </style>
      ${this._header ? `<h1>${this._header}</h1>` : ""}<slot></slot>`;
  }
}
customElements.define("ha-card", StubCard);

class StubIcon extends HTMLElement {
  static observedAttributes = ["icon"];
  private _icon = "";
  set icon(value: string) {
    this._icon = value;
    this._render();
  }
  attributeChangedCallback(_name: string, _old: string, value: string) {
    this.icon = value;
  }
  private _render() {
    const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
    // mdi:door-open -> mdiDoorOpen
    const key = this._icon
      .replace(/^mdi:/, "mdi-")
      .replace(/-([a-z0-9])/g, (_match, char: string) => char.toUpperCase());
    const path = (mdi as Record<string, string>)[key] ?? mdi.mdiHelpCircleOutline;
    root.innerHTML = `
      <style>:host { display: inline-flex; line-height: 0; }
        svg { width: var(--mdc-icon-size, 24px); height: var(--mdc-icon-size, 24px); }</style>
      <svg viewBox="0 0 24 24"><path fill="currentColor" d="${path}"></path></svg>`;
  }
}
customElements.define("ha-icon", StubIcon);

/** The frontend's localize, answered from the integration's own English strings. */
function localize(key: string, values?: Record<string, string | number>): string {
  let node: unknown = en;
  for (const part of key.replace(/^component\.alert_redux\./, "").split(".")) {
    node = (node as Record<string, unknown> | undefined)?.[part];
  }
  if (typeof node !== "string") return "";
  return node.replace(/\{(\w+)\}/g, (_match, name: string) => String(values?.[name] ?? ""));
}

/** A stand-in for ha-form: a text box per field, sections as groups. */
class StubForm extends HTMLElement {
  hass?: unknown;
  schema: { name: string; type?: string; schema?: unknown[] }[] = [];
  data: Record<string, unknown> = {};
  error: Record<string, string> = {};
  computeLabel!: (schema: unknown, data: unknown, options?: { path?: string[] }) => string;
  computeHelper!: (schema: unknown, options?: { path?: string[] }) => string;
  computeError!: (error: string, schema: unknown) => string;
  connectedCallback() {
    queueMicrotask(() => this._render());
  }
  private _render() {
    const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
    const field = (item: any, data: Record<string, unknown>, path: string[]): string => {
      if (item.type === "expandable") {
        const inner = (item.schema as unknown[]).map((child) =>
          field(child, (data[item.name] ?? {}) as Record<string, unknown>, [item.name]),
        );
        return `<details><summary>${this.computeLabel(item, this.data)}</summary>${inner.join("")}</details>`;
      }
      const error = this.error?.[item.name];
      return `<label style="display:block;margin:6px 0">
        <div>${this.computeLabel(item, this.data, { path })}${item.required ? " *" : ""}</div>
        <input data-name="${item.name}" data-path="${path.join(".")}"
          value="${String(data[item.name] ?? "").replace(/"/g, "&quot;")}" style="width:100%" />
        <small>${this.computeHelper(item, { path })}</small>
        ${error ? `<div style="color:red">${this.computeError(error, item)}</div>` : ""}</label>`;
    };
    // Like ha-form, a form-wide (base) error goes above the fields.
    const base = this.error?.base
      ? `<div style="color:red">${this.computeError(this.error.base, this.schema)}</div>`
      : "";
    root.innerHTML = base + this.schema.map((item) => field(item, this.data, [])).join("");
    root.querySelectorAll("input").forEach((input) =>
      input.addEventListener("input", () => {
        const next = structuredClone(this.data);
        const path = input.dataset.path ? input.dataset.path.split(".") : [];
        let target = next;
        for (const part of path) target = (target[part] ??= {}) as Record<string, unknown>;
        target[input.dataset.name!] = input.value;
        this.dispatchEvent(new CustomEvent("value-changed", { detail: { value: next } }));
      }),
    );
  }
}
customElements.define("ha-form", StubForm);

// --- Mock alerts ------------------------------------------------------------------

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

/** An event alert's attributes: fired minutesAgo, with a duration of minutes. */
const event = (kind: string, minutesAgo: number, minutes: number) => ({
  kind,
  firing_since: ago(minutesAgo),
  last_fired: ago(minutesAgo),
  event_expires: ago(minutesAgo - minutes),
});

function alert(
  objectId: string,
  name: string,
  priority: string,
  state: string,
  extra: Record<string, unknown> = {},
): HassEntity {
  const firing = state === "active" || state === "ack";
  return {
    entity_id: `alert_redux.${objectId}`,
    state,
    last_changed: ago(0),
    attributes: {
      friendly_name: name,
      priority,
      kind: "state",
      acknowledgeable: true,
      firing_since: firing ? ago(12) : null,
      message: firing ? `${name} is firing.` : null,
      display_message: null,
      no_data_since: null,
      missing_inputs: [],
      ...extra,
    },
  };
}

const ALERTS: HassEntity[] = [
  alert("smoke_kitchen", "Smoke in Kitchen", "emergency", "active", {
    icon: "mdi:smoke-detector-variant-alert",
    message: "Smoke detected by the kitchen sensor. Evacuate and call 999.",
    firing_since: ago(2),
  }),
  alert("flood_basement", "Basement Flooding", "emergency", "ack", {
    icon: "mdi:water-alert",
    message: "Water level 4 cm and rising.",
    firing_since: ago(95),
  }),
  alert("server_room_hot", "Server Room Overheated", "critical", "active", {
    message: "Server room is 38.5 °C (limit 30 °C).",
    firing_since: ago(40),
  }),
  alert("freezer_warm", "Freezer Warm", "critical", "ack", {
    icon: "mdi:fridge-alert",
    message: "Freezer is −4 °C.",
    firing_since: ago(300),
    snoozed_until: ago(-23),
  }),
  // Latched (spec §10): fired three times overnight, unacknowledged.
  alert("leak_sink", "Leak Under Sink", "emergency", "latched", {
    icon: "mdi:pipe-leak",
    latching: true,
    message: "Water detected under the kitchen sink.",
    fire_count: 3,
    last_fired: ago(70),
    last_ended: ago(45),
  }),
  alert("back_door_open", "Back Door Open", "warning", "active", {
    icon: "mdi:door-open",
    display_message: "The back door is open.",
    superseded_by: ["alert_redux.back_door_left_open"],
  }),
  // Supersession: Back Door Left Open supersedes Back Door Open, and Workshop
  // Open Overnight supersedes a chain of two.
  alert("back_door_left_open", "Back Door Left Open", "critical", "active", {
    icon: "mdi:door-open",
    message: "The back door has been open for 10 minutes.",
    firing_since: ago(2),
  }),
  alert("workshop_overnight", "Workshop Open Overnight", "critical", "active", {
    icon: "mdi:garage-alert",
    firing_since: ago(30),
  }),
  alert("workshop_left_open", "Workshop Door Left Open", "warning", "ack", {
    icon: "mdi:garage-open",
    firing_since: ago(50),
    superseded_by: ["alert_redux.workshop_overnight"],
  }),
  alert("workshop_open", "Workshop Door Open", "notice", "ack", {
    icon: "mdi:garage-open",
    firing_since: ago(60),
    superseded_by: ["alert_redux.workshop_overnight", "alert_redux.workshop_left_open"],
  }),
  alert("garage_left_open", "Garage Door Left Open", "warning", "ack", {
    icon: "mdi:garage-open",
    no_data_since: ago(3),
    missing_inputs: ["cover.garage_door"],
  }),
  alert("washing_done", "Washing Finished", "notice", "active", {
    buttons: ["Start dryer", "Lock up"],
    buttons_require_unlock: ["Lock up"],
    icon: "mdi:washing-machine",
    kind: "manual",
    user_dismissable: true,
    message: "The washing machine has finished. Hang the washing out.",
    firing_since: ago(1),
  }),
  alert("garden_motion", "Garden Motion", "warning", "active", {
    icon: "mdi:motion-sensor",
    message: "Motion in the back garden.",
    ...event("trigger", 7, 15),
  }),
  alert("doorbell", "Doorbell", "notice", "active", {
    icon: "mdi:doorbell",
    message: "Someone is at the front door.",
    ...event("event", 0.2, 5),
  }),
  alert("parcel", "Parcel Delivered", "informational", "ack", {
    icon: "mdi:package-variant-closed",
    message: "A parcel was left in the porch.",
    ...event("event", 4, 5),
  }),
  alert("bin_day", "Bin Day", "informational", "active", {
    icon: "mdi:trash-can",
    kind: "manual",
    user_dismissable: true,
    acknowledgeable: false,
    message: "Recycling goes out tonight.",
    firing_since: ago(60 * 26),
  }),
  alert("battery_low", "Remote Battery Low", "informational", "ack", {
    icon: "mdi:battery-alert",
    kind: "threshold",
    generated_by: "sensor.alert_redux_generator_battery_low",
  }),
  alert("leak_bathroom", "Bathroom Leak", "critical", "no_data", {
    no_data_since: ago(25),
    missing_inputs: ["binary_sensor.bathroom_leak"],
  }),
  alert("attic_humid", "Attic Humid", "notice", "no_data", {
    no_data_since: ago(1),
  }),
  alert("porch_light", "Porch Light On", "notice", "idle"),
  alert("pool_pump", "Pool Pump Fault", "warning", "disabled", {
    icon: "mdi:pool",
    kind: "threshold",
  }),
  alert("office_window", "Office Window Open", "informational", "disabled", {
    icon: "mdi:window-open",
    disabled_until: ago(-60 * 14),
  }),
];

// --- Mock definitions, as the export action returns them -----------------------------

const DEFINITIONS = {
  format: "alert_redux",
  version: 1,
  alerts: [
    {
      id: "01M3EWQ0P4MT6R6FWNW6TRFCMM",
      name: "Workshop Door Left Open",
      kind: "state",
      priority: "warning",
      acknowledgeable: true,
      entity_id: "cover.workshop_garage_door",
      target_state: "open",
      delay_on: { hours: 0, minutes: 10, seconds: 0 },
      delay_off: { hours: 0, minutes: 0, seconds: 5 },
      message: "The workshop main door has been left open.",
      reminder_message: "The workshop main door has been left open for {{ duration }}.",
      done_message: "The workshop main door has been closed. It was open for {{ duration }}.",
      notifier_groups: ["Quiet", "Office Only"],
      reminder_schedule: [5, 15],
      supersedes: [
        {
          alert: "alert_redux.workshop_door_open",
          propagation: "snooze",
          snooze_duration: { hours: 4, minutes: 0, seconds: 0 },
        },
      ],
      buttons: [{ label: "Close door", action: [], require_unlock: true }],
      proxy_switch: true,
      proxy_snooze_button: true,
    },
  ],
  generators: [
    {
      id: "01M3FZK72JW93F4YNJRM8F7P7Y",
      name: "Battery Low",
      kind: "threshold",
      priority: "informational",
      acknowledgeable: true,
      name_template: "{{ target_name }} battery low",
      targets: { domains: ["sensor"], device_classes: ["battery"], exclude: ["sensor.spare"] },
      minimum: "15",
      hysteresis: 5,
      throttle: [3, 60],
    },
  ],
};

// --- The page ---------------------------------------------------------------------

type Card = HTMLElement & { hass: HomeAssistant; setConfig(config: object): void };

const cards: Card[] = [];
let states: Record<string, HassEntity> = {};
// ?empty and ?stale start the page with those toggles on.
const params = new URLSearchParams(location.search);
let empty = params.has("empty");
let stale = params.has("stale");
for (const id of ["empty", "stale"]) {
  const box = document.querySelector<HTMLInputElement>(`#${id}`);
  if (box) box.checked = params.has(id);
}

function setStates(list: HassEntity[]) {
  states = Object.fromEntries(list.map((entity) => [entity.entity_id, entity]));
}
// The generator of the generated alert (spec §12.3); not an alert itself.
const GENERATOR: HassEntity = {
  entity_id: "sensor.alert_redux_generator_battery_low",
  state: "1",
  last_changed: ago(0),
  attributes: { friendly_name: "Alert Redux generator Battery Low" },
} as HassEntity;
setStates([...ALERTS, GENERATOR]);

function update(entityId: string, changes: Partial<HassEntity>) {
  const old = states[entityId];
  states = { ...states, [entityId]: { ...old, ...changes } };
  refresh();
}

// A stand-in for the subentry flow API: a kind menu, then one state-alert form that
// refuses the name "Bad", then a created entry.
function mockFlow(method: string, path: string, body?: Record<string, unknown>) {
  const flow_id = "flow1";
  if (method === "DELETE") return {};
  if (path.endsWith("/flow")) {
    if (body?.subentry_id) return stateForm(flow_id, {});
    const type = (body?.handler as string[])[1];
    return { type: "menu", flow_id, step_id: "user", menu_options: type === "alert" ? ["manual", "state"] : ["state"] };
  }
  if (body?.next_step_id) return stateForm(flow_id, {});
  const name = String((body as { name?: string }).name ?? "");
  if (name === "Bad") return stateForm(flow_id, { name: "name_exists" }, { base: "name_exists" });
  return { type: "create_entry", flow_id };
}

function stateForm(flow_id: string, errors: Record<string, string>, extra = {}) {
  return {
    type: "form",
    flow_id,
    step_id: "state",
    errors: { ...errors, ...extra },
    description_placeholders: {},
    data_schema: [
      { name: "name", type: "string", required: true },
      { name: "priority", type: "select", required: true, default: "warning" },
      { name: "entity_id", type: "string", required: true },
      { name: "target_state", type: "string", required: true },
      {
        name: "notifications",
        type: "expandable",
        schema: [
          { name: "use_default_groups", type: "boolean", default: true },
          { name: "message", type: "string" },
        ],
      },
    ],
  };
}

// The entity registry: some alerts have areas and labels, for the scope options.
const REGISTRY: Record<string, { area_id: string | null; labels: string[] }> = {
  smoke_kitchen: { area_id: "kitchen", labels: ["safety"] },
  flood_basement: { area_id: "basement", labels: ["safety"] },
  server_room_hot: { area_id: "office", labels: ["network"] },
  back_door_open: { area_id: "hall", labels: [] },
  back_door_left_open: { area_id: "hall", labels: [] },
  leak_bathroom: { area_id: "bathroom", labels: ["safety"] },
};

function hassFor(dark: boolean): HomeAssistant {
  return {
    states: empty ? {} : states,
    entities: Object.fromEntries(
      Object.keys(states).map((entityId) => [
        entityId,
        {
          entity_id: entityId,
          ...(REGISTRY[entityId.replace("alert_redux.", "")] ?? { area_id: null, labels: [] }),
        },
      ]),
    ),
    themes: { darkMode: dark },
    locale: { language: "en-GB" },
    user: { is_admin: !params.has("user") },
    localize,
    async loadBackendTranslation() {
      return localize;
    },
    async callWS<T>(message: { type: string; entity_id?: string }) {
      if (message.type === "config_entries/get") return [{ entry_id: "entry1" }] as T;
      if (message.type === "config/entity_registry/get") {
        const generated = states[String(message.entity_id)]?.attributes.generated_by;
        void generated;
        return { config_entry_id: "entry1", config_subentry_id: `sub_${message.entity_id}` } as T;
      }
      if (message.type === "config_entries/subentries/delete") {
        console.log("delete", message);
        return null as T;
      }
      return { version: stale ? "9.9.9" : __CARD_VERSION__ } as T;
    },
    async callApi<T>(method: string, path: string, body?: Record<string, unknown>) {
      return mockFlow(method, path, body) as T;
    },
    async callService(_domain, service, data) {
      if (service === "export") {
        await new Promise((resolve) => setTimeout(resolve, 200));
        // A generated alert exports its generator.
        const generated = data?.entity_id === "alert_redux.battery_low";
        return {
          response: {
            ...DEFINITIONS,
            alerts: data?.entity_id && generated ? [] : DEFINITIONS.alerts,
            generators: data?.entity_id && !generated ? [] : DEFINITIONS.generators,
          },
        };
      }
      if (service === "import") {
        await new Promise((resolve) => setTimeout(resolve, 300));
        const file = data?.definitions as { alerts?: { name: string }[] } | undefined;
        if (file?.alerts?.some((definition) => definition.name === "Bad")) {
          throw new Error("Nothing was imported:\n- alert 'Bad': unknown_group (Loud)");
        }
        const names = (file?.alerts ?? []).map((definition) => ({ name: definition.name }));
        return {
          response: { created: names, updated: [], unchanged: [], dry_run: data?.dry_run },
        };
      }
      const entityId = String(data?.entity_id);
      await new Promise((resolve) => setTimeout(resolve, 300));
      const attributes = (snoozed_until: string | null) => ({
        attributes: { ...states[entityId].attributes, snoozed_until },
      });
      if (service === "ack") {
        const latched = states[entityId].state === "latched";
        update(entityId, { state: latched ? "idle" : "ack", ...attributes(null) });
      }
      if (service === "unack") update(entityId, { state: "active", ...attributes(null) });
      if (service === "disable" || service === "suspend") {
        const until = data?.until
          ? String(data.until)
          : data?.duration
            ? ago(-Number((data.duration as { minutes: number }).minutes))
            : null;
        update(entityId, {
          state: "disabled",
          attributes: {
            ...states[entityId].attributes,
            disabled_until: until,
            firing_since: null,
            snoozed_until: null,
          },
        });
      }
      if (service === "enable") {
        update(entityId, {
          state: "idle",
          attributes: { ...states[entityId].attributes, disabled_until: null },
        });
      }
      if (service === "snooze") {
        const minutes = Number((data?.duration as { minutes: number }).minutes);
        const latched = states[entityId].state === "latched";
        update(entityId, { state: latched ? "latched" : "ack", ...attributes(ago(-minutes)) });
      }
      if (service === "dismiss") update(entityId, { state: "idle" });
      if (service === "press_button") console.log("press_button", entityId, data?.label);
      return undefined;
    },
  };
}

function refresh() {
  for (const card of cards) card.hass = hassFor(card.dataset.theme === "dark");
}

function build() {
  for (const column of document.querySelectorAll<HTMLElement>(".column")) {
    // ?admin shows the admin card; ?user shows it as a non-admin sees it.
    const admin = params.has("admin") || params.has("user");
    const card = document.createElement(
      admin ? "alert-redux-admin-card" : "alert-redux-card",
    ) as Card;
    card.dataset.theme = column.dataset.theme;
    card.setConfig({
      type: admin ? "custom:alert-redux-admin-card" : "custom:alert-redux-card",
      title: admin ? "All alerts" : "Alerts",
      // ?areas=kitchen,hall and ?labels=safety scope the main card; ?hide starts it with
      // acknowledged alerts hidden, and ?prios=critical,warning with only those shown.
      ...(params.has("areas") ? { areas: params.get("areas")!.split(",") } : {}),
      ...(params.has("labels") ? { labels: params.get("labels")!.split(",") } : {}),
      ...(params.has("hide") ? { hide_acknowledged: true } : {}),
      ...(params.has("prios") ? { priorities: params.get("prios")!.split(",") } : {}),
      // ?pagesize=5 pages the admin card; ?page=2 starts on the second page.
      ...(params.has("pagesize") ? { page_size: Number(params.get("pagesize")) } : {}),
    });
    if (params.has("page")) {
      Object.assign(card, { _page: Number(params.get("page")) - 1 });
    }
    column.append(card);
    cards.push(card);
  }
  refresh();
  // ?menu=<object ID> opens that alert's snooze (or suspend) menu; ?until also
  // opens the admin card's date and time field.
  // ?expanded shows every alert's superseded alerts.
  if (params.has("expanded")) {
    const expanded = new Set(Object.keys(states));
    for (const card of cards) Object.assign(card, { _expanded: expanded });
  }
  // ?add, ?addgen, ?edit=<object ID>, or ?delete=<object ID> open those dialogs.
  const flowParam = params.has("add")
    ? { type: "alert", entryId: "entry1" }
    : params.has("addgen")
      ? { type: "generator", entryId: "entry1" }
      : params.has("edit")
        ? { type: "alert", entryId: "entry1", subentryId: "sub1" }
        : undefined;
  if (flowParam) for (const card of cards) Object.assign(card, { _flow: flowParam });
  if (params.has("delete")) {
    const alert = collectAlerts(hassFor(false)).find((a) => a.entityId.endsWith(params.get("delete")!));
    for (const card of cards) {
      Object.assign(card, {
        _delete: { alert, entryId: "entry1", subentryId: "sub1", generator: false, referrers: ["Back Door Left Open"] },
      });
    }
  }
  // ?summary=<object ID>, ?export, or ?import opens that dialog.
  const dialog = params.has("summary")
    ? { mode: "summary", entityId: `alert_redux.${params.get("summary")}` }
    : params.has("export")
      ? { mode: "export" }
      : params.has("import")
        ? { mode: "import" }
        : undefined;
  if (dialog) for (const card of cards) Object.assign(card, { _transfer: dialog });
  const menu = params.get("menu");
  if (menu) {
    const entityId = `alert_redux.${menu}`;
    for (const card of cards) {
      Object.assign(card, { _snoozeMenu: entityId, _menu: entityId, _untilOpen: params.has("until") });
    }
  }
}

document.querySelector("#empty")?.addEventListener("change", (event) => {
  empty = (event.target as HTMLInputElement).checked;
  refresh();
});
document.querySelector("#reset")?.addEventListener("click", () => {
  setStates([...ALERTS, GENERATOR]);
  refresh();
});
document.querySelector("#stale")?.addEventListener("change", (event) => {
  stale = (event.target as HTMLInputElement).checked;
  // The card checks once; rebuild the cards to check again.
  for (const card of cards) card.remove();
  cards.length = 0;
  build();
});
document.addEventListener("hass-more-info", (event) =>
  console.log("more-info", (event as CustomEvent).detail),
);

build();
