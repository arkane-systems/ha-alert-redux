"""Repairs issues for legacy notify actions that don't exist (spec §9.2).

Legacy actions disappear as integrations move to notify entities; a member naming
one can't be sent to, so it's raised as an issue naming the group and the action.
The issues belong to whichever integration owns the notifier, which also supplies
the translation for the ISSUE_ACTION_MISSING key.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .model import ActionMember, GroupConfig

ISSUE_ACTION_MISSING = "notify_action_missing"


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
