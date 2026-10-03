import { LitElement, html, nothing, type PropertyValues } from "lit";

import {
  DEFAULT_SNOOZE_DURATIONS,
  PRIORITIES,
  PRIORITY_NAMES,
  asList,
  inScope,
  viewPriorities,
  cardMessage,
  collectAlerts,
  compareFiring,
  compareNoData,
  groupSuperseded,
  isAlertEntity,
  remainingFraction,
  isLatched,
  isListed,
  snoozeDurations,
  type AlertGroup,
} from "./alerts";
import { clockTime, elapsed, remaining, span } from "./format";
import { cardStyles, sharedStyles } from "./styles";
import type { Alert, AlertReduxCardConfig, HomeAssistant, Priority } from "./types";

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
    _expanded: { state: true },
    _confirm: { state: true },
    _hideAcknowledged: { state: true },
    _priorities: { state: true },
  };

  declare hass?: HomeAssistant;
  declare _config?: AlertReduxCardConfig;
  /** The integration's version, when it differs from this card's. */
  declare _serverVersion?: string;
  /** Entity IDs with an action in flight, so their buttons can't be pressed twice. */
  declare _busy: Set<string>;
  /** The entity ID whose snooze menu is open, if any. */
  declare _snoozeMenu?: string;
  /** The entity IDs of alerts whose superseded alerts are shown. */
  declare _expanded: Set<string>;
  /** A "Require unlock" button waiting for the user to confirm it (spec §13.1). */
  /** The view controls (spec §13.1): the config sets their starting values. */
  declare _hideAcknowledged: boolean;
  declare _priorities: Set<Priority>;
  declare _confirm?: { entityId: string; label: string };

  private _tick?: number;
  private _progressTick?: number;
  /** Whether the last render showed a progress bar, which needs frequent updates. */
  private _hasProgress = false;
  private _versionChecked = false;

  static styles = [sharedStyles, cardStyles];

  constructor() {
    super();
    this._busy = new Set();
    this._expanded = new Set();
    this._hideAcknowledged = false;
    this._priorities = new Set(PRIORITIES);
  }

  static getStubConfig(): Partial<AlertReduxCardConfig> {
    return {};
  }

  static getConfigForm() {
    const labels: Record<string, string> = {
      snooze_durations: "Snooze durations",
      areas: "Only these areas",
      labels: "Only these labels",
      hide_acknowledged: "Start with acknowledged alerts hidden",
      priorities: "Start with only these priorities shown",
    };
    const helpers: Record<string, string> = {
      snooze_durations: `The snooze menu, in minutes. Leave empty for ${DEFAULT_SNOOZE_DURATIONS.join(", ")}.`,
      areas: "The card shows only alerts in these areas. Leave empty for every alert.",
      labels: "The card shows only alerts with one of these labels. Leave empty for every alert.",
      priorities: "The priorities shown when the card loads; the card's own buttons change them. Leave empty for all.",
    };
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        {
          name: "snooze_durations",
          selector: { text: { multiple: true, type: "number", suffix: "min" } },
        },
        { name: "areas", selector: { area: { multiple: true } } },
        { name: "labels", selector: { label: { multiple: true } } },
        { name: "hide_acknowledged", selector: { boolean: {} } },
        {
          name: "priorities",
          selector: {
            select: {
              multiple: true,
              mode: "list",
              options: PRIORITIES.map((value) => ({ value, label: PRIORITY_NAMES[value] })),
            },
          },
        },
      ],
      computeLabel: (schema: { name: string }) => labels[schema.name],
      computeHelper: (schema: { name: string }) => helpers[schema.name],
    };
  }

  setConfig(config: AlertReduxCardConfig): void {
    this._config = config;
    this._hideAcknowledged = config.hide_acknowledged === true;
    this._priorities = viewPriorities(config.priorities);
  }

  /** The alerts in the card's scope: its areas and labels (spec §13.1). */
  private _scoped(): Alert[] {
    if (!this.hass) return [];
    const areas = asList(this._config?.areas);
    const labels = asList(this._config?.labels);
    const alerts = collectAlerts(this.hass);
    // Without the registry (a frontend too old to give it) the scope can't be told.
    if (!this.hass.entities) return alerts;
    return alerts.filter((alert) => inScope(this.hass!.entities![alert.entityId], areas, labels));
  }

  getCardSize(): number {
    if (!this.hass) return 2;
    const alerts = this._scoped();
    const groups = this._visible(groupSuperseded(alerts.filter(isListed).sort(compareFiring)));
    const shown = groups.reduce(
      (size, group) =>
        size +
        3 +
        (group.superseded.length
          ? 1 + (this._expanded.has(group.alert.entityId) ? group.superseded.length * 3 : 0)
          : 0),
      0,
    );
    const noData = alerts.filter((alert) => alert.state === "no_data").length;
    const disabled = alerts.some((alert) => alert.state === "disabled");
    return 1 + Math.max(1, shown) + (noData ? 1 + noData : 0) + (disabled ? 1 : 0);
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
    if (old.entities !== this.hass.entities && (this._config?.areas || this._config?.labels)) {
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
    const alerts = this._scoped();
    const firing = alerts.filter(isListed).sort(compareFiring);
    const allGroups = groupSuperseded(firing);
    const groups = this._visible(allGroups);
    const hidden = allGroups.reduce((n, g) => n + 1 + g.superseded.length, 0) -
      groups.reduce((n, g) => n + 1 + g.superseded.length, 0);
    const noData = alerts.filter((alert) => alert.state === "no_data").sort(compareNoData);
    const disabled = alerts.filter((alert) => alert.state === "disabled").length;
    const title = this._config.title;
    const dark = this.hass.themes?.darkMode ?? false;

    return html`
      <ha-card .header=${title || undefined}>
        <div class="content ${title ? "has-header" : ""} ${dark ? "dark" : "light"}">
          ${this._serverVersion ? this._renderBanner(this._serverVersion) : nothing}
          ${this._renderFilters(firing)}
          ${groups.length
            ? groups.map((group) => this._renderGroup(group))
            : html`<div class="empty">
                ${firing.length ? "No firing alerts match the filters." : "No alerts are firing."}
              </div>`}
          ${hidden && groups.length
            ? html`<div class="disabled-line">
                <ha-icon icon="mdi:filter-outline"></ha-icon>${hidden}
                ${hidden === 1 ? "alert" : "alerts"} hidden by the filters
              </div>`
            : nothing}
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

  /** The groups the view controls let through: judged by the alert at the root. */
  private _visible(groups: AlertGroup[]): AlertGroup[] {
    return groups.filter(
      ({ alert }) =>
        this._priorities.has(alert.priority) &&
        !(this._hideAcknowledged && alert.state === "ack"),
    );
  }

  /**
   * The view controls (spec §13.1): hide acknowledged alerts, and show only some
   * priorities. They're for changing while looking at the card; the card's
   * configuration only sets where they start.
   */
  private _renderFilters(firing: Alert[]) {
    const present = PRIORITIES.filter((p) => firing.some((alert) => alert.priority === p));
    const anyAcknowledged = firing.some((alert) => alert.state === "ack");
    if (present.length < 2 && !anyAcknowledged && !this._hideAcknowledged) return nothing;
    return html`<div class="filters" role="group" aria-label="Filters">
      ${anyAcknowledged || this._hideAcknowledged
        ? html`<button
            class="chip-button"
            aria-pressed=${this._hideAcknowledged ? "true" : "false"}
            @click=${() => (this._hideAcknowledged = !this._hideAcknowledged)}
          >
            <ha-icon icon="mdi:eye-off-outline"></ha-icon>Hide acknowledged
          </button>`
        : nothing}
      ${present.length > 1
        ? present.map(
            (priority) => html`<button
              class="chip-button p-${priority}"
              aria-pressed=${this._priorities.has(priority) ? "true" : "false"}
              @click=${() => this._togglePriority(priority)}
            >
              <span class="dot"></span>${PRIORITY_NAMES[priority]}
            </button>`,
          )
        : nothing}
    </div>`;
  }

  private _togglePriority(priority: Priority): void {
    const next = new Set(this._priorities);
    if (!next.delete(priority)) next.add(priority);
    this._priorities = next;
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

  /** An alert, and the alerts it supersedes behind a disclosure (spec §8.1). */
  private _renderGroup(group: AlertGroup) {
    const count = group.superseded.length;
    if (!count) return this._renderAlert(group.alert);
    const id = group.alert.entityId;
    const open = this._expanded.has(id);
    return html`
      ${this._renderAlert(group.alert)}
      <div class="superseded">
        <button
          class="disclosure"
          aria-expanded=${open ? "true" : "false"}
          @click=${() => this._toggleExpanded(id)}
        >
          <ha-icon icon=${open ? "mdi:chevron-down" : "mdi:chevron-right"}></ha-icon>${count}
          superseded ${count === 1 ? "alert" : "alerts"}
        </button>
        ${open ? group.superseded.map((alert) => this._renderAlert(alert)) : nothing}
      </div>
    `;
  }

  private _toggleExpanded(entityId: string): void {
    const expanded = new Set(this._expanded);
    if (!expanded.delete(entityId)) expanded.add(entityId);
    this._expanded = expanded;
  }

  private _renderAlert(alert: Alert) {
    const message = cardMessage(alert);
    const language = this.hass?.locale?.language;
    const since = alert.firingSince;
    const latched = isLatched(alert);
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
              ${latched && alert.lastEnded
                ? html`<span>·</span>
                    <span title=${alert.lastEnded.toLocaleString(language)}
                      >stopped ${elapsed(alert.lastEnded)} ago (at
                      ${clockTime(alert.lastEnded, language)})</span
                    >`
                : nothing}
              ${alert.fireCount > 1
                ? html`<span>·</span><span>fired ${alert.fireCount}×</span>`
                : nothing}
              ${latched
                ? html`<span
                    class="badge latched"
                    title="Stopped firing without being acknowledged; kept until it is"
                    ><ha-icon icon="mdi:pin-outline"></ha-icon>Unacknowledged</span
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
    const latched = isLatched(alert);
    const dismiss = alert.kind === "manual" && alert.userDismissable && !latched;
    if (!alert.acknowledgeable && !dismiss && !alert.buttons.length) return nothing;
    // A snoozed latched alert isn't acknowledged: it still offers Acknowledge.
    const snoozed = (alert.state === "ack" || latched) && alert.snoozedUntil;
    const menuOpen = this._snoozeMenu === alert.entityId;
    return html`
      <div class="controls">
        ${alert.buttons.map((label) => this._renderButton(alert, label, busy))}
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
        ${!alert.acknowledgeable || (snoozed && !latched)
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
   * One of the alert's custom buttons (spec §13.1). One marked "Require unlock"
   * turns into a confirmation first, since the dashboard has no unlocked phone to
   * rely on.
   */
  private _renderButton(alert: Alert, label: string, busy: boolean) {
    const confirming =
      this._confirm?.entityId === alert.entityId && this._confirm.label === label;
    if (confirming) {
      return html`<span class="confirm">
        Run "${label}"?
        <button class="primary" ?disabled=${busy} @click=${() => this._press(alert, label)}>
          Confirm
        </button>
        <button @click=${() => (this._confirm = undefined)}>Cancel</button>
      </span>`;
    }
    return html`<button
      ?disabled=${busy}
      @click=${() =>
        alert.unlockButtons.includes(label)
          ? (this._confirm = { entityId: alert.entityId, label })
          : this._press(alert, label)}
    >
      <ha-icon icon="mdi:gesture-tap-button"></ha-icon>${label}
    </button>`;
  }

  private _press(alert: Alert, label: string): void {
    this._confirm = undefined;
    void this._call(alert, "press_button", { label });
  }

  /**
   * The snooze durations, opened below the controls rather than floating over the
   * card, where the alert's box would clip it. A snoozed alert can also be kept
   * acknowledged, or unsnoozed.
   */
  private _renderSnoozeMenu(alert: Alert, busy: boolean) {
    const snoozed = alert.state === "ack" && alert.snoozedUntil;
    const latchedSnoozed = isLatched(alert) && alert.snoozedUntil;
    return html`
      <div class="choices" role="group" aria-label="Snooze for">
        <span class="label">${snoozed || latchedSnoozed ? "Snooze again for" : "Snooze for"}</span>
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
    service: "ack" | "unack" | "dismiss" | "snooze" | "press_button",
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
