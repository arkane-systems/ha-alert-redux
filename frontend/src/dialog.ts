import { LitElement, css, html } from "lit";

import { sharedStyles } from "./styles";

/**
 * A small modal dialog for the admin card: a heading, a body, and a row of buttons
 * (the "actions" slot). It is a native <dialog>, shown modally, so it sits in the
 * browser's top layer whatever the card's surroundings are. It closes on Escape and
 * on a click outside it, by firing "closed"; whoever opened it removes it.
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
        display: contents;
      }
      dialog {
        box-sizing: border-box;
        width: calc(100% - 32px);
        max-width: 640px;
        max-height: calc(100% - 32px);
        padding: 0;
        border: none;
        border-radius: 16px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        overflow: hidden;
      }
      .inner {
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-sizing: border-box;
        max-height: calc(100vh - 32px);
        padding: 20px;
      }
      dialog::backdrop {
        background: rgba(0, 0, 0, 0.5);
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
    this.renderRoot.querySelector("dialog")?.showModal();
  }

  render() {
    return html`
      <dialog
        aria-label=${this.heading}
        @click=${this._click}
        @close=${this._close}
        @cancel=${this._close}
      >
        <div class="inner">
          <h2>${this.heading}</h2>
          <div class="body"><slot></slot></div>
          <div class="actions"><slot name="actions"></slot></div>
        </div>
      </dialog>
    `;
  }

  /** A click on the dialog element itself, not its content, is on the backdrop. */
  private _click(event: MouseEvent): void {
    // Only the backdrop is the dialog element itself; the padding is inside .inner.
    if (event.target === event.currentTarget) this._close(event);
  }

  private _close = (event: Event): void => {
    // The native close would follow; the owner removes the element.
    event.preventDefault();
    this.dispatchEvent(new CustomEvent("closed"));
  };
}

if (!customElements.get("alert-redux-dialog")) {
  customElements.define("alert-redux-dialog", AlertReduxDialog);
}
