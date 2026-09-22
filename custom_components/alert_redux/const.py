"""Constants for the Alert Redux integration."""

from __future__ import annotations

DOMAIN = "alert_redux"

# The bundled Lovelace card(s). The bundle is built from frontend/ at the repo root
# and committed under custom_components/alert_redux/frontend/ so that a plain HACS
# install ships it; the integration serves it and registers it as a resource.
CARD_FILENAME = "alert-redux-card.js"
CARD_URL_BASE = f"/{DOMAIN}/frontend"
CARD_URL = f"{CARD_URL_BASE}/{CARD_FILENAME}"
