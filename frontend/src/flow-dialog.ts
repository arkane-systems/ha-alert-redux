import { LitElement, css, html, nothing } from "lit";

import "./dialog";
import {
  cancelFlow,
  dataToSend,
  initialData,
  startFlow,
  stepFlow,
  type FlowStep,
  type SchemaItem,
  type SubentryType,
} from "./flow-client";
import { sharedStyles } from "./styles";
import type { HomeAssistant } from "./types";

const DOMAIN = "alert_redux";
const SETTINGS_PATH = `/config/integrations/integration/${DOMAIN}`;

type Values = Record<string, string | number> | undefined;

/**
 * Load Home Assistant's form element, which it loads only where it uses it: the
 * dashboard editor's cards do, so creating one of those pulls it in.
 */
async function ensureForm(): Promise<boolean> {
  if (customElements.get("ha-form")) return true;
  try {
    const helpers = await (
      window as unknown as { loadCardHelpers?: () => Promise<Record<string, unknown>> }
    ).loadCardHelpers?.();
    const create = helpers?.createCardElement as
      | ((config: object) => Promise<{ constructor: { getConfigElement?: () => Promise<unknown> } }>)
      | undefined;
    const card = await create?.({ type: "entities", entities: [] });
    await card?.constructor.getConfigElement?.();
  } catch {
    // Handled below: the form element is simply not there.
  }
  return Boolean(customElements.get("ha-form"));
}

const messageOf = (err: unknown): string =>
  (err as { message?: string } | undefined)?.message ?? String(err);

/**
 * Creates or edits an alert or generator by driving Home Assistant's own subentry
 * flow (spec §13.2), so that every check the forms make is made, with the same
 * words: a step's form is shown with Home Assistant's form element, labelled from
 * the integration's translations.
 */
export class AlertReduxFlowDialog extends LitElement {
  static properties = {
    hass: { attribute: false },
    subentryType: { type: String },
    entryId: { type: String },
    subentryId: { type: String },
    _step: { state: true },
    _data: { state: true },
    _error: { state: true },
    _busy: { state: true },
    _unavailable: { state: true },
  };

  declare hass?: HomeAssistant;
  declare subentryType: SubentryType;
  declare entryId: string;
  /** To edit: the subentry. Unset adds a new one. */
  declare subentryId?: string;
  declare _step?: FlowStep;
  declare _data: Record<string, unknown>;
  declare _error?: string;
  declare _busy: boolean;
  /** Whether Home Assistant's form element couldn't be loaded here. */
  declare _unavailable: boolean;

  static styles = [
    sharedStyles,
    css`
      .description {
        font-size: 0.9rem;
        color: var(--secondary-text-color);
        overflow-wrap: anywhere;
      }
      .menu {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .menu button {
        justify-content: flex-start;
        border-radius: 12px;
        text-align: left;
      }
      .error {
        padding: 8px 10px;
        border-radius: 8px;
        color: var(--primary-text-color);
        background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent);
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
    `,
  ];

  constructor() {
    super();
    this.subentryType = "alert";
    this._data = {};
    this._busy = false;
    this._unavailable = false;
  }

  connectedCallback(): void {
    super.connectedCallback();
    void this._begin();
  }

  private async _begin(): Promise<void> {
    const hass = this.hass;
    if (!hass) return;
    this._busy = true;
    try {
      // The words come from the integration's own translations.
      await Promise.all([
        hass.loadBackendTranslation?.("config_subentries", DOMAIN),
        hass.loadBackendTranslation?.("selector", DOMAIN),
      ]);
      if (!(await ensureForm())) {
        this._unavailable = true;
        return;
      }
      this._setStep(await startFlow(hass, this.entryId, this.subentryType, this.subentryId));
    } catch (err) {
      this._error = messageOf(err);
    } finally {
      this._busy = false;
    }
  }

  /** Take the next step; a finished flow closes the dialog. */
  private _setStep(step: FlowStep): void {
    this._error = undefined;
    if (step.type === "create_entry" || (step.type === "abort" && step.reason === "reconfigure_successful")) {
      this._step = undefined;
      this.dispatchEvent(new CustomEvent("saved"));
      this._finish();
      return;
    }
    this._step = step;
    if (step.type === "form") this._data = initialData(step.data_schema ?? []);
  }

  /** Home Assistant's translation of a key under this flow's strings. */
  private _t(path: string, values?: Values): string {
    return (
      this.hass?.localize?.(`component.${DOMAIN}.config_subentries.${this.subentryType}.${path}`, values) ?? ""
    );
  }

  private _stepText(step: FlowStep, part: "title" | "description"): string {
    return this._t(`step.${step.step_id}.${part}`, step.description_placeholders ?? undefined);
  }

  render() {
    const step = this._step;
    const heading =
      (step && this._stepText(step, "title")) ||
      (this.subentryId ? "Edit" : this.subentryType === "alert" ? "Add an alert" : "Add a generator");
    return html`
      <alert-redux-dialog .heading=${heading} @closed=${this._cancel}>
        ${this._unavailable ? this._renderUnavailable() : this._renderStep(step)}
        ${this._error ? html`<div class="error">${this._error}</div>` : nothing}
        <button slot="actions" @click=${this._cancel}>
          ${step?.type === "abort" || this._unavailable ? "Close" : "Cancel"}
        </button>
        ${step?.type === "form"
          ? html`<button slot="actions" class="primary" ?disabled=${this._busy} @click=${this._submit}>
              Submit
            </button>`
          : nothing}
      </alert-redux-dialog>
    `;
  }

  private _renderUnavailable() {
    return html`
      <div class="description">
        This page can't show Home Assistant's forms. Use the Alert Redux page in Home
        Assistant's settings instead.
      </div>
      <button @click=${this._openSettings}>Open Alert Redux settings</button>
    `;
  }

  private _renderStep(step?: FlowStep) {
    if (!step) return this._busy ? html`<div class="description">Loading…</div>` : nothing;
    const description = this._stepText(step, "description");
    const text = description
      ? html`<ha-markdown class="description" breaks .content=${description}></ha-markdown>`
      : nothing;
    if (step.type === "menu") {
      const options = Array.isArray(step.menu_options)
        ? step.menu_options
        : Object.keys(step.menu_options ?? {});
      return html`${text}
        <div class="menu">
          ${options.map(
            (option) => html`<button
              ?disabled=${this._busy}
              @click=${() => this._send({ next_step_id: option })}
            >
              ${this._t(`step.${step.step_id}.menu_options.${option}`) || option}
            </button>`,
          )}
        </div>`;
    }
    if (step.type === "form") {
      // ha-form shows a form-wide (base) error itself, above the fields.
      const errors = step.errors ?? {};
      return html`${text}
        <ha-form
          .hass=${this.hass}
          .data=${this._data}
          .schema=${step.data_schema ?? []}
          .error=${errors}
          .computeLabel=${this._label(step)}
          .computeHelper=${this._helper(step)}
          .computeError=${(error: string) => this._t(`error.${error}`) || error}
          @value-changed=${(event: CustomEvent) => (this._data = event.detail.value)}
        ></ha-form>`;
    }
    if (step.type === "abort") {
      return html`<div class="description">
        ${this._t(`abort.${step.reason}`) || step.reason}
      </div>`;
    }
    return html`<div class="description">Working…</div>`;
  }

  /** A field's label: sections have their own data under the section's name. */
  private _label(step: FlowStep) {
    return (schema: SchemaItem, _data: unknown, options?: { path?: string[] }) => {
      const base = `step.${step.step_id}`;
      if (schema.type === "expandable") {
        return this._t(`${base}.sections.${schema.name}.name`) || schema.name;
      }
      const section = options?.path?.[0];
      const key = section
        ? `${base}.sections.${section}.data.${schema.name}`
        : `${base}.data.${schema.name}`;
      return this._t(key) || schema.name;
    };
  }

  private _helper(step: FlowStep) {
    return (schema: SchemaItem, options?: { path?: string[] }) => {
      const base = `step.${step.step_id}`;
      const section = options?.path?.[0];
      return this._t(
        section
          ? `${base}.sections.${section}.data_description.${schema.name}`
          : `${base}.data_description.${schema.name}`,
      );
    };
  }

  private _submit = (): void => {
    void this._send(dataToSend(this._data));
  };

  private async _send(data: Record<string, unknown>): Promise<void> {
    const step = this._step;
    if (!this.hass || !step) return;
    this._busy = true;
    try {
      this._setStep(await stepFlow(this.hass, step.flow_id, data));
    } catch (err) {
      this._error = messageOf(err);
    } finally {
      this._busy = false;
    }
  }

  private _openSettings = (): void => {
    history.pushState(null, "", SETTINGS_PATH);
    window.dispatchEvent(new CustomEvent("location-changed"));
    this._finish();
  };

  /** Abandon the flow, if it's still open, and close. */
  private _cancel = (): void => {
    const step = this._step;
    if (this.hass && step && (step.type === "form" || step.type === "menu")) {
      cancelFlow(this.hass, step.flow_id).catch(() => undefined);
    }
    this._finish();
  };

  private _finish(): void {
    this.dispatchEvent(new CustomEvent("closed"));
  }
}

if (!customElements.get("alert-redux-flow-dialog")) {
  customElements.define("alert-redux-flow-dialog", AlertReduxFlowDialog);
}
