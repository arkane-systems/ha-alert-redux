import { LitElement, css, html } from "lit";

import { sharedStyles } from "./styles";

/**
 * A small modal dialog for the admin card: a heading, a body, and a row of buttons
 * (the "actions" slot). It closes on Escape and on a click outside it, by firing
 * "closed"; whoever opened it removes it.
 */
export class AlertReduxDialog extends LitElement {
  static properties = {
    heading: { type: String },
  };

  declare heading: string;

  static styles = [
    sharedStyles,
    css`
      :host {
        position: fixed;
        inset: 0;
        z-index: 8;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
        box-sizing: border-box;
        background: rgba(0, 0, 0, 0.5);
      }
      .dialog {
        display: flex;
        flex-direction: column;
        gap: 12px;
        width: 100%;
        max-width: 640px;
        max-height: 100%;
        box-sizing: border-box;
        padding: 20px;
        border-radius: 16px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      }
      .dialog:focus {
        outline: none;
      }
      h2 {
        margin: 0;
        font-size: 1.25rem;
        font-weight: 500;
      }
      .body {
        display: flex;
        flex-direction: column;
        gap: 10px;
        min-height: 0;
        overflow: auto;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
      }
    `,
  ];

  constructor() {
    super();
    this.heading = "";
  }

  protected firstUpdated(): void {
    this.renderRoot.querySelector<HTMLElement>(".dialog")?.focus();
  }

  render() {
    return html`
      <div
        class="dialog"
        role="dialog"
        aria-modal="true"
        aria-label=${this.heading}
        tabindex="-1"
        @click=${(event: Event) => event.stopPropagation()}
        @keydown=${this._keydown}
      >
        <h2>${this.heading}</h2>
        <div class="body"><slot></slot></div>
        <div class="actions"><slot name="actions"></slot></div>
      </div>
    `;
  }

  connectedCallback(): void {
    super.connectedCallback();
    // A click that reaches the host is outside the dialog.
    this.addEventListener("click", this._close);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.removeEventListener("click", this._close);
  }

  private _keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.stopPropagation();
      this._close();
    }
  }

  private _close = (): void => {
    this.dispatchEvent(new CustomEvent("closed"));
  };
}

if (!customElements.get("alert-redux-dialog")) {
  customElements.define("alert-redux-dialog", AlertReduxDialog);
}
