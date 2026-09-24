"""Config flow for the Alert Redux integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    IconSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ACKNOWLEDGEABLE,
    CONF_ICON,
    CONF_KIND,
    CONF_PRIORITY,
    CONF_USER_DISMISSABLE,
    DOMAIN,
    SUBENTRY_ALERT,
    AlertKind,
    Priority,
)


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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types: alerts (spec §12.1)."""
        return {SUBENTRY_ALERT: AlertSubentryFlowHandler}


def _alert_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the form for a manual alert, pre-filled from defaults."""
    icon = (
        {"suggested_value": defaults[CONF_ICON]} if defaults.get(CONF_ICON) else {}
    )
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, vol.UNDEFINED)): (
                TextSelector()
            ),
            vol.Required(
                CONF_PRIORITY, default=defaults.get(CONF_PRIORITY, Priority.WARNING)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[priority.value for priority in Priority],
                    translation_key=CONF_PRIORITY,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_ICON, description=icon): IconSelector(),
            vol.Required(
                CONF_ACKNOWLEDGEABLE,
                default=defaults.get(CONF_ACKNOWLEDGEABLE, True),
            ): BooleanSelector(),
            vol.Required(
                CONF_USER_DISMISSABLE,
                default=defaults.get(CONF_USER_DISMISSABLE, False),
            ): BooleanSelector(),
        }
    )


class AlertSubentryFlowHandler(ConfigSubentryFlow):
    """Create and edit alerts.

    Only manual alerts exist so far; later phases put a choice of kind in front of
    the kind-specific forms.
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a manual alert."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if self._name_in_use(name):
                errors[CONF_NAME] = "name_exists"
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_KIND: AlertKind.MANUAL, **_alert_data(user_input)},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_alert_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an alert."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if self._name_in_use(name, subentry.subentry_id):
                errors[CONF_NAME] = "name_exists"
            else:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=name,
                    data={CONF_KIND: subentry.data[CONF_KIND], **_alert_data(user_input)},
                )

        defaults = user_input or {CONF_NAME: subentry.title, **subentry.data}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_alert_schema(defaults),
            errors=errors,
        )

    def _name_in_use(self, name: str, exclude: str | None = None) -> bool:
        """Return whether another alert already has this name."""
        folded = name.casefold()
        return any(
            subentry.title.casefold() == folded
            for subentry_id, subentry in self._get_entry().subentries.items()
            if subentry.subentry_type == SUBENTRY_ALERT and subentry_id != exclude
        )


def _alert_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the subentry data from a submitted form (the name is the title)."""
    data = {
        CONF_PRIORITY: user_input[CONF_PRIORITY],
        CONF_ACKNOWLEDGEABLE: user_input[CONF_ACKNOWLEDGEABLE],
        CONF_USER_DISMISSABLE: user_input[CONF_USER_DISMISSABLE],
    }
    if icon := user_input.get(CONF_ICON):
        data[CONF_ICON] = icon
    return data
