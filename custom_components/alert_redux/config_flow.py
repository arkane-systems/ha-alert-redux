"""Config flow for the Alert Redux integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class AlertReduxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the (single-instance) Alert Redux config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup; there is nothing to configure yet."""
        if user_input is not None:
            return self.async_create_entry(title="Alert Redux", data={})

        return self.async_show_form(step_id="user")
