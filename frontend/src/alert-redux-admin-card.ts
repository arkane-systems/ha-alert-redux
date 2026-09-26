import { LitElement, css, html, nothing, type PropertyValues } from "lit";

import {
  KIND_NAMES,
  PRIORITIES,
  PRIORITY_NAMES,
  STATE_NAMES,
  collectAlerts,
  compareName,
  isAlertEntity,
  isFiring,
} from "./alerts";
import { clockTime, elapsed, span } from "./format";
import { sharedStyles } from "./styles";
import type { Alert, AlertReduxAdminCardConfig, HomeAssistant } from "./types";

/** Re-render this often, to keep the times current. */
const TICK_MS = 30_000;
/** The suspend menu's durations, in minutes. */
const SUSPEND_DURATIONS: readonly number[] = [60, 240, 480, 1440, 10080];

/**
 * The admin card (spec §13.2): every alert, grouped by priority, with its kind and
 * state, and for admins, controls to enable, disable, and suspend it.
 */
export class AlertReduxAdminCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _busy: { state: true },
    _menu: { state: true },
    _untilOpen: { state: true },
  };

  declare hass?: HomeAssistant;
  declare _config?: AlertReduxAdminCardConfig;
  /** Entity IDs with an action in flight, so their buttons can't be pressed twice. */
  declare _busy: Set<string>;
  /** The entity ID whose suspend menu is open, if any. */
  declare _menu?: string;
  /** Whether the open suspend menu is showing its date and time field. */
  declare _untilOpen: boolean;

  private _tick?: number;

  static styles = [
    sharedStyles,
    css`
      .content {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 16px;
      }
      .content.has-header {
        padding-top: 0;
      }
      .section-title .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--c);
      }
      .group {
        display: flex;
        flex-direction: column;
        border: 1px solid var(--divider-color);
        border-radius: 12px;
        margin-bottom: 4px;
      }
      .row {
        padding: 8px 12px;
      }
      .row + .row {
        border-top: 1px solid var(--divider-color);
      }
      .line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px 10px;
      }
      .line > ha-icon {
        color: var(--c);
        flex-shrink: 0;
        cursor: pointer;
        --mdc-icon-size: 22px;
      }
      .text {
        flex: 1;
        min-width: 150px;
      }
      .name {
        font-weight: 500;
        color: var(--primary-text-color);
        cursor: pointer;
        overflow-wrap: anywhere;
      }
      .meta {
        font-size: 0.8rem;
        color: var(--secondary-text-color);
      }
      .state {
        display: inline-block;
        padding: 0 7px;
        border-radius: 8px;
        line-height: 1.3rem;
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--primary-text-color);
        background: color-mix(in srgb, var(--primary-text-color) 8%, transparent);
      }
      .state.active {
        background: color-mix(in srgb, var(--c) 30%, transparent);
      }
      .state.ack {
        background: color-mix(in srgb, var(--c) 14%, transparent);
      }
      .state.no_data {
        background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
      }
      .row.disabled > .line > ha-icon,
      .row.disabled .name {
        opacity: 0.55;
      }
      .controls {
        display: flex;
        gap: 6px;
        margin-left: auto;
      }
      .controls button {
        padding: 4px 12px;
        font-size: 0.8rem;
        --mdc-icon-size: 16px;
      }
      .choices {
        margin-top: 8px;
      }
      .until {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        align-items: center;
        gap: 6px;
        flex-basis: 100%;
      }
      input[type="datetime-local"] {
        font: inherit;
        font-size: 0.85rem;
        padding: 3px 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color, transparent);
        color: var(--primary-text-color);
        color-scheme: light dark;
      }
      .empty {
        color: var(--secondary-text-color);
        font-size: 0.9rem;
      }
    `,
  ];

  constructor() {
    super();
    this._busy = new Set();
    this._untilOpen = false;
  }

  static getStubConfig(): Partial<AlertReduxAdminCardConfig> {
    return {};
  }

  static getConfigForm() {
    return { schema: [{ name: "title", selector: { text: {} } }] };
  }

  setConfig(config: AlertReduxAdminCardConfig): void {
    this._config = config;
  }

  getCardSize(): number {
    return 1 + (this.hass ? collectAlerts(this.hass).length : 1);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  connectedCallback(): void {
    super.connectedCallback();
    this._tick = window.setInterval(() => this.requestUpdate(), TICK_MS);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    window.clearInterval(this._tick);
  }

  /** Skip renders for state changes that don't touch any alert. */
  protected shouldUpdate(changed: PropertyValues<this>): boolean {
    if (changed.size !== 1 || !changed.has("hass")) return true;
    const old = changed.get("hass") as HomeAssistant | undefined;
    if (!old || !this.hass || old.user?.is_admin !== this.hass.user?.is_admin) {
      return true;
    }
    const states = this.hass.states;
    const oldStates = old.states;
    for (const entityId in states) {
      if (isAlertEntity(entityId) && states[entityId] !== oldStates[entityId]) return true;
    }
    for (const entityId in oldStates) {
      if (isAlertEntity(entityId) && !(entityId in states)) return true;
    }
    return false;
  }

  render() {
    if (!this.hass || !this._config) return nothing;
    const alerts = collectAlerts(this.hass);
    const title = this._config.title;
    return html`
      <ha-card .header=${title || undefined}>
        <div class="content ${title ? "has-header" : ""}">
          ${alerts.length
            ? PRIORITIES.map((priority) => {
                const group = alerts
                  .filter((alert) => alert.priority === priority)
                  .sort(compareName);
                if (!group.length) return nothing;
                return html`
                  <div class="section-title p-${priority}">
                    <span class="dot"></span>${PRIORITY_NAMES[priority]} (${group.length})
                  </div>
                  <div class="group">${group.map((alert) => this._renderRow(alert))}</div>
                `;
              })
            : html`<div class="empty">No alerts are configured.</div>`}
        </div>
      </ha-card>
    `;
  }

  private _renderRow(alert: Alert) {
    const admin = this.hass?.user?.is_admin ?? false;
    const busy = this._busy.has(alert.entityId);
    const disabled = alert.state === "disabled";
    return html`
      <div class="row p-${alert.priority} ${alert.state}">
        <div class="line">
          <ha-icon .icon=${alert.icon} @click=${() => this._moreInfo(alert)}></ha-icon>
          <div class="text">
            <div class="name" @click=${() => this._moreInfo(alert)}>${alert.name}</div>
            <div class="meta">
              ${this._kind(alert)} ·
              <span class="state ${alert.state}">${this._state(alert)}</span>
              ${this._detail(alert)}
            </div>
          </div>
          ${admin
            ? html`<div class="controls">
                ${disabled
                  ? html`<button
                      class="primary"
                      ?disabled=${busy}
                      @click=${() => this._call(alert, "enable")}
                    >
                      <ha-icon icon="mdi:bell-outline"></ha-icon>Enable
                    </button>`
                  : html`<button ?disabled=${busy} @click=${() => this._call(alert, "disable")}>
                      <ha-icon icon="mdi:bell-off-outline"></ha-icon>Disable
                    </button>`}
                <button
                  ?disabled=${busy}
                  aria-expanded=${this._menu === alert.entityId ? "true" : "false"}
                  @click=${() => this._toggleMenu(alert)}
                >
                  <ha-icon icon="mdi:timer-pause-outline"></ha-icon>Suspend<ha-icon
                    class="caret"
                    icon=${this._menu === alert.entityId ? "mdi:menu-up" : "mdi:menu-down"}
                  ></ha-icon>
                </button>
              </div>`
            : nothing}
        </div>
        ${admin && this._menu === alert.entityId ? this._renderMenu(alert, busy) : nothing}
      </div>
    `;
  }

  /** How long to suspend for, or until when; for a suspended alert, a new end. */
  private _renderMenu(alert: Alert, busy: boolean) {
    return html`
      <div class="choices" role="group" aria-label="Suspend for">
        <span class="label">Suspend for</span>
        ${SUSPEND_DURATIONS.map(
          (minutes) => html`<button
            class="chip-button"
            ?disabled=${busy}
            @click=${() => this._suspend(alert, { duration: { minutes } })}
          >
            ${minutes === 10080 ? "1 week" : span(minutes * 60_000)}
          </button>`,
        )}
        <button
          class="chip-button"
          ?disabled=${busy}
          aria-expanded=${this._untilOpen ? "true" : "false"}
          @click=${() => (this._untilOpen = !this._untilOpen)}
        >
          Until…
        </button>
        ${this._untilOpen
          ? html`<div class="until">
              <input
                type="datetime-local"
                aria-label="Suspend until"
                .value=${this._defaultUntil()}
              />
              <button class="primary chip-button" ?disabled=${busy} @click=${() =>
                this._suspendUntil(alert)}>Suspend</button>
            </div>`
          : nothing}
      </div>
    `;
  }

  private _kind(alert: Alert): string {
    const entity = this.hass?.states[alert.entityId];
    const text = entity ? this.hass?.formatEntityAttributeValue?.(entity, "kind") : undefined;
    return text && text !== alert.kind ? text : (KIND_NAMES[alert.kind] ?? alert.kind);
  }

  private _state(alert: Alert): string {
    const entity = this.hass?.states[alert.entityId];
    const text = entity ? this.hass?.formatEntityState?.(entity) : undefined;
    return text && text !== alert.state ? text : (STATE_NAMES[alert.state] ?? alert.state);
  }

  /** A few words about the state: since when, until when, or for how long. */
  private _detail(alert: Alert) {
    const language = this.hass?.locale?.language;
    if (alert.state === "disabled") {
      return alert.disabledUntil
        ? html`until ${clockTime(alert.disabledUntil, language)}`
        : nothing;
    }
    if (alert.state === "ack" && alert.snoozedUntil) {
      return html`snoozed until ${clockTime(alert.snoozedUntil, language)}`;
    }
    if (isFiring(alert) && alert.firingSince) {
      return html`since ${clockTime(alert.firingSince, language)}`;
    }
    if (alert.state === "no_data" && alert.noDataSince) {
      return html`for ${elapsed(alert.noDataSince)}`;
    }
    return nothing;
  }

  /** Tomorrow at 08:00, local time, in the form a datetime-local input takes. */
  private _defaultUntil(): string {
    const date = new Date();
    date.setDate(date.getDate() + 1);
    date.setHours(8, 0, 0, 0);
    const pad = (value: number) => String(value).padStart(2, "0");
    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
      `T${pad(date.getHours())}:${pad(date.getMinutes())}`
    );
  }

  private _toggleMenu(alert: Alert): void {
    this._untilOpen = false;
    this._menu = this._menu === alert.entityId ? undefined : alert.entityId;
  }

  private _suspendUntil(alert: Alert): void {
    const input = this.renderRoot.querySelector<HTMLInputElement>(
      'input[type="datetime-local"]',
    );
    if (!input?.value) return;
    // The browser's local time, sent with its offset so there's no doubt which.
    const until = new Date(input.value);
    if (Number.isNaN(until.getTime())) return;
    this._suspend(alert, { until: until.toISOString() });
  }

  private _suspend(alert: Alert, data: Record<string, unknown>): void {
    this._menu = undefined;
    this._untilOpen = false;
    void this._call(alert, "suspend", data);
  }

  private async _call(
    alert: Alert,
    service: "enable" | "disable" | "suspend",
    data: Record<string, unknown> = {},
  ): Promise<void> {
    if (!this.hass) return;
    this._busy = new Set(this._busy).add(alert.entityId);
    try {
      await this.hass.callService("alert_redux", service, {
        entity_id: alert.entityId,
        ...data,
      });
    } catch (err) {
      this._fire("hass-notification", {
        message: (err as { message?: string } | undefined)?.message ?? String(err),
      });
    } finally {
      const busy = new Set(this._busy);
      busy.delete(alert.entityId);
      this._busy = busy;
    }
  }

  private _moreInfo(alert: Alert): void {
    this._fire("hass-more-info", { entityId: alert.entityId });
  }

  private _fire(type: string, detail: Record<string, unknown>): void {
    this.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
  }
}

if (!customElements.get("alert-redux-admin-card")) {
  customElements.define("alert-redux-admin-card", AlertReduxAdminCard);
  window.customCards = window.customCards ?? [];
  window.customCards.push({
    type: "alert-redux-admin-card",
    name: "Alert Redux admin",
    description: "Lists every Alert Redux alert, and lets admins disable, enable, and suspend them.",
  });
}
