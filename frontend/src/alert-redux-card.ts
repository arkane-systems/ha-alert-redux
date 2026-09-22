import { LitElement, css, html } from "lit";

// Minimal slice of the frontend's `hass` object; grows as the cards need more of it.
interface HomeAssistant {
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
}

interface AlertReduxCardConfig {
  type: string;
  title?: string;
}

declare global {
  interface Window {
    customCards?: Array<{ type: string; name: string; description: string }>;
  }
}

class AlertReduxCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  declare hass?: HomeAssistant;
  declare _config?: AlertReduxCardConfig;

  setConfig(config: AlertReduxCardConfig): void {
    this._config = config;
  }

  getCardSize(): number {
    return 1;
  }

  static styles = css`
    .content {
      padding: 0 16px 16px;
      color: var(--secondary-text-color);
    }
  `;

  render() {
    return html`
      <ha-card .header=${this._config?.title ?? "Alerts"}>
        <div class="content">Alert Redux card — not yet implemented.</div>
      </ha-card>
    `;
  }
}

if (!customElements.get("alert-redux-card")) {
  customElements.define("alert-redux-card", AlertReduxCard);
  window.customCards = window.customCards ?? [];
  window.customCards.push({
    type: "alert-redux-card",
    name: "Alert Redux",
    description: "Shows and manages Alert Redux alerts.",
  });
  console.info(`%c ALERT-REDUX-CARD %c ${__CARD_VERSION__} `, "color:white;background:#b71c1c", "");
}
