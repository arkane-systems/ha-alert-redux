"""An alert's area and labels, in the entity registry (spec §11.6).

The registry is where they live. A new alert is given the area and labels its
configuration names once, when it is added, by the rule the alerts label follows
(§11.5): never forced back. A generated alert's placement comes from its generator
(§12.3), and a change to it is followed: the labels the generator added or removed,
and the area, but nothing the user set by hand.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .definitions import Placement

_LOGGER = logging.getLogger(__name__)


@callback
def async_apply_placement(
    hass: HomeAssistant, entity_id: str, placement: Placement
) -> None:
    """Give an alert its placement: the area, if one is named, and the labels
    added to those it has (the alerts label among them)."""
    registry = er.async_get(hass)
    if (entry := registry.async_get(entity_id)) is None:
        return
    area_id = placement.area_id if placement.area_id else entry.area_id
    labels = set(entry.labels) | placement.labels
    if area_id != entry.area_id or labels != set(entry.labels):
        _LOGGER.debug("Placing %s", entity_id)
        registry.async_update_entity(entity_id, area_id=area_id, labels=labels)


@callback
def async_follow_placement(
    hass: HomeAssistant,
    entity_id: str,
    old: Placement | None,
    new: Placement | None,
) -> None:
    """Follow a change in an alert's configured placement: remove the labels it
    no longer names, add the new ones, and set a new area. Labels and areas the
    configuration never gave it are left alone."""
    old = old or Placement()
    new = new or Placement()
    registry = er.async_get(hass)
    if (entry := registry.async_get(entity_id)) is None:
        return
    labels = (set(entry.labels) - (old.labels - new.labels)) | new.labels
    area_id = new.area_id if new.area_id and new.area_id != old.area_id else entry.area_id
    if area_id != entry.area_id or labels != set(entry.labels):
        registry.async_update_entity(entity_id, area_id=area_id, labels=labels)
