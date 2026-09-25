import { LitElement, html, nothing, type PropertyValues } from "lit";

import {
  PRIORITY_NAMES,
  cardMessage,
  collectAlerts,
  compareFiring,
  compareNoData,
  isAlertEntity,
  isFiring,
} from "./alerts";
import { clockTime, elapsed } from "./format";
import { cardStyles } from "./styles";
import type { Alert, AlertReduxCardConfig, HomeAssistant } from "./types";

declare global {
  interface Window {
    customCards?: Array<{ type: string; name: string; description: string }>;
  }
}

/** Re-render this often, to keep the "firing for" times current. */
const TICK_MS = 30_000;

/**
 * The main card (spec §13.1): a sub-card for each firing alert, the alerts that
 * have no data, and an empty state when nothing is firing.
 */
export class AlertReduxCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _serverVersion: { state: true },
    _busy: { state: true },
  };

  declare hass?: HomeAssistant;
  declare _config?: AlertReduxCardConfig;
  /** The integration's version, when it differs from this card's. */
  declare _serverVersion?: string;
  /** Entity IDs with an action in flight, so their buttons can't be pressed twice. */
  declare _busy: Set<string>;

  private _tick?: number;
  private _versionChecked = false;

  static styles = cardStyles;

  constructor() {
    super();
    this._busy = new Set();
  }

  static getStubConfig(): Partial<AlertReduxCardConfig> {
    return {};
  }

  static getConfigForm() {
    return { schema: [{ name: "title", selector: { text: {} } }] };
  }

  setConfig(config: AlertReduxCardConfig): void {
    this._config = config;
  }

  getCardSize(): number {
    if (!this.hass) return 2;
    const alerts = collectAlerts(this.hass);
    const firing = alerts.filter(isFiring).length;
    const noData = alerts.filter((alert) => alert.state === "no_data").length;
    return 1 + Math.max(1, firing * 3) + (noData ? 1 + noData : 0);
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
    if (!old || !this.hass || old.themes?.darkMode !== this.hass.themes?.darkMode) {
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

  protected updated(): void {
    if (this.hass && !this._versionChecked) {
      this._versionChecked = true;
      void this._checkVersion();
    }
  }

  /** Offer a reload if the browser is still running an older card (spec §20, phase 3). */
  private async _checkVersion(): Promise<void> {
    try {
      const { version } = await this.hass!.callWS<{ version: string }>({
        type: "alert_redux/info",
      });
      if (version !== __CARD_VERSION__) this._serverVersion = version;
    } catch {
      // The integration isn't loaded, or is too old to say; nothing to offer.
    }
  }

  render() {
    if (!this.hass || !this._config) return nothing;
    const alerts = collectAlerts(this.hass);
    const firing = alerts.filter(isFiring).sort(compareFiring);
    const noData = alerts.filter((alert) => alert.state === "no_data").sort(compareNoData);
    const title = this._config.title;
    const dark = this.hass.themes?.darkMode ?? false;

    return html`
      <ha-card .header=${title || undefined}>
        <div class="content ${title ? "has-header" : ""} ${dark ? "dark" : "light"}">
          ${this._serverVersion ? this._renderBanner(this._serverVersion) : nothing}
          ${firing.length
            ? firing.map((alert) => this._renderAlert(alert))
            : html`<div class="empty">No alerts are firing.</div>`}
          ${noData.length ? this._renderNoData(noData) : nothing}
        </div>
      </ha-card>
    `;
  }

  private _renderBanner(version: string) {
    return html`
      <div class="banner" role="status">
        <ha-icon icon="mdi:update"></ha-icon>
        <span>Alert Redux has been updated to ${version}. Reload to use the new card.</span>
        <button class="primary" @click=${() => location.reload()}>Reload</button>
      </div>
    `;
  }

  private _renderAlert(alert: Alert) {
    const message = cardMessage(alert);
    const language = this.hass?.locale?.language;
    const since = alert.firingSince;
    return html`
      <div class="alert p-${alert.priority} ${alert.state}">
        <div class="head">
          <div class="chip" @click=${() => this._moreInfo(alert)}>
            <ha-icon .icon=${alert.icon}></ha-icon>
          </div>
          <div class="title">
            <div class="name" @click=${() => this._moreInfo(alert)}>${alert.name}</div>
            <div class="meta">
              <span>${PRIORITY_NAMES[alert.priority]}</span>
              ${since
                ? html`<span>·</span>
                    <span title=${since.toLocaleString(language)}
                      >firing for ${elapsed(since)} (since ${clockTime(since, language)})</span
                    >`
                : nothing}
              ${alert.noDataSince
                ? html`<span
                    class="badge"
                    title=${alert.missingInputs.length
                      ? `Missing: ${alert.missingInputs.join(", ")}`
                      : "Waiting for data"}
                    ><ha-icon icon="mdi:lan-disconnect"></ha-icon>No data</span
                  >`
                : nothing}
            </div>
          </div>
        </div>
        ${message ? html`<div class="message">${message}</div>` : nothing}
        ${this._renderControls(alert)}
      </div>
    `;
  }

  private _renderControls(alert: Alert) {
    const busy = this._busy.has(alert.entityId);
    const dismiss = alert.kind === "manual" && alert.userDismissable;
    if (!alert.acknowledgeable && !dismiss) return nothing;
    return html`
      <div class="controls">
        ${dismiss
          ? html`<button
              ?disabled=${busy}
              @click=${() => this._call(alert, "dismiss")}
            >
              <ha-icon icon="mdi:close"></ha-icon>Dismiss
            </button>`
          : nothing}
        ${!alert.acknowledgeable
          ? nothing
          : alert.state === "ack"
            ? html`<button
                ?disabled=${busy}
                title="Remove the acknowledgement"
                @click=${() => this._call(alert, "unack")}
              >
                <ha-icon icon="mdi:check-circle"></ha-icon>Acknowledged
              </button>`
            : html`<button
                class="primary"
                ?disabled=${busy}
                @click=${() => this._call(alert, "ack")}
              >
                <ha-icon icon="mdi:check"></ha-icon>Acknowledge
              </button>`}
      </div>
    `;
  }

  private _renderNoData(alerts: Alert[]) {
    return html`
      <div class="section-title">
        <ha-icon icon="mdi:lan-disconnect"></ha-icon>No data (${alerts.length})
      </div>
      <div class="no-data">
        ${alerts.map(
          (alert) => html`
            <div class="no-data-row p-${alert.priority}" @click=${() => this._moreInfo(alert)}>
              <ha-icon .icon=${alert.icon}></ha-icon>
              <div class="text">
                <div class="name">${alert.name}</div>
                <div class="meta">
                  ${alert.missingInputs.length
                    ? `Missing: ${alert.missingInputs.join(", ")}`
                    : "Waiting for data"}${alert.noDataSince
                    ? ` · for ${elapsed(alert.noDataSince)}`
                    : ""}
                </div>
              </div>
            </div>
          `,
        )}
      </div>
    `;
  }

  private async _call(alert: Alert, service: "ack" | "unack" | "dismiss"): Promise<void> {
    if (!this.hass) return;
    this._busy = new Set(this._busy).add(alert.entityId);
    try {
      await this.hass.callService("alert_redux", service, { entity_id: alert.entityId });
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

if (!customElements.get("alert-redux-card")) {
  customElements.define("alert-redux-card", AlertReduxCard);
  window.customCards = window.customCards ?? [];
  window.customCards.push({
    type: "alert-redux-card",
    name: "Alert Redux",
    description: "Shows firing Alert Redux alerts, and lets you acknowledge them.",
  });
  console.info(`%c ALERT-REDUX-CARD %c ${__CARD_VERSION__} `, "color:white;background:#b71c1c", "");
}
