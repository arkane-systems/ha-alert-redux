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
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    EntitySelector,
    EntitySelectorConfig,
    IconSelector,
    ObjectSelector,
    ObjectSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
)

from .const import (
    CONDITION_KINDS,
    CONF_ACKNOWLEDGEABLE,
    CONF_ACTION,
    CONF_ACTIONS,
    CONF_CONDITION,
    CONF_DATA,
    CONF_DEFAULT_GROUPS,
    CONF_DEFAULT_REMINDER_SCHEDULE,
    CONF_DELAY_OFF,
    CONF_DELAY_ON,
    CONF_DISPLAY_MESSAGE,
    CONF_DONE_MESSAGE,
    CONF_ENTITIES,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_KIND,
    CONF_LOUD,
    CONF_MESSAGE,
    CONF_NO_DATA_GRACE,
    CONF_NOTIFIER_GROUPS,
    CONF_PERSISTENT,
    CONF_PRIORITY,
    CONF_REMINDER_MESSAGE,
    CONF_REMINDER_SCHEDULE,
    CONF_STARTUP_DELAY,
    CONF_SUBJECT_ENTITY,
    CONF_TARGET,
    CONF_TARGET_STATE,
    CONF_TEMPLATE,
    CONF_USE_DEFAULT_GROUPS,
    CONF_USE_DEFAULT_REMINDERS,
    CONF_USER_DISMISSABLE,
    DOMAIN,
    SECTION_NOTIFICATIONS,
    SUBENTRY_ALERT,
    SUBENTRY_NOTIFIER_GROUP,
    AlertKind,
    Priority,
)
from .model import Settings, format_schedule, parse_schedule

# notify actions that aren't legacy notifiers: offered through the other member kinds.
_NOT_LEGACY_NOTIFIERS = frozenset({"send_message", "persistent_notification"})


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
        """Return the subentry types: alerts and notifier groups (spec §12.1)."""
        return {
            SUBENTRY_ALERT: AlertSubentryFlowHandler,
            SUBENTRY_NOTIFIER_GROUP: NotifierGroupSubentryFlowHandler,
        }


class AlertReduxOptionsFlow(OptionsFlow):
    """Edit the global defaults."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the defaults."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                schedule = parse_schedule(
                    user_input.get(CONF_DEFAULT_REMINDER_SCHEDULE, "")
                )
            except ValueError:
                errors["base"] = "invalid_schedule"
            else:
                return self.async_create_entry(
                    data={
                        CONF_NO_DATA_GRACE: user_input[CONF_NO_DATA_GRACE],
                        CONF_STARTUP_DELAY: user_input[CONF_STARTUP_DELAY],
                        CONF_DEFAULT_GROUPS: user_input.get(CONF_DEFAULT_GROUPS, []),
                        CONF_DEFAULT_REMINDER_SCHEDULE: list(schedule),
                    }
                )

        settings = Settings.from_options(self.config_entry.options)
        defaults = user_input or {
            CONF_NO_DATA_GRACE: _duration_dict(settings.no_data_grace),
            CONF_STARTUP_DELAY: _duration_dict(settings.startup_delay),
            CONF_DEFAULT_GROUPS: list(settings.default_groups),
            CONF_DEFAULT_REMINDER_SCHEDULE: format_schedule(
                settings.reminder_schedule
            ),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NO_DATA_GRACE, default=defaults[CONF_NO_DATA_GRACE]
                    ): DurationSelector(),
                    vol.Required(
                        CONF_STARTUP_DELAY, default=defaults[CONF_STARTUP_DELAY]
                    ): DurationSelector(),
                    vol.Optional(
                        CONF_DEFAULT_GROUPS,
                        description=_suggested(defaults, CONF_DEFAULT_GROUPS),
                    ): _groups_selector(self.config_entry),
                    vol.Optional(
                        CONF_DEFAULT_REMINDER_SCHEDULE,
                        description=_suggested(
                            defaults, CONF_DEFAULT_REMINDER_SCHEDULE
                        ),
                    ): TextSelector(),
                }
            ),
            errors=errors,
        )


def _duration_dict(value: timedelta) -> dict[str, int]:
    """Return a timedelta in a duration selector's form."""
    minutes, seconds = divmod(int(value.total_seconds()), 60)
    hours, minutes = divmod(minutes, 60)
    return {"hours": hours, "minutes": minutes, "seconds": seconds}


def _suggested(defaults: dict[str, Any], key: str) -> dict[str, Any]:
    """Pre-fill an optional field without making its value impossible to clear."""
    if defaults.get(key) in (None, "", []):
        return {}
    return {"suggested_value": defaults[key]}


def _groups_selector(entry: ConfigEntry) -> SelectSelector:
    """Return a multi-select of the notifier groups."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=subentry_id, label=subentry.title)
                for subentry_id, subentry in entry.subentries.items()
                if subentry.subentry_type == SUBENTRY_NOTIFIER_GROUP
            ],
            multiple=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return a submitted form with its section's fields brought to the top level."""
    flat = dict(user_input)
    notifications = flat.pop(SECTION_NOTIFICATIONS, {})
    return flat | notifications


def _notifications_section(entry: ConfigEntry, defaults: dict[str, Any]) -> section:
    """Return the alert form's notifications section (spec §9.4–§9.6).

    Each "use the default" checkbox stands for the setting being absent from the
    alert's data; with it off, the field is the alert's own, and may be empty.
    """
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_USE_DEFAULT_GROUPS,
            default=defaults.get(CONF_USE_DEFAULT_GROUPS, True),
        ): BooleanSelector(),
        vol.Optional(
            CONF_NOTIFIER_GROUPS, description=_suggested(defaults, CONF_NOTIFIER_GROUPS)
        ): _groups_selector(entry),
        vol.Required(
            CONF_USE_DEFAULT_REMINDERS,
            default=defaults.get(CONF_USE_DEFAULT_REMINDERS, True),
        ): BooleanSelector(),
        vol.Optional(
            CONF_REMINDER_SCHEDULE,
            description=_suggested(defaults, CONF_REMINDER_SCHEDULE),
        ): TextSelector(),
    }
    for key in (
        CONF_MESSAGE,
        CONF_DISPLAY_MESSAGE,
        CONF_REMINDER_MESSAGE,
        CONF_DONE_MESSAGE,
    ):
        schema[vol.Optional(key, description=_suggested(defaults, key))] = (
            TemplateSelector()
        )
    return section(vol.Schema(schema), {"collapsed": True})


def _alert_form_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Return an alert's stored data in its form's shape, to pre-fill an edit."""
    defaults = dict(data)
    defaults[CONF_USE_DEFAULT_GROUPS] = CONF_NOTIFIER_GROUPS not in data
    defaults[CONF_USE_DEFAULT_REMINDERS] = CONF_REMINDER_SCHEDULE not in data
    if CONF_REMINDER_SCHEDULE in data:
        defaults[CONF_REMINDER_SCHEDULE] = format_schedule(data[CONF_REMINDER_SCHEDULE])
    return defaults


def _alert_schema(
    kind: AlertKind, defaults: dict[str, Any], entry: ConfigEntry
) -> vol.Schema:
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
    if kind in CONDITION_KINDS:
        schema[
            vol.Optional(
                CONF_NO_DATA_GRACE, description=_suggested(defaults, CONF_NO_DATA_GRACE)
            )
        ] = DurationSelector()
    schema[vol.Optional(SECTION_NOTIFICATIONS, default={})] = _notifications_section(
        entry, defaults
    )
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
            user_input = _flatten(user_input)
            name = user_input[CONF_NAME].strip()
            if _name_in_use(
                self._get_entry(),
                SUBENTRY_ALERT,
                name,
                subentry.subentry_id if subentry else None,
            ):
                errors[CONF_NAME] = "name_exists"
            try:
                data = {CONF_KIND: kind, **_alert_data(kind, user_input)}
            except ValueError:
                errors["base"] = "invalid_schedule"
            if not errors:
                if subentry is None:
                    return self.async_create_entry(title=name, data=data)
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=name, data=data
                )

        if user_input is not None:
            defaults = user_input
        elif subentry is not None:
            defaults = {
                CONF_NAME: subentry.title,
                **_alert_form_defaults(subentry.data),
            }
        else:
            defaults = {}
        return self.async_show_form(
            step_id=f"reconfigure_{kind}" if reconfigure else kind.value,
            data_schema=_alert_schema(kind, defaults, self._get_entry()),
            errors=errors,
        )


def _name_in_use(
    entry: ConfigEntry, subentry_type: str, name: str, exclude: str | None = None
) -> bool:
    """Return whether another subentry of the type already has this name."""
    folded = name.casefold()
    return any(
        subentry.title.casefold() == folded
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == subentry_type and subentry_id != exclude
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
    optional = [
        CONF_ICON,
        CONF_SUBJECT_ENTITY,
        CONF_MESSAGE,
        CONF_DISPLAY_MESSAGE,
        CONF_REMINDER_MESSAGE,
        CONF_DONE_MESSAGE,
    ]
    if kind in CONDITION_KINDS:
        optional += [CONF_CONDITION, CONF_DELAY_ON, CONF_DELAY_OFF, CONF_NO_DATA_GRACE]
    for key in optional:
        if (value := user_input.get(key)) not in (None, ""):
            data[key] = value
    if not user_input.get(CONF_USE_DEFAULT_GROUPS, True):
        data[CONF_NOTIFIER_GROUPS] = list(user_input.get(CONF_NOTIFIER_GROUPS, []))
    if not user_input.get(CONF_USE_DEFAULT_REMINDERS, True):
        # Raises ValueError for a schedule that won't parse.
        data[CONF_REMINDER_SCHEDULE] = list(
            parse_schedule(user_input.get(CONF_REMINDER_SCHEDULE, ""))
        )
    return data


def _legacy_notifiers(hass: HomeAssistant) -> list[str]:
    """Return the legacy notify actions currently registered."""
    return sorted(
        f"notify.{service}"
        for service in hass.services.async_services_for_domain("notify")
        if service not in _NOT_LEGACY_NOTIFIERS
    )


def _group_schema(hass: HomeAssistant, defaults: dict[str, Any]) -> vol.Schema:
    """Return the notifier group form, pre-filled from defaults (spec §9.3)."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, vol.UNDEFINED)): (
                TextSelector()
            ),
            vol.Required(CONF_LOUD, default=defaults.get(CONF_LOUD, False)): (
                BooleanSelector()
            ),
            vol.Optional(
                CONF_ENTITIES, description=_suggested(defaults, CONF_ENTITIES)
            ): EntitySelector(EntitySelectorConfig(domain="notify", multiple=True)),
            vol.Optional(
                CONF_ACTIONS, description=_suggested(defaults, CONF_ACTIONS)
            ): ObjectSelector(
                ObjectSelectorConfig(
                    multiple=True,
                    label_field=CONF_ACTION,
                    fields={
                        CONF_ACTION: {
                            "label": "Action",
                            "required": True,
                            "selector": SelectSelector(
                                SelectSelectorConfig(
                                    options=_legacy_notifiers(hass),
                                    custom_value=True,
                                    mode=SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        },
                        CONF_DATA: {"label": "Data", "selector": ObjectSelector()},
                        CONF_TARGET: {"label": "Target", "selector": TextSelector()},
                    },
                )
            ),
            vol.Required(
                CONF_PERSISTENT, default=defaults.get(CONF_PERSISTENT, False)
            ): BooleanSelector(),
        }
    )


def _group_data(user_input: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Return a notifier group's data from its form, or an error key."""
    actions: list[dict[str, Any]] = []
    for item in user_input.get(CONF_ACTIONS) or []:
        action = str(item.get(CONF_ACTION) or "").strip()
        if not action:
            return {}, "action_missing"
        if not action.startswith("notify."):
            action = f"notify.{action}"
        entry: dict[str, Any] = {CONF_ACTION: action}
        if data := item.get(CONF_DATA):
            if not isinstance(data, dict):
                return {}, "invalid_data"
            entry[CONF_DATA] = data
        if target := str(item.get(CONF_TARGET) or "").strip():
            entry[CONF_TARGET] = target
        actions.append(entry)
    data = {
        CONF_LOUD: user_input[CONF_LOUD],
        CONF_ENTITIES: list(user_input.get(CONF_ENTITIES) or []),
        CONF_ACTIONS: actions,
        CONF_PERSISTENT: user_input[CONF_PERSISTENT],
    }
    if not (data[CONF_ENTITIES] or actions or data[CONF_PERSISTENT]):
        return data, "no_members"
    return data, None


class NotifierGroupSubentryFlowHandler(ConfigSubentryFlow):
    """Create and edit notifier groups (spec §9.3)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a notifier group."""
        return await self._async_step_group(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a notifier group."""
        return await self._async_step_group(user_input, reconfigure=True)

    async def _async_step_group(
        self, user_input: dict[str, Any] | None, reconfigure: bool = False
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry() if reconfigure else None
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if _name_in_use(
                self._get_entry(),
                SUBENTRY_NOTIFIER_GROUP,
                name,
                subentry.subentry_id if subentry else None,
            ):
                errors[CONF_NAME] = "name_exists"
            data, error = _group_data(user_input)
            if error:
                errors["base"] = error
            if not errors:
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
            step_id="reconfigure" if reconfigure else "user",
            data_schema=_group_schema(self.hass, defaults),
            errors=errors,
        )
