"""Tests for references to alerts that don't exist, and renames (spec §12.4)."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from custom_components.alert_redux.const import DOMAIN, SUBENTRY_ALERT

from .conftest import SetupAlerts, alert_state_alert, alert_subentry

OPEN = "alert_redux.back_door_open"
LEFT_OPEN = "alert_redux.back_door_left_open"
UNACKED = "alert_redux.back_door_unacknowledged"


def _issues(hass: HomeAssistant) -> dict[str, dict[str, str]]:
    return {
        issue_id: issue.translation_placeholders or {}
        for (domain, issue_id), issue in ir.async_get(hass).issues.items()
        if domain == DOMAIN and issue_id.startswith("broken_reference_")
    }


def _broken(hass: HomeAssistant, entity_id: str) -> list[str]:
    return hass.states.get(entity_id).attributes["broken_references"]


async def _call(hass: HomeAssistant, service: str, entity_id: str) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def _setup(setup_alerts: SetupAlerts) -> Any:
    return await setup_alerts(
        alert_subentry("Back Door Open", "open"),
        alert_subentry(
            "Back Door Left Open",
            "left",
            supersedes=[{"alert": OPEN, "propagation": "acknowledge"}],
        ),
        alert_state_alert("Back Door Unacknowledged", OPEN, ["active"], "unacked"),
    )


async def test_missing_references_at_startup(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(
        alert_subentry(
            "Back Door Left Open", "left", supersedes=[{"alert": "alert_redux.gone"}]
        ),
        alert_state_alert("Back Door Unacknowledged", "alert_redux.gone", ["active"]),
    )
    assert _broken(hass, LEFT_OPEN) == ["alert_redux.gone"]
    assert _broken(hass, UNACKED) == ["alert_redux.gone"]
    issues = _issues(hass)
    assert issues["broken_reference_left_gone"] == {
        "alert": "Back Door Left Open",
        "missing": "alert_redux.gone",
    }
    assert len(issues) == 2


async def test_deleted_then_recreated(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Deleting a referenced alert raises issues; recreating it clears them."""
    entry = await _setup(setup_alerts)
    assert _issues(hass) == {}
    assert _broken(hass, LEFT_OPEN) == []

    assert hass.config_entries.async_remove_subentry(entry, "open")
    await hass.async_block_till_done()
    assert _broken(hass, LEFT_OPEN) == [OPEN]
    assert _broken(hass, UNACKED) == [OPEN]
    assert set(_issues(hass)) == {
        "broken_reference_left_back_door_open",
        "broken_reference_unacked_back_door_open",
    }
    # Failing towards more noise: the alert state alert has no data.
    assert hass.states.get(UNACKED).state == "no_data"

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(alert_subentry("Back Door Open")["data"]),
            subentry_type=SUBENTRY_ALERT,
            title="Back Door Open",
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()
    assert hass.states.get(OPEN) is not None
    assert _issues(hass) == {}
    assert _broken(hass, LEFT_OPEN) == []
    assert hass.states.get(UNACKED).state == "idle"


async def test_editing_away_the_reference_clears_the_issue(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    entry = await setup_alerts(
        alert_subentry(
            "Back Door Left Open", "left", supersedes=[{"alert": "alert_redux.gone"}]
        )
    )
    assert _issues(hass)
    subentry = entry.subentries["left"]
    data = {key: value for key, value in subentry.data.items() if key != "supersedes"}
    hass.config_entries.async_update_subentry(entry, subentry, data=data)
    await hass.async_block_till_done()
    assert _issues(hass) == {}
    assert _broken(hass, LEFT_OPEN) == []


async def test_rename_is_followed(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Renaming an alert's entity ID rewrites the references to it."""
    entry = await _setup(setup_alerts)
    await _call(hass, "fire", OPEN)
    await _call(hass, "ack", OPEN)
    assert hass.states.get(LEFT_OPEN).attributes["pre_acked_by"] == [OPEN]

    renamed = "alert_redux.rear_door_open"
    er.async_get(hass).async_update_entity(OPEN, new_entity_id=renamed)
    await hass.async_block_till_done()

    assert entry.subentries["left"].data["supersedes"] == [
        {"alert": renamed, "propagation": "acknowledge"}
    ]
    assert entry.subentries["unacked"].data["alert"] == renamed
    assert _issues(hass) == {}
    left = hass.states.get(LEFT_OPEN).attributes
    assert left["supersedes"] == [renamed]
    assert left["broken_references"] == []
    assert left["pre_acked_by"] == [renamed]

    # Supersession works under the new ID.
    await _call(hass, "fire", LEFT_OPEN)
    assert hass.states.get(LEFT_OPEN).state == "ack"
    assert hass.states.get(renamed).attributes["superseded_by"] == [LEFT_OPEN]


async def test_reconfigure_lists_referrers(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The edit form stands in for a delete warning (spec §12.4)."""
    entry = await _setup(setup_alerts)
    for subentry_id, referrers in (
        ("open", "Back Door Left Open, Back Door Unacknowledged"),
        ("left", "none"),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_ALERT),
            context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
        )
        assert result["description_placeholders"] == {"referrers": referrers}
