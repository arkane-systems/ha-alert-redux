"""The label applied to every alert (spec §11.5).

Selecting this one label in a card that takes targets, such as the Activity card,
shows every alert, including alerts added later. It's created once, the first time
the integration sets up. Each alert is given it once, when it's first added, or, for
alerts that existed before the label, the first time they're added afterwards; the
alert's stored record remembers that. It's never forced back: if the label is
removed from an alert, or deleted altogether, that's left alone.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr

from .const import ALERTS_LABEL_DESCRIPTION, ALERTS_LABEL_ICON, ALERTS_LABEL_NAME
from .store import AlertStore

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_label(hass: HomeAssistant, store: AlertStore) -> str | None:
    """Return the alerts label's ID, creating it the first time.

    Returns None if the label has been deleted since it was created.
    """
    labels = lr.async_get(hass)
    if (label_id := store.label_id) is not None:
        return label_id if labels.async_get_label(label_id) is not None else None

    label = labels.async_get_label_by_name(ALERTS_LABEL_NAME) or labels.async_create(
        ALERTS_LABEL_NAME,
        icon=ALERTS_LABEL_ICON,
        description=ALERTS_LABEL_DESCRIPTION,
    )
    store.set_label_id(label.label_id)
    return label.label_id


@callback
def async_apply_label(hass: HomeAssistant, entity_id: str, label_id: str) -> None:
    """Add the alerts label to an alert, if the label still exists."""
    if lr.async_get(hass).async_get_label(label_id) is None:
        return
    registry = er.async_get(hass)
    if (registry_entry := registry.async_get(entity_id)) is None:
        return
    if label_id not in registry_entry.labels:
        _LOGGER.debug("Adding the alerts label to %s", entity_id)
        registry.async_update_entity(
            entity_id, labels=registry_entry.labels | {label_id}
        )
