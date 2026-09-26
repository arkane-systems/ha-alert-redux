// The card against a mock hass, in light and dark themes, for working on its looks
// without Home Assistant. Build with `npm run preview`, then open dev/preview.html.
import * as mdi from "@mdi/js";

import "../src/alert-redux-card";
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
  alert("back_door_open", "Back Door Open", "warning", "active", {
    icon: "mdi:door-open",
    display_message: "The back door has been open for more than 10 minutes.",
  }),
  alert("garage_left_open", "Garage Door Left Open", "warning", "ack", {
    icon: "mdi:garage-open",
    no_data_since: ago(3),
    missing_inputs: ["cover.garage_door"],
  }),
  alert("washing_done", "Washing Finished", "notice", "active", {
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
  }),
  alert("leak_bathroom", "Bathroom Leak", "critical", "no_data", {
    no_data_since: ago(25),
    missing_inputs: ["binary_sensor.bathroom_leak"],
  }),
  alert("attic_humid", "Attic Humid", "notice", "no_data", {
    no_data_since: ago(1),
  }),
  alert("porch_light", "Porch Light On", "notice", "idle"),
];

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
setStates(ALERTS);

function update(entityId: string, changes: Partial<HassEntity>) {
  const old = states[entityId];
  states = { ...states, [entityId]: { ...old, ...changes } };
  refresh();
}

function hassFor(dark: boolean): HomeAssistant {
  return {
    states: empty ? {} : states,
    themes: { darkMode: dark },
    locale: { language: "en-GB" },
    async callWS<T>() {
      return { version: stale ? "9.9.9" : __CARD_VERSION__ } as T;
    },
    async callService(_domain, service, data) {
      const entityId = String(data?.entity_id);
      await new Promise((resolve) => setTimeout(resolve, 300));
      const attributes = (snoozed_until: string | null) => ({
        attributes: { ...states[entityId].attributes, snoozed_until },
      });
      if (service === "ack") update(entityId, { state: "ack", ...attributes(null) });
      if (service === "unack") update(entityId, { state: "active", ...attributes(null) });
      if (service === "snooze") {
        const minutes = Number((data?.duration as { minutes: number }).minutes);
        update(entityId, { state: "ack", ...attributes(ago(-minutes)) });
      }
      if (service === "dismiss") update(entityId, { state: "idle" });
      return undefined;
    },
  };
}

function refresh() {
  for (const card of cards) card.hass = hassFor(card.dataset.theme === "dark");
}

function build() {
  for (const column of document.querySelectorAll<HTMLElement>(".column")) {
    const card = document.createElement("alert-redux-card") as Card;
    card.dataset.theme = column.dataset.theme;
    card.setConfig({ type: "custom:alert-redux-card", title: "Alerts" });
    column.append(card);
    cards.push(card);
  }
  refresh();
  // ?menu=<object ID> opens that alert's snooze menu.
  const menu = params.get("menu");
  if (menu) for (const card of cards) Object.assign(card, { _snoozeMenu: `alert_redux.${menu}` });
}

document.querySelector("#empty")?.addEventListener("change", (event) => {
  empty = (event.target as HTMLInputElement).checked;
  refresh();
});
document.querySelector("#reset")?.addEventListener("click", () => {
  setStates(ALERTS);
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
