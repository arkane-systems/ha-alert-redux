import { LitElement, html, nothing, type PropertyValues } from "lit";

import {
  PRIORITY_NAMES,
  cardMessage,
  collectAlerts,
  compareFiring,
  compareNoData,
  isAlertEntity,
  remainingFraction,
  isFiring,
  snoozeDurations,
} from "./alerts";
import { clockTime, elapsed, remaining, span } from "./format";
import { cardStyles, sharedStyles } from "./styles";
import type { Alert, AlertReduxCardConfig, HomeAssistant } from "./types";

declare global {
  interface Window {
    customCards?: Array<{ type: string; name: string; description: string }>;
  }
}

/** Re-render this often, to keep the "firing for" times current. */
const TICK_MS = 30_000;
/** While an event alert's progress bar is showing, re-render this often. */
const PROGRESS_TICK_MS = 1_000;

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
    _snoozeMenu: { state: true },
  };

  declare hass?: HomeAssistant;
  declare _config?: AlertReduxCardConfig;
  /** The integration's version, when it differs from this card's. */
  declare _serverVersion?: string;
  /** Entity IDs with an action in flight, so their buttons can't be pressed twice. */
  declare _busy: Set<string>;
  /** The entity ID whose snooze menu is open, if any. */
  declare _snoozeMenu?: string;

  private _tick?: number;
  private _progressTick?: number;
  /** Whether the last render showed a progress bar, which needs frequent updates. */
  private _hasProgress = false;
  private _versionChecked = false;

  static styles = [sharedStyles, cardStyles];

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
    const disabled = alerts.some((alert) => alert.state === "disabled");
    return 1 + Math.max(1, firing * 3) + (noData ? 1 + noData : 0) + (disabled ? 1 : 0);
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
    window.clearTimeout(this._progressTick);
    this._progressTick = undefined;
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
    // Progress bars drain smoothly: each render moves them on a second's worth,
    // with a matching transition, until the next render.
    if (this._hasProgress && this._progressTick === undefined && this.isConnected) {
      this._progressTick = window.setTimeout(() => {
        this._progressTick = undefined;
        this.requestUpdate();
      }, PROGRESS_TICK_MS);
    }
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
    this._hasProgress = false;
    if (!this.hass || !this._config) return nothing;
    const alerts = collectAlerts(this.hass);
    const firing = alerts.filter(isFiring).sort(compareFiring);
    const noData = alerts.filter((alert) => alert.state === "no_data").sort(compareNoData);
    const disabled = alerts.filter((alert) => alert.state === "disabled").length;
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
          ${disabled
            ? html`<div class="disabled-line">
                <ha-icon icon="mdi:bell-off-outline"></ha-icon>${disabled}
                ${disabled === 1 ? "alert" : "alerts"} disabled
              </div>`
            : nothing}
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
        ${this._renderProgress(alert)}
      </div>
    `;
  }

  /** An event alert's duration, as a bar that drains as it runs out (spec §13.1). */
  private _renderProgress(alert: Alert) {
    const fraction = remainingFraction(alert);
    if (fraction === null || !alert.eventExpires) return nothing;
    this._hasProgress = true;
    const ends = clockTime(alert.eventExpires, this.hass?.locale?.language);
    return html`
      <div class="progress" title="Ends at ${ends}">
        <div class="progress-fill" style="width: ${(fraction * 100).toFixed(2)}%"></div>
      </div>
    `;
  }

  private _renderControls(alert: Alert) {
    const busy = this._busy.has(alert.entityId);
    const dismiss = alert.kind === "manual" && alert.userDismissable;
    if (!alert.acknowledgeable && !dismiss) return nothing;
    const snoozed = alert.state === "ack" && alert.snoozedUntil;
    const menuOpen = this._snoozeMenu === alert.entityId;
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
          : html`<button
              class=${snoozed ? "snoozed" : ""}
              ?disabled=${busy}
              aria-expanded=${menuOpen ? "true" : "false"}
              title=${snoozed ? `Snoozed until ${this._time(alert.snoozedUntil!)}` : "Snooze"}
              @click=${() => this._toggleSnoozeMenu(alert)}
            >
              <ha-icon icon="mdi:alarm-snooze"></ha-icon>${snoozed
                ? `Snoozed · ${remaining(alert.snoozedUntil!)}`
                : "Snooze"}<ha-icon
                class="caret"
                icon=${menuOpen ? "mdi:menu-up" : "mdi:menu-down"}
              ></ha-icon>
            </button>`}
        ${!alert.acknowledgeable || snoozed
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
      ${menuOpen ? this._renderSnoozeMenu(alert, busy) : nothing}
    `;
  }

  /**
   * The snooze durations, opened below the controls rather than floating over the
   * card, where the alert's box would clip it. A snoozed alert can also be kept
   * acknowledged, or unsnoozed.
   */
  private _renderSnoozeMenu(alert: Alert, busy: boolean) {
    const snoozed = alert.state === "ack" && alert.snoozedUntil;
    return html`
      <div class="choices" role="group" aria-label="Snooze for">
        <span class="label">${snoozed ? "Snooze again for" : "Snooze for"}</span>
        ${snoozeDurations(this._config?.snooze_durations).map(
          (minutes) => html`<button
            class="chip-button"
            ?disabled=${busy}
            @click=${() => this._snooze(alert, minutes)}
          >
            ${span(minutes * 60_000)}
          </button>`,
        )}
        ${snoozed
          ? html`<span class="break"></span>
              <button
                class="chip-button"
                ?disabled=${busy}
                title="Stay acknowledged until the alert stops firing"
                @click=${() => this._menuCall(alert, "ack")}
              >
                <ha-icon icon="mdi:check-circle"></ha-icon>Keep acknowledged
              </button>
              <button
                class="chip-button"
                ?disabled=${busy}
                title="Remove the snooze and the acknowledgement"
                @click=${() => this._menuCall(alert, "unack")}
              >
                <ha-icon icon="mdi:alarm-off"></ha-icon>Unsnooze
              </button>`
          : nothing}
      </div>
    `;
  }

  private _toggleSnoozeMenu(alert: Alert): void {
    this._snoozeMenu = this._snoozeMenu === alert.entityId ? undefined : alert.entityId;
  }

  private _snooze(alert: Alert, minutes: number): void {
    this._snoozeMenu = undefined;
    void this._call(alert, "snooze", { duration: { minutes } });
  }

  private _menuCall(alert: Alert, service: "ack" | "unack"): void {
    this._snoozeMenu = undefined;
    void this._call(alert, service);
  }

  private _time(date: Date): string {
    return clockTime(date, this.hass?.locale?.language);
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

  private async _call(
    alert: Alert,
    service: "ack" | "unack" | "dismiss" | "snooze",
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
