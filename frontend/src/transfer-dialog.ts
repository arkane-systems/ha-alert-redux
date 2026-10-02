import { LitElement, css, html, nothing } from "lit";

import { describe, type Definition } from "./describe";
import "./dialog";
import { sharedStyles } from "./styles";
import type { HomeAssistant } from "./types";

/** What the alert_redux.export action returns (spec §16). */
interface ExportFile {
  alerts?: Definition[];
  generators?: Definition[];
}

type Mode = "summary" | "export" | "import";
type View = "summary" | "json";

const TITLES: Record<Mode, string> = {
  summary: "Settings summary",
  export: "Export definitions",
  import: "Import definitions",
};

const messageOf = (err: unknown): string =>
  (err as { message?: string } | undefined)?.message ?? String(err);

/** Copy text; the clipboard API needs a secure context, so fall back to selecting. */
async function copyText(text: string, field?: HTMLTextAreaElement | null): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    field?.select();
    return document.execCommand("copy");
  }
}

function downloadText(text: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * The admin card's dialogs for definitions (spec §13.2): the summary of an alert's
 * settings and the export of definitions (both made from the export action's
 * response), and the import of a file.
 */
export class AlertReduxTransferDialog extends LitElement {
  static properties = {
    hass: { attribute: false },
    mode: { type: String },
    entityId: { type: String },
    _json: { state: true },
    _summary: { state: true },
    _view: { state: true },
    _error: { state: true },
    _busy: { state: true },
    _note: { state: true },
    _input: { state: true },
    _overwrite: { state: true },
    _result: { state: true },
  };

  declare hass?: HomeAssistant;
  declare mode: Mode;
  /** The alert or generator sensor to export; unset is every definition. */
  declare entityId?: string;
  declare _json: string;
  declare _summary: string;
  declare _view: View;
  declare _error?: string;
  declare _busy: boolean;
  /** A short confirmation, e.g. that the text was copied. */
  declare _note?: string;
  declare _input: string;
  declare _overwrite: boolean;
  declare _result?: string;

  static styles = [
    sharedStyles,
    css`
      textarea {
        box-sizing: border-box;
        width: 100%;
        min-height: 220px;
        resize: vertical;
        padding: 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--secondary-background-color, transparent);
        color: var(--primary-text-color);
        font: 0.8rem/1.4 var(--code-font-family, monospace);
      }
      .views {
        display: flex;
        gap: 6px;
      }
      button.chip-button[aria-pressed="true"] {
        border-color: transparent;
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .hint {
        font-size: 0.85rem;
        color: var(--secondary-text-color);
      }
      pre {
        margin: 0;
        padding: 8px 10px;
        border-radius: 8px;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        font: 0.8rem/1.4 var(--code-font-family, monospace);
      }
      pre.error {
        background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent);
      }
      pre.result {
        background: color-mix(in srgb, var(--primary-text-color) 7%, transparent);
      }
      label.check {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    `,
  ];

  constructor() {
    super();
    this.mode = "export";
    this._json = "";
    this._summary = "";
    this._view = "json";
    this._busy = false;
    this._input = "";
    this._overwrite = false;
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (this.mode !== "import") {
      this._view = this.mode === "summary" ? "summary" : "json";
      void this._load();
    }
  }

  render() {
    return html`
      <alert-redux-dialog .heading=${TITLES[this.mode]} @closed=${this._close}>
        ${this.mode === "import" ? this._renderImport() : this._renderExport()}
        <button slot="actions" @click=${this._close}>Close</button>
        ${this.mode === "import"
          ? html`
              <button slot="actions" ?disabled=${this._busy || !this._input.trim()} @click=${() => this._import(true)}>
                Check
              </button>
              <button
                slot="actions"
                class="primary"
                ?disabled=${this._busy || !this._input.trim()}
                @click=${() => this._import(false)}
              >
                Import
              </button>
            `
          : html`
              <button slot="actions" ?disabled=${!this._text()} @click=${this._copy}>
                ${this._note ?? "Copy"}
              </button>
              ${this._view === "json"
                ? html`<button slot="actions" class="primary" ?disabled=${!this._json} @click=${this._download}>
                    Download
                  </button>`
                : nothing}
            `}
      </alert-redux-dialog>
    `;
  }

  private _renderExport() {
    return html`
      ${this.mode === "summary"
        ? html`<div class="views">
            ${(["summary", "json"] as const).map(
              (view) => html`<button
                class="chip-button"
                aria-pressed=${this._view === view ? "true" : "false"}
                @click=${() => (this._view = view)}
              >
                ${view === "summary" ? "Summary" : "Definition (JSON)"}
              </button>`,
            )}
          </div>`
        : nothing}
      ${this._error
        ? html`<pre class="error">${this._error}</pre>`
        : html`<textarea
            readonly
            aria-label=${TITLES[this.mode]}
            .value=${this._busy ? "Loading…" : this._text()}
          ></textarea>`}
      ${this._view === "json"
        ? html`<div class="hint">
            This is what the import action takes. Notifier groups are written by name and
            aren't included.
          </div>`
        : nothing}
    `;
  }

  private _renderImport() {
    return html`
      <div class="hint">
        Paste definitions exported from Alert Redux, or choose a file. Everything is
        checked first: if anything is wrong, nothing is imported.
      </div>
      <textarea
        aria-label="Definitions to import"
        placeholder='{"format": "alert_redux", "version": 1, "alerts": [], "generators": []}'
        .value=${this._input}
        @input=${(event: Event) => {
          this._input = (event.target as HTMLTextAreaElement).value;
          this._result = this._error = undefined;
        }}
      ></textarea>
      <input type="file" accept=".json,application/json" @change=${this._file} />
      <label class="check">
        <input
          type="checkbox"
          .checked=${this._overwrite}
          @change=${(event: Event) =>
            (this._overwrite = (event.target as HTMLInputElement).checked)}
        />
        Replace alerts and generators that already exist
      </label>
      ${this._error ? html`<pre class="error">${this._error}</pre>` : nothing}
      ${this._result ? html`<pre class="result">${this._result}</pre>` : nothing}
    `;
  }

  /** The text shown, copied, and downloaded. */
  private _text(): string {
    return this._view === "summary" ? this._summary : this._json;
  }

  private async _load(): Promise<void> {
    if (!this.hass) return;
    this._busy = true;
    try {
      const result = await this.hass.callService(
        "alert_redux",
        "export",
        this.entityId ? { entity_id: this.entityId } : {},
        undefined,
        false,
        true,
      );
      const file = (result?.response ?? {}) as ExportFile;
      this._json = JSON.stringify(file, null, 2);
      this._summary = [
        ...(file.alerts ?? []).map((definition) => describe(definition)),
        ...(file.generators ?? []).map((definition) => describe(definition, true)),
      ].join("\n\n");
    } catch (err) {
      this._error = messageOf(err);
    } finally {
      this._busy = false;
    }
  }

  private _copy = async (): Promise<void> => {
    const field = this.renderRoot.querySelector<HTMLTextAreaElement>("textarea");
    this._note = (await copyText(this._text(), field)) ? "Copied" : "Press Ctrl+C to copy";
    window.setTimeout(() => (this._note = undefined), 2000);
  };

  private _download = (): void => {
    const day = new Date().toISOString().slice(0, 10);
    const name = this.entityId ? this.entityId.split(".").pop() : day;
    downloadText(this._json, `alert-redux-${name}.json`);
  };

  private _file = async (event: Event): Promise<void> => {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this._input = await file.text();
    this._result = this._error = undefined;
  };

  /** Check the definitions (dryRun), or import them. */
  private async _import(dryRun: boolean): Promise<void> {
    if (!this.hass) return;
    this._error = this._result = undefined;
    let definitions: unknown;
    try {
      definitions = JSON.parse(this._input);
    } catch (err) {
      this._error = `This isn't valid JSON: ${messageOf(err)}`;
      return;
    }
    this._busy = true;
    try {
      const result = await this.hass.callService(
        "alert_redux",
        "import",
        { definitions, overwrite: this._overwrite, dry_run: dryRun },
        undefined,
        false,
        true,
      );
      this._result = this._resultText((result?.response ?? {}) as Record<string, unknown>, dryRun);
    } catch (err) {
      this._error = messageOf(err);
    } finally {
      this._busy = false;
    }
  }

  private _resultText(response: Record<string, unknown>, dryRun: boolean): string {
    const lines = [dryRun ? "Checked. Nothing has been changed." : "Imported."];
    for (const [key, label] of [
      ["created", dryRun ? "Would create" : "Created"],
      ["updated", dryRun ? "Would replace" : "Replaced"],
      ["unchanged", "Already the same"],
    ] as const) {
      const items = (response[key] as { name: string }[] | undefined) ?? [];
      if (items.length) lines.push(`${label}: ${items.map((item) => item.name).join(", ")}`);
    }
    return lines.join("\n");
  }

  private _close = (): void => {
    this.dispatchEvent(new CustomEvent("closed"));
  };
}

if (!customElements.get("alert-redux-transfer-dialog")) {
  customElements.define("alert-redux-transfer-dialog", AlertReduxTransferDialog);
}
