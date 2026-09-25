"""Config flow for the Alert Redux integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    EntitySelector,
    IconSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
)

from .const import (
    CONDITION_KINDS,
    CONF_ACKNOWLEDGEABLE,
    CONF_CONDITION,
    CONF_DELAY_OFF,
    CONF_DELAY_ON,
    CONF_DISPLAY_MESSAGE,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_KIND,
    CONF_MESSAGE,
    CONF_NO_DATA_GRACE,
    CONF_PRIORITY,
    CONF_STARTUP_DELAY,
    CONF_SUBJECT_ENTITY,
    CONF_TARGET_STATE,
    CONF_TEMPLATE,
    CONF_USER_DISMISSABLE,
    DOMAIN,
    SUBENTRY_ALERT,
    AlertKind,
    Priority,
)
from .model import Settings


class AlertReduxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the (single-instance) Alert Redux config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup; the defaults are set later, in the options."""
        if user_input is not None:
            return self.async_create_entry(title="Alert Redux", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow: the global defaults (spec §12.1)."""
        return AlertReduxOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types: alerts (spec §12.1)."""
        return {SUBENTRY_ALERT: AlertSubentryFlowHandler}


class AlertReduxOptionsFlow(OptionsFlow):
    """Edit the global defaults."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the defaults."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        settings = Settings.from_options(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NO_DATA_GRACE,
                        default=_duration_dict(settings.no_data_grace),
                    ): DurationSelector(),
                    vol.Required(
                        CONF_STARTUP_DELAY,
                        default=_duration_dict(settings.startup_delay),
                    ): DurationSelector(),
                }
            ),
        )


def _duration_dict(value: timedelta) -> dict[str, int]:
    """Return a timedelta in a duration selector's form."""
    minutes, seconds = divmod(int(value.total_seconds()), 60)
    hours, minutes = divmod(minutes, 60)
    return {"hours": hours, "minutes": minutes, "seconds": seconds}


def _suggested(defaults: dict[str, Any], key: str) -> dict[str, Any]:
    """Pre-fill an optional field without making its value impossible to clear."""
    if defaults.get(key) in (None, ""):
        return {}
    return {"suggested_value": defaults[key]}


def _alert_schema(kind: AlertKind, defaults: dict[str, Any]) -> vol.Schema:
    """Return the form for an alert of the given kind, pre-filled from defaults."""
    schema: dict[Any, Any] = {
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
        vol.Optional(CONF_ICON, description=_suggested(defaults, CONF_ICON)): (
            IconSelector()
        ),
    }
    if kind is AlertKind.STATE:
        schema[
            vol.Required(
                CONF_ENTITY_ID, default=defaults.get(CONF_ENTITY_ID, vol.UNDEFINED)
            )
        ] = EntitySelector()
        schema[
            vol.Required(
                CONF_TARGET_STATE,
                default=defaults.get(CONF_TARGET_STATE, vol.UNDEFINED),
            )
        ] = TextSelector()
    elif kind is AlertKind.TEMPLATE:
        schema[
            vol.Required(
                CONF_TEMPLATE, default=defaults.get(CONF_TEMPLATE, vol.UNDEFINED)
            )
        ] = TemplateSelector()
    if kind in CONDITION_KINDS:
        for key, selector in (
            (CONF_CONDITION, TemplateSelector()),
            (CONF_DELAY_ON, DurationSelector()),
            (CONF_DELAY_OFF, DurationSelector()),
        ):
            schema[vol.Optional(key, description=_suggested(defaults, key))] = selector
    schema[
        vol.Required(
            CONF_ACKNOWLEDGEABLE, default=defaults.get(CONF_ACKNOWLEDGEABLE, True)
        )
    ] = BooleanSelector()
    if kind is AlertKind.MANUAL:
        schema[
            vol.Required(
                CONF_USER_DISMISSABLE,
                default=defaults.get(CONF_USER_DISMISSABLE, False),
            )
        ] = BooleanSelector()
    schema[
        vol.Optional(
            CONF_SUBJECT_ENTITY, description=_suggested(defaults, CONF_SUBJECT_ENTITY)
        )
    ] = EntitySelector()
    for key in (CONF_MESSAGE, CONF_DISPLAY_MESSAGE):
        schema[vol.Optional(key, description=_suggested(defaults, key))] = (
            TemplateSelector()
        )
    if kind in CONDITION_KINDS:
        schema[
            vol.Optional(
                CONF_NO_DATA_GRACE, description=_suggested(defaults, CONF_NO_DATA_GRACE)
            )
        ] = DurationSelector()
    return vol.Schema(schema)


class AlertSubentryFlowHandler(ConfigSubentryFlow):
    """Create and edit alerts: a menu of kinds, then each kind's form."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the kind of alert to create."""
        return self.async_show_menu(
            step_id="user", menu_options=[kind.value for kind in AlertKind]
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a manual alert."""
        return await self._async_step_alert(AlertKind.MANUAL, user_input)

    async def async_step_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a state alert."""
        return await self._async_step_alert(AlertKind.STATE, user_input)

    async def async_step_template(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a template alert."""
        return await self._async_step_alert(AlertKind.TEMPLATE, user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an alert with its kind's form; the kind can't be changed."""
        kind = AlertKind(self._get_reconfigure_subentry().data[CONF_KIND])
        return await self._async_step_alert(kind, user_input, reconfigure=True)

    async def async_step_reconfigure_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a manual alert."""
        return await self._async_step_alert(AlertKind.MANUAL, user_input, True)

    async def async_step_reconfigure_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a state alert."""
        return await self._async_step_alert(AlertKind.STATE, user_input, True)

    async def async_step_reconfigure_template(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a template alert."""
        return await self._async_step_alert(AlertKind.TEMPLATE, user_input, True)

    async def _async_step_alert(
        self,
        kind: AlertKind,
        user_input: dict[str, Any] | None,
        reconfigure: bool = False,
    ) -> SubentryFlowResult:
        """Show a kind's form, and create or update the alert from it."""
        subentry = self._get_reconfigure_subentry() if reconfigure else None
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if self._name_in_use(name, subentry.subentry_id if subentry else None):
                errors[CONF_NAME] = "name_exists"
            if not errors:
                data = {CONF_KIND: kind, **_alert_data(kind, user_input)}
                if subentry is None:
                    return self.async_create_entry(title=name, data=data)
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=name, data=data
                )

        if user_input is not None:
            defaults = user_input
        elif subentry is not None:
            defaults = {CONF_NAME: subentry.title, **subentry.data}
        else:
            defaults = {}
        return self.async_show_form(
            step_id=f"reconfigure_{kind}" if reconfigure else kind.value,
            data_schema=_alert_schema(kind, defaults),
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


def _alert_data(kind: AlertKind, user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the subentry data from a submitted form (the name is the title)."""
    data = {
        CONF_PRIORITY: user_input[CONF_PRIORITY],
        CONF_ACKNOWLEDGEABLE: user_input[CONF_ACKNOWLEDGEABLE],
    }
    if kind is AlertKind.MANUAL:
        data[CONF_USER_DISMISSABLE] = user_input[CONF_USER_DISMISSABLE]
    elif kind is AlertKind.STATE:
        data[CONF_ENTITY_ID] = user_input[CONF_ENTITY_ID]
        data[CONF_TARGET_STATE] = user_input[CONF_TARGET_STATE].strip()
    else:
        data[CONF_TEMPLATE] = user_input[CONF_TEMPLATE]
    optional = [CONF_ICON, CONF_SUBJECT_ENTITY, CONF_MESSAGE, CONF_DISPLAY_MESSAGE]
    if kind in CONDITION_KINDS:
        optional += [CONF_CONDITION, CONF_DELAY_ON, CONF_DELAY_OFF, CONF_NO_DATA_GRACE]
    for key in optional:
        if (value := user_input.get(key)) not in (None, ""):
            data[key] = value
    return data
