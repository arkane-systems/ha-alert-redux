"""Repairs issues for Alert Redux's own configuration (not the repairs platform)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_NOTIFIER_GROUPS,
    DOMAIN,
    ISSUE_DEFAULT_GROUPS_UNSET,
    SUBENTRY_ALERT,
)
from .model import Settings


@callback
def async_check_default_groups(
    hass: HomeAssistant, entry: ConfigEntry, settings: Settings
) -> None:
    """Raise an issue while alerts rely on default groups that aren't configured.

    Those alerts notify the fallback instead (spec §9.4); the issue says why, and
    goes away once default groups are set or no alert relies on them.
    """
    relying = [
        subentry.title
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_ALERT
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
