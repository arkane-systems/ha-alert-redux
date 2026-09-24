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
    subentry: dict[str, Any] = {
        "title": title,
        "subentry_type": SUBENTRY_ALERT,
        "unique_id": None,
        "data": {
            "kind": "manual",
            "priority": "warning",
            "acknowledgeable": True,
            "user_dismissable": False,
            **data,
        },
    }
    if subentry_id is not None:
        subentry["subentry_id"] = subentry_id
    return subentry


SetupAlerts = Callable[..., Awaitable[MockConfigEntry]]


@pytest.fixture
def setup_alerts(hass: HomeAssistant) -> SetupAlerts:
    """Return a function that sets up the integration with the given alerts."""

    async def _setup(*subentries: dict[str, Any]) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN, title="Alert Redux", subentries_data=list(subentries)
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup
