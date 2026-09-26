"""Repairs issues for Alert Redux's own configuration (not the repairs platform)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .const import (
    CONF_ALERT,
    CONF_NOTIFIER_GROUPS,
    CONF_SUPERSEDES,
    DOMAIN,
    ISSUE_BROKEN_REFERENCE,
    ISSUE_DEFAULT_GROUPS_UNSET,
    SUBENTRY_ALERT,
    SUBENTRY_GENERATOR,
)
from .model import Settings
from .supersession import relationship_targets


@callback
def async_check_default_groups(
    hass: HomeAssistant, entry: ConfigEntry, settings: Settings
) -> None:
    """Raise an issue while alerts (or generators) rely on default groups that
    aren't configured.

    Those alerts notify the fallback instead (spec §9.4); the issue says why, and
    goes away once default groups are set or no alert relies on them.
    """
    relying = [
        subentry.title
        for subentry in entry.subentries.values()
        # A generator's alerts share its groups (spec §12.3).
        if subentry.subentry_type in (SUBENTRY_ALERT, SUBENTRY_GENERATOR)
        and CONF_NOTIFIER_GROUPS not in subentry.data
    ]
    if settings.default_groups or not relying:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_DEFAULT_GROUPS_UNSET)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_DEFAULT_GROUPS_UNSET,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_DEFAULT_GROUPS_UNSET,
        translation_placeholders={
            "count": str(len(relying)),
            "alerts": ", ".join(sorted(relying)),
        },
    )


@callback
def async_check_broken_references(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise an issue for each reference to an alert that doesn't exist (§12.4).

    One per referring alert and missing alert; each goes away once the reference
    is fixed, or the missing alert comes back.
    """
    registry = er.async_get(hass)
    wanted: dict[str, dict[str, str]] = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_ALERT:
            continue
        watched = [subentry.data[CONF_ALERT]] if CONF_ALERT in subentry.data else []
        for target in (
            relationship_targets(subentry.data.get(CONF_SUPERSEDES, [])) + watched
        ):
            if (found := registry.async_get(target)) is None or found.platform != DOMAIN:
                issue_id = (
                    f"{ISSUE_BROKEN_REFERENCE}_{subentry_id}_{target.split('.', 1)[-1]}"
                )
                wanted[issue_id] = {"alert": subentry.title, "missing": target}
    prefix = f"{ISSUE_BROKEN_REFERENCE}_"
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(prefix) and issue_id not in wanted:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
    for issue_id, placeholders in wanted.items():
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_BROKEN_REFERENCE,
            translation_placeholders=placeholders,
        )
