"""Fixtures for alert_redux tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alert_redux.const import DOMAIN, SUBENTRY_ALERT

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration loading for every test in this suite."""
    yield


def alert_subentry(
    title: str,
    subentry_id: str | None = None,
    **data: Any,
) -> dict[str, Any]:
    """Return subentry data for a manual alert, with the form's defaults."""
    return _subentry(
        title, subentry_id, {"kind": "manual", "user_dismissable": False, **data}
    )


def state_alert(
    title: str,
    entity_id: str,
    target_state: str = "on",
    subentry_id: str | None = None,
    **data: Any,
) -> dict[str, Any]:
    """Return subentry data for a state alert."""
    return _subentry(
        title,
        subentry_id,
        {"kind": "state", "entity_id": entity_id, "target_state": target_state, **data},
    )


def template_alert(
    title: str,
    template: str,
    subentry_id: str | None = None,
    **data: Any,
) -> dict[str, Any]:
    """Return subentry data for a template alert."""
    return _subentry(
        title, subentry_id, {"kind": "template", "template": template, **data}
    )


def _subentry(
    title: str, subentry_id: str | None, data: dict[str, Any]
) -> dict[str, Any]:
    subentry: dict[str, Any] = {
        "title": title,
        "subentry_type": SUBENTRY_ALERT,
        "unique_id": None,
        "data": {"priority": "warning", "acknowledgeable": True, **data},
    }
    if subentry_id is not None:
        subentry["subentry_id"] = subentry_id
    return subentry


SetupAlerts = Callable[..., Awaitable[MockConfigEntry]]


@pytest.fixture
def setup_alerts(hass: HomeAssistant) -> SetupAlerts:
    """Return a function that sets up the integration with the given alerts."""

    async def _setup(
        *subentries: dict[str, Any], options: dict[str, Any] | None = None
    ) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Alert Redux",
            subentries_data=list(subentries),
            options=options or {},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup
