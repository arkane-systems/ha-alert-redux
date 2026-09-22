# Alert Redux

A replacement alert system for Home Assistant, intended to take over from the
now-deprecated built-in `alert` integration.

> **Status:** early development. The repository currently contains the integration and
> card scaffolding only; no alerting functionality exists yet.

## Installation

### HACS

1. In HACS, add `https://github.com/arkane-systems/ha-alert-redux` as a custom
   repository of type **Integration**.
2. Install **Alert Redux** and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and add **Alert Redux**.

### Manual

Copy `custom_components/alert_redux/` into your Home Assistant `config/custom_components/`
directory, restart Home Assistant, and add the integration as above.

## Lovelace card

The Alert Redux card is bundled with the integration: there is no separate frontend
install and no need to add a dashboard resource by hand. When the integration is set
up, it serves the card and registers it as a dashboard resource automatically. (On
YAML-mode dashboards, it is loaded app-wide instead.)

Add it to a dashboard as a **Custom: Alert Redux** card, or in YAML:

```yaml
type: custom:alert-redux-card
title: Alerts
```

## License

MIT; see [LICENSE](LICENSE).
