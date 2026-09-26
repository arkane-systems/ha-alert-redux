"""Repairs issues for what the notifier needs but can't find.

Legacy actions disappear as integrations move to notify entities; a member naming
one can't be sent to, so it's raised as an issue naming the group and the action
(spec §9.2). A quiet-hours entity that doesn't exist means quiet hours never
apply, so that's raised too (§9.9). The issues belong to whichever integration
owns the notifier, which also supplies the translations for the ISSUE_* keys.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .model import ActionMember, GroupConfig

ISSUE_ACTION_MISSING = "notify_action_missing"
ISSUE_QUIET_ENTITY_MISSING = "quiet_entity_missing"


def issue_id(group_id: str, member: ActionMember) -> str:
    """Return the issue ID for a group's missing action."""
    return f"{ISSUE_ACTION_MISSING}_{group_id}_{member.action}"


@callback
def async_raise_action_missing(
    hass: HomeAssistant, domain: str, group: GroupConfig, member: ActionMember
) -> str:
    """Raise the issue for a missing action, returning its ID."""
    ident = issue_id(group.id, member)
    ir.async_create_issue(
        hass,
        domain,
        ident,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_ACTION_MISSING,
        translation_placeholders={"group": group.name, "action": str(member)},
    )
    return ident


@callback
def async_clear_issue(hass: HomeAssistant, domain: str, ident: str) -> None:
    """Delete an issue."""
    ir.async_delete_issue(hass, domain, ident)


def quiet_issue_id(entity_id: str) -> str:
    """Return the issue ID for a missing quiet-hours entity."""
    return f"{ISSUE_QUIET_ENTITY_MISSING}_{entity_id}"


@callback
def async_raise_quiet_entity_missing(
    hass: HomeAssistant, domain: str, entity_id: str, used_by: str
) -> str:
    """Raise the issue for a missing quiet-hours entity, returning its ID.

    used_by says where it's set: the global setting, or the groups' names.
    """
    ident = quiet_issue_id(entity_id)
    ir.async_create_issue(
        hass,
        domain,
        ident,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_QUIET_ENTITY_MISSING,
        translation_placeholders={"entity": entity_id, "used_by": used_by},
    )
    return ident
