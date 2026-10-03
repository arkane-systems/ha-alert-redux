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
import "./dialog";
import "./flow-dialog";
import { deleteSubentry, entryId, subentryOf, type SubentryType } from "./flow-client";
import "./transfer-dialog";
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
    _page: { state: true },
    _listMin: { state: true },
    _transfer: { state: true },
    _flow: { state: true },
    _delete: { state: true },
  };

  declare hass?: HomeAssistant;
  declare _config?: AlertReduxAdminCardConfig;
  /** Entity IDs with an action in flight, so their buttons can't be pressed twice. */
  declare _busy: Set<string>;
  /** The entity ID whose suspend menu is open, if any. */
  declare _menu?: string;
  /** Whether the open suspend menu is showing its date and time field. */
  declare _untilOpen: boolean;
  /** The page shown, from 0; kept within the pages there are. */
  declare _page: number;
  /**
   * With paging, the tallest the list has been at this page size and number of
   * alerts. The list keeps at least this height, so a short last page doesn't
   * shrink the card and shuffle the dashboard's other cards.
   */
  declare _listMin: number;
  private _pagingKey = "";
  /** The summary, export, or import dialog that's open, if any. */
  /** The flow dialog that's open: to add (no subentry), or edit, an alert or generator. */
  declare _flow?: { type: SubentryType; entryId: string; subentryId?: string };
  /** The deletion awaiting confirmation. */
  declare _delete?: {
    alert: Alert;
    entryId: string;
    subentryId: string;
    generator: boolean;
    referrers: string[];
  };
  declare _transfer?: { mode: "summary" | "export" | "import"; entityId?: string };

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
      .generated,
      .superseded {
        font-style: italic;
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
      .state.latched {
        background: color-mix(in srgb, var(--c) 22%, transparent);
        outline: 1px dashed var(--c);
        outline-offset: -1px;
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
      .toolbar {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
      }
      .toolbar button {
        white-space: nowrap;
        padding: 4px 12px;
        font-size: 0.8rem;
        --mdc-icon-size: 16px;
      }
      .list-inner {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .pager {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        color: var(--secondary-text-color);
        font-size: 0.85rem;
      }
    `,
  ];

  constructor() {
    super();
    this._busy = new Set();
    this._untilOpen = false;
    this._page = 0;
    this._listMin = 0;
  }

  static getStubConfig(): Partial<AlertReduxAdminCardConfig> {
    return {};
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "page_size", selector: { number: { min: 1, mode: "box" } } },
      ],
    };
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

  protected willUpdate(): void {
    // A different page size, or a different number of alerts, starts the height over.
    const key = `${this._pageSize()}:${this.hass ? collectAlerts(this.hass).length : 0}`;
    if (key !== this._pagingKey) {
      this._pagingKey = key;
      this._listMin = 0;
    }
  }

  protected updated(): void {
    if (!this._pageSize()) return;
    const height = this.renderRoot.querySelector<HTMLElement>(".list-inner")?.offsetHeight ?? 0;
    if (height > this._listMin) this._listMin = height;
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

  /** The page size: a whole number of at least 1, or none (all on one page). */
  private _pageSize(): number | undefined {
    const size = Math.floor(Number(this._config?.page_size));
    return size >= 1 ? size : undefined;
  }

  render() {
    if (!this.hass || !this._config) return nothing;
    // In card order: by priority, then by name.
    const alerts = collectAlerts(this.hass);
    const ordered = PRIORITIES.flatMap((priority) =>
      alerts.filter((alert) => alert.priority === priority).sort(compareName),
    );
    const size = this._pageSize();
    const pages = size ? Math.ceil(ordered.length / size) : 1;
    const page = Math.min(this._page, Math.max(pages - 1, 0));
    const shown = size ? ordered.slice(page * size, (page + 1) * size) : ordered;
    const title = this._config.title;
    const admin = this.hass.user?.is_admin ?? false;
    return html`
      <ha-card .header=${title || undefined}>
        <div class="content ${title ? "has-header" : ""}">
          <div class="toolbar">
            <button @click=${() => (this._transfer = { mode: "export" })}>
              <ha-icon icon="mdi:export"></ha-icon>Export
            </button>
            ${admin
              ? html`<button @click=${() => (this._transfer = { mode: "import" })}>
                    <ha-icon icon="mdi:import"></ha-icon>Import
                  </button>
                  <button @click=${() => this._add("alert")}>
                    <ha-icon icon="mdi:plus"></ha-icon>Add alert
                  </button>
                  <button @click=${() => this._add("generator")}>
                    <ha-icon icon="mdi:plus"></ha-icon>Add generator
                  </button>`
              : nothing}
          </div>
          <div class="list" style=${pages > 1 ? `min-height: ${this._listMin}px` : ""}>
            <div class="list-inner">${this._renderGroups(alerts, shown)}</div>
          </div>
          ${pages > 1 ? this._renderPager(page, pages) : nothing}
        </div>
      </ha-card>
      ${this._flow
        ? html`<alert-redux-flow-dialog
            .hass=${this.hass}
            .subentryType=${this._flow.type}
            .entryId=${this._flow.entryId}
            .subentryId=${this._flow.subentryId}
            @closed=${() => (this._flow = undefined)}
          ></alert-redux-flow-dialog>`
        : nothing}
      ${this._delete ? this._renderDelete(this._delete) : nothing}
      ${this._transfer
        ? html`<alert-redux-transfer-dialog
            .hass=${this.hass}
            .mode=${this._transfer.mode}
            .entityId=${this._transfer.entityId}
            @closed=${() => (this._transfer = undefined)}
          ></alert-redux-transfer-dialog>`
        : nothing}
    `;
  }

  private _renderGroups(alerts: Alert[], shown: Alert[]) {
    if (!shown.length) return html`<div class="empty">No alerts are configured.</div>`;
    return PRIORITIES.map((priority) => {
      const group = shown.filter((alert) => alert.priority === priority);
      if (!group.length) return nothing;
      // The heading counts the priority's alerts on every page.
      const total = alerts.filter((alert) => alert.priority === priority).length;
      return html`
        <div class="section-title p-${priority}">
          <span class="dot"></span>${PRIORITY_NAMES[priority]} (${total})
        </div>
        <div class="group">${group.map((alert) => this._renderRow(alert))}</div>
      `;
    });
  }

  private _renderPager(page: number, pages: number) {
    return html`
      <div class="pager">
        <button
          class="chip-button"
          aria-label="Previous page"
          ?disabled=${page === 0}
          @click=${() => (this._page = page - 1)}
        >
          <ha-icon icon="mdi:chevron-left"></ha-icon>
        </button>
        <span>Page ${page + 1} of ${pages}</span>
        <button
          class="chip-button"
          aria-label="Next page"
          ?disabled=${page >= pages - 1}
          @click=${() => (this._page = page + 1)}
        >
          <ha-icon icon="mdi:chevron-right"></ha-icon>
        </button>
      </div>
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
              ${this._kind(alert)}${this._generated(alert)} ·
              <span class="state ${alert.state}">${this._state(alert)}</span>
              ${this._detail(alert)}${this._superseded(alert)}
            </div>
          </div>
          <div class="controls">
            <button
              aria-label=${`Settings summary of ${alert.name}`}
              title="Settings summary"
              @click=${() => (this._transfer = { mode: "summary", entityId: alert.entityId })}
            >
              <ha-icon icon="mdi:text-box-outline"></ha-icon>
            </button>
            ${admin
              ? html`<button
                    aria-label=${`Edit ${alert.name}`}
                    title="Edit"
                    ?disabled=${busy}
                    @click=${() => this._edit(alert)}
                  >
                    <ha-icon icon="mdi:pencil-outline"></ha-icon>
                  </button>
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
                  <button
                    aria-label=${`Delete ${alert.name}`}
                    title="Delete"
                    ?disabled=${busy}
                    @click=${() => this._confirmDelete(alert)}
                  >
                    <ha-icon icon="mdi:delete-outline"></ha-icon>
                  </button>`
              : nothing}
          </div>
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

  private _renderDelete(pending: NonNullable<AlertReduxAdminCard["_delete"]>) {
    const { alert, generator, referrers } = pending;
    return html`
      <alert-redux-dialog
        .heading=${generator ? "Delete generator?" : "Delete alert?"}
        @closed=${() => (this._delete = undefined)}
      >
        <div>
          ${generator
            ? html`This deletes <b>${this._generatorName(alert)}</b> and all the alerts it makes.`
            : html`This deletes <b>${alert.name}</b>.`}
          Its history stays in the logbook.
        </div>
        ${referrers.length
          ? html`<div>
              Alerts that refer to it will keep working but get a Repairs issue:
              ${referrers.join(", ")}.
            </div>`
          : nothing}
        <button slot="actions" @click=${() => (this._delete = undefined)}>Cancel</button>
        <button slot="actions" class="primary" @click=${() => this._deleteNow(pending)}>
          Delete
        </button>
      </alert-redux-dialog>
    `;
  }

  private _generatorName(alert: Alert): string {
    const sensor = alert.generatedBy ? this.hass?.states[alert.generatedBy] : undefined;
    const name = String(sensor?.attributes.friendly_name ?? alert.generatedBy ?? alert.name);
    return name.replace(/^Alert Redux generator /, "");
  }

  /** Add an alert or generator: the flow's own first step asks what kind. */
  private async _add(type: SubentryType): Promise<void> {
    if (!this.hass) return;
    try {
      const id = await entryId(this.hass);
      if (id) this._flow = { type, entryId: id };
    } catch (err) {
      this._notify(err);
    }
  }

  /** Edit an alert, or for a generated alert its generator (§12.3). */
  private async _edit(alert: Alert): Promise<void> {
    const target = await this._target(alert);
    if (target) this._flow = target;
  }

  private async _confirmDelete(alert: Alert): Promise<void> {
    const target = await this._target(alert);
    if (!target?.subentryId) return;
    const referrers = Object.values(this.hass?.states ?? {})
      .filter(
        (entity) =>
          isAlertEntity(entity.entity_id) &&
          Array.isArray(entity.attributes.supersedes) &&
          (entity.attributes.supersedes as string[]).includes(alert.entityId),
      )
      .map((entity) => String(entity.attributes.friendly_name ?? entity.entity_id));
    this._delete = {
      alert,
      entryId: target.entryId,
      subentryId: target.subentryId,
      generator: target.type === "generator",
      referrers,
    };
  }

  private async _deleteNow(pending: NonNullable<AlertReduxAdminCard["_delete"]>): Promise<void> {
    this._delete = undefined;
    if (!this.hass) return;
    try {
      await deleteSubentry(this.hass, pending.entryId, pending.subentryId);
    } catch (err) {
      this._notify(err);
    }
  }

  /** The subentry that defines an alert: its own, or its generator's. */
  private async _target(
    alert: Alert,
  ): Promise<{ type: SubentryType; entryId: string; subentryId: string } | undefined> {
    if (!this.hass) return undefined;
    try {
      const found = await subentryOf(this.hass, alert.generatedBy ?? alert.entityId);
      return found && { type: alert.generatedBy ? "generator" : "alert", ...found };
    } catch (err) {
      this._notify(err);
      return undefined;
    }
  }

  private _notify(err: unknown): void {
    this._fire("hass-notification", {
      message: (err as { message?: string } | undefined)?.message ?? String(err),
    });
  }

  private _kind(alert: Alert): string {
    const entity = this.hass?.states[alert.entityId];
    const text = entity ? this.hass?.formatEntityAttributeValue?.(entity, "kind") : undefined;
    return text && text !== alert.kind ? text : (KIND_NAMES[alert.kind] ?? alert.kind);
  }

  /** Marks a generated alert, which is edited through its generator (§12.3). */
  private _generated(alert: Alert) {
    if (!alert.generatedBy) return nothing;
    const generator = this.hass?.states[alert.generatedBy];
    const name = generator?.attributes.friendly_name ?? alert.generatedBy;
    return html`, <span class="generated" title=${`Generated by ${name}`}>generated</span>`;
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
    if ((alert.state === "ack" || alert.state === "latched") && alert.snoozedUntil) {
      return html`snoozed until ${clockTime(alert.snoozedUntil, language)}`;
    }
    if (alert.state === "latched" && alert.lastEnded) {
      return html`stopped ${clockTime(alert.lastEnded, language)}`;
    }
    if (isFiring(alert) && alert.firingSince) {
      return html`since ${clockTime(alert.firingSince, language)}`;
    }
    if (alert.state === "no_data" && alert.noDataSince) {
      return html`for ${elapsed(alert.noDataSince)}`;
    }
    return nothing;
  }

  /**
   * Marks a firing alert that another is superseding (§8.1): the highest
   * priority superseder by name, and a count of any others, all in the tooltip.
   */
  private _superseded(alert: Alert) {
    if (!isFiring(alert) || !alert.supersededBy.length) return nothing;
    const names = alert.supersededBy.map(
      (id) => this.hass?.states[id]?.attributes.friendly_name ?? id,
    );
    const more = names.length > 1 ? ` +${names.length - 1}` : "";
    return html` · <span class="superseded" title=${`Superseded by ${names.join(", ")}`}
        >superseded by ${names[0]}${more}</span
      >`;
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
      this._notify(err);
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
    description: "Lists every Alert Redux alert, shows its settings, exports and imports definitions, and lets admins add, edit, delete, disable, enable, and suspend alerts.",
  });
}
