"""Smoke tests covering the config flow and card registration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alert_redux.const import CARD_URL, DOMAIN


async def test_config_flow_creates_entry(hass: HomeAssistant) -> None:
    """The user config flow creates a single entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Alert Redux"


async def test_config_flow_single_instance(hass: HomeAssistant) -> None:
    """A second config flow aborts because only one instance is allowed."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_setup_registers_card_resource(hass: HomeAssistant) -> None:
    """Setting up the entry registers the card as a Lovelace resource."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "lovelace", {})

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    resources = hass.data["lovelace"].resources
    urls = [item["url"] for item in resources.async_items()]
    assert len(urls) == 1
    assert urls[0].startswith(f"{CARD_URL}?v=")

    assert await hass.config_entries.async_unload(entry.entry_id)
