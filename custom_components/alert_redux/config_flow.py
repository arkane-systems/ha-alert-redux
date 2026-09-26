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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    EntitySelector,
    EntitySelectorConfig,
    IconSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    ObjectSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TriggerSelector,
)
from homeassistant.util import slugify

from .const import (
    CONDITION_KINDS,
    CONF_ACKNOWLEDGEABLE,
    CONF_ACTION,
    CONF_ACTIONS,
    CONF_ALERT,
    CONF_ALERT_STATES,
    CONF_ATTRIBUTE,
    CONF_CONDITION,
    CONF_DATA,
    CONF_DEFAULT_GROUPS,
    CONF_DEFAULT_REMINDER_SCHEDULE,
    CONF_DELAY_OFF,
    CONF_DELAY_ON,
    CONF_DISPLAY_MESSAGE,
    CONF_DONE_MESSAGE,
    CONF_DONE_WINDOW,
    CONF_DURATION,
    CONF_ENTITIES,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_EVENT_DURATIONS,
    CONF_EVENT_TYPE,
    CONF_FALLBACK_GROUP,
    CONF_HYSTERESIS,
    CONF_ICON,
    CONF_KIND,
    CONF_LOUD,
    CONF_MAXIMUM,
    CONF_MESSAGE,
    CONF_MINIMUM,
    CONF_NOTIFIER_GROUPS,
    CONF_NO_DATA_GRACE,
    CONF_OFF_TEMPLATE,
    CONF_OFF_TRIGGERS,
    CONF_ON_TEMPLATE,
    CONF_ON_TRIGGERS,
    CONF_PERSISTENT,
    CONF_PRIORITY,
    CONF_PROPAGATION,
    CONF_REMINDER_MESSAGE,
    CONF_REMINDER_SCHEDULE,
    CONF_RETRY_TIMEOUT,
    CONF_SNOOZE_DURATION,
    CONF_SNOOZE_REMINDER_WINDOW,
    CONF_STARTUP_DELAY,
    CONF_SUBJECT_ENTITY,
    CONF_SUPERSEDES,
    CONF_SUPERSESSION_DEBOUNCE,
    CONF_TARGET,
    CONF_TARGET_STATE,
    CONF_TEMPLATE,
    CONF_TRIGGERS,
    CONF_USER_DISMISSABLE,
    CONF_USE_DEFAULT_GROUPS,
    CONF_USE_DEFAULT_REMINDERS,
    CONF_VALUE_TEMPLATE,
    DOMAIN,
    EVENT_KINDS,
    SECTION_NOTIFICATIONS,
    SECTION_SUPERSESSION,
    SUBENTRY_ALERT,
    SUBENTRY_NOTIFIER_GROUP,
    AlertKind,
    AlertState,
    Priority,
    Propagation,
)
from .model import Settings, format_schedule, parse_schedule, to_timedelta
from .supersession import find_cycle, propagation_of, relationship_targets
from .triggers import async_validate_triggers, is_storable

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
        settings = Settings.from_options(self.config_entry.options)
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
                        CONF_FALLBACK_GROUP: user_input.get(CONF_FALLBACK_GROUP),
                        CONF_RETRY_TIMEOUT: user_input[CONF_RETRY_TIMEOUT],
                        CONF_SNOOZE_REMINDER_WINDOW: user_input[
                            CONF_SNOOZE_REMINDER_WINDOW
                        ],
                        CONF_EVENT_DURATIONS: user_input.get(CONF_EVENT_DURATIONS)
                        or _event_durations(settings),
                        **(
                            user_input.get(SECTION_SUPERSESSION)
                            or _supersession_options(settings)
                        ),
                    }
                )

        defaults = user_input or {
            CONF_NO_DATA_GRACE: _duration_dict(settings.no_data_grace),
            CONF_STARTUP_DELAY: _duration_dict(settings.startup_delay),
            CONF_DEFAULT_GROUPS: list(settings.default_groups),
            CONF_DEFAULT_REMINDER_SCHEDULE: format_schedule(settings.reminder_schedule),
            CONF_FALLBACK_GROUP: settings.fallback_group,
            CONF_RETRY_TIMEOUT: _duration_dict(settings.retry_timeout),
            CONF_SNOOZE_REMINDER_WINDOW: _duration_dict(
                settings.snooze_reminder_window
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
                    vol.Optional(
                        CONF_FALLBACK_GROUP,
                        description=_suggested(defaults, CONF_FALLBACK_GROUP),
                    ): _groups_selector(self.config_entry, multiple=False),
                    vol.Required(
                        CONF_RETRY_TIMEOUT, default=defaults[CONF_RETRY_TIMEOUT]
                    ): DurationSelector(),
                    vol.Required(
                        CONF_SNOOZE_REMINDER_WINDOW,
                        default=defaults[CONF_SNOOZE_REMINDER_WINDOW],
                    ): DurationSelector(),
                    # No default: the frontend then builds the section's value from
                    # its fields' defaults (see the alert form's section).
                    vol.Optional(CONF_EVENT_DURATIONS): section(
                        vol.Schema(
                            {
                                vol.Required(str(priority), default=duration): (
                                    DurationSelector()
                                )
                                for priority, duration in (
                                    defaults.get(CONF_EVENT_DURATIONS)
                                    or _event_durations(settings)
                                ).items()
                            }
                        ),
                        {"collapsed": True},
                    ),
                    vol.Optional(SECTION_SUPERSESSION): section(
                        vol.Schema(
                            {
                                vol.Required(key, default=value): NumberSelector(
                                    NumberSelectorConfig(
                                        min=0,
                                        max=300,
                                        step=0.1,
                                        unit_of_measurement="s",
                                        mode=NumberSelectorMode.BOX,
                                    )
                                )
                                for key, value in (
                                    defaults.get(SECTION_SUPERSESSION)
                                    or _supersession_options(settings)
                                ).items()
                            }
                        ),
                        {"collapsed": True},
                    ),
                }
            ),
            errors=errors,
        )


def _supersession_options(settings: Settings) -> dict[str, float]:
    """Return the supersession timings in the options' form: seconds."""
    return {
        CONF_SUPERSESSION_DEBOUNCE: settings.supersession_debounce.total_seconds(),
        CONF_DONE_WINDOW: settings.done_window.total_seconds(),
    }


def _event_durations(settings: Settings) -> dict[str, dict[str, int]]:
    """Return the per-priority event durations in the options' form."""
    return {
        priority.value: _duration_dict(duration)
        for priority, duration in settings.event_durations.items()
    }


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


def _groups_selector(entry: ConfigEntry, multiple: bool = True) -> SelectSelector:
    """Return a selector of the notifier groups."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=subentry_id, label=subentry.title)
                for subentry_id, subentry in entry.subentries.items()
                if subentry.subentry_type == SUBENTRY_NOTIFIER_GROUP
            ],
            multiple=multiple,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return a submitted form with its sections' fields brought to the top level."""
    flat = dict(user_input)
    notifications = flat.pop(SECTION_NOTIFICATIONS, {})
    supersession = flat.pop(SECTION_SUPERSESSION, {})
    return flat | notifications | supersession


def _alerts_selector(exclude: str | None) -> EntitySelector:
    """Return a selector of the other alerts."""
    return EntitySelector(
        EntitySelectorConfig(
            domain=DOMAIN, exclude_entities=[exclude] if exclude else []
        )
    )


def _supersession_section(defaults: dict[str, Any], own: str | None) -> section:
    """Return the alert form's supersession section (spec §8)."""
    return section(
        vol.Schema(
            {
                vol.Optional(
                    CONF_SUPERSEDES, description=_suggested(defaults, CONF_SUPERSEDES)
                ): ObjectSelector(
                    ObjectSelectorConfig(
                        multiple=True,
                        label_field=CONF_ALERT,
                        fields={
                            CONF_ALERT: {
                                "label": "Alert",
                                "required": True,
                                "selector": _alerts_selector(own),
                            },
                            CONF_PROPAGATION: {
                                "label": "When it's acknowledged",
                                "selector": SelectSelector(
                                    SelectSelectorConfig(
                                        options=[
                                            SelectOptionDict(
                                                value=Propagation.NONE,
                                                label="Do nothing to this alert",
                                            ),
                                            SelectOptionDict(
                                                value=Propagation.ACKNOWLEDGE,
                                                label="Acknowledge this alert",
                                            ),
                                            SelectOptionDict(
                                                value=Propagation.SNOOZE,
                                                label="Snooze this alert",
                                            ),
                                        ],
                                        mode=SelectSelectorMode.DROPDOWN,
                                    )
                                ),
                            },
                            CONF_SNOOZE_DURATION: {
                                "label": "Snooze for",
                                "selector": DurationSelector(),
                            },
                        },
                    )
                ),
            }
        ),
        {"collapsed": True},
    )


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
    kind: AlertKind,
    defaults: dict[str, Any],
    entry: ConfigEntry,
    own: str | None = None,
) -> vol.Schema:
    """Return the form for an alert of the given kind, pre-filled from defaults.

    own is the alert's own entity ID, when editing, so that it can't pick itself.
    """
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
    elif kind is AlertKind.ALERT_STATE:
        schema[
            vol.Required(CONF_ALERT, default=defaults.get(CONF_ALERT, vol.UNDEFINED))
        ] = _alerts_selector(own)
        schema[
            vol.Required(
                CONF_ALERT_STATES,
                default=defaults.get(CONF_ALERT_STATES, [AlertState.ACTIVE.value]),
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                options=[state.value for state in AlertState],
                multiple=True,
                translation_key=CONF_ALERT_STATES,
                mode=SelectSelectorMode.LIST,
            )
        )
    elif kind is AlertKind.THRESHOLD:
        for key, selector in (
            (CONF_ENTITY_ID, EntitySelector()),
            (CONF_ATTRIBUTE, TextSelector()),
            (CONF_VALUE_TEMPLATE, TemplateSelector()),
            (CONF_MINIMUM, TemplateSelector()),
            (CONF_MAXIMUM, TemplateSelector()),
        ):
            schema[vol.Optional(key, description=_suggested(defaults, key))] = selector
        schema[
            vol.Required(CONF_HYSTERESIS, default=defaults.get(CONF_HYSTERESIS, 0))
        ] = NumberSelector(
            NumberSelectorConfig(min=0, step="any", mode=NumberSelectorMode.BOX)
        )
    elif kind is AlertKind.ON_OFF:
        for key, selector in (
            (CONF_ON_TEMPLATE, TemplateSelector()),
            (CONF_ON_TRIGGERS, TriggerSelector()),
            (CONF_OFF_TEMPLATE, TemplateSelector()),
            (CONF_OFF_TRIGGERS, TriggerSelector()),
        ):
            schema[vol.Optional(key, description=_suggested(defaults, key))] = selector
    elif kind is AlertKind.TRIGGER:
        schema[
            vol.Required(
                CONF_TRIGGERS, default=defaults.get(CONF_TRIGGERS, vol.UNDEFINED)
            )
        ] = TriggerSelector()
    elif kind is AlertKind.EVENT:
        schema[
            vol.Required(
                CONF_EVENT_TYPE, default=defaults.get(CONF_EVENT_TYPE, vol.UNDEFINED)
            )
        ] = TextSelector()
        schema[
            vol.Optional(
                CONF_EVENT_DATA, description=_suggested(defaults, CONF_EVENT_DATA)
            )
        ] = ObjectSelector()
    if kind in EVENT_KINDS:
        for key, selector in (
            (CONF_CONDITION, TemplateSelector()),
            (CONF_DURATION, DurationSelector()),
        ):
            schema[vol.Optional(key, description=_suggested(defaults, key))] = selector
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
    # Required, and without a default: the frontend then builds the section's
    # value from its fields' defaults and suggested values. With a default of {},
    # it used that instead, so the section showed empty and saving wiped it.
    schema[vol.Required(SECTION_NOTIFICATIONS)] = _notifications_section(
        entry, defaults
    )
    schema[vol.Required(SECTION_SUPERSESSION)] = _supersession_section(defaults, own)
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

    async def async_step_on_off(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create an on/off alert."""
        return await self._async_step_alert(AlertKind.ON_OFF, user_input)

    async def async_step_threshold(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a threshold alert."""
        return await self._async_step_alert(AlertKind.THRESHOLD, user_input)

    async def async_step_trigger(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a trigger alert."""
        return await self._async_step_alert(AlertKind.TRIGGER, user_input)

    async def async_step_event(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a bus event alert."""
        return await self._async_step_alert(AlertKind.EVENT, user_input)

    async def async_step_alert_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create an alert state alert."""
        return await self._async_step_alert(AlertKind.ALERT_STATE, user_input)

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

    async def async_step_reconfigure_on_off(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an on/off alert."""
        return await self._async_step_alert(AlertKind.ON_OFF, user_input, True)

    async def async_step_reconfigure_threshold(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a threshold alert."""
        return await self._async_step_alert(AlertKind.THRESHOLD, user_input, True)

    async def async_step_reconfigure_trigger(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a trigger alert."""
        return await self._async_step_alert(AlertKind.TRIGGER, user_input, True)

    async def async_step_reconfigure_event(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a bus event alert."""
        return await self._async_step_alert(AlertKind.EVENT, user_input, True)

    async def async_step_reconfigure_alert_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an alert state alert."""
        return await self._async_step_alert(AlertKind.ALERT_STATE, user_input, True)

    async def _async_step_alert(
        self,
        kind: AlertKind,
        user_input: dict[str, Any] | None,
        reconfigure: bool = False,
    ) -> SubentryFlowResult:
        """Show a kind's form, and create or update the alert from it."""
        subentry = self._get_reconfigure_subentry() if reconfigure else None
        own = (
            _alert_entity_id(self.hass, subentry.subentry_id) if subentry else None
        )
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
            else:
                if error := await _async_check_alert(
                    self.hass, kind, data
                ) or _check_references(
                    self.hass,
                    self._get_entry(),
                    own or f"{DOMAIN}.{slugify(name)}",
                    subentry.subentry_id if subentry else None,
                    data,
                ):
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
            defaults = {
                CONF_NAME: subentry.title,
                **_alert_form_defaults(subentry.data),
            }
        else:
            defaults = {}
        return self.async_show_form(
            step_id=f"reconfigure_{kind}" if reconfigure else kind.value,
            data_schema=_alert_schema(kind, defaults, self._get_entry(), own),
            errors=errors,
            description_placeholders=(
                {
                    "referrers": _referrers(
                        self.hass, self._get_entry(), subentry.subentry_id
                    )
                }
                if subentry
                else None
            ),
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
    elif kind is AlertKind.TEMPLATE:
        data[CONF_TEMPLATE] = user_input[CONF_TEMPLATE]
    elif kind is AlertKind.ALERT_STATE:
        data[CONF_ALERT] = user_input[CONF_ALERT]
        data[CONF_ALERT_STATES] = list(user_input.get(CONF_ALERT_STATES) or [])
    elif kind is AlertKind.THRESHOLD:
        data[CONF_HYSTERESIS] = user_input.get(CONF_HYSTERESIS) or 0
    elif kind is AlertKind.TRIGGER:
        data[CONF_TRIGGERS] = user_input[CONF_TRIGGERS]
    elif kind is AlertKind.EVENT:
        data[CONF_EVENT_TYPE] = user_input[CONF_EVENT_TYPE].strip()
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
        if kind is AlertKind.THRESHOLD:
            optional += [
                CONF_ENTITY_ID,
                CONF_ATTRIBUTE,
                CONF_VALUE_TEMPLATE,
                CONF_MINIMUM,
                CONF_MAXIMUM,
            ]
        elif kind is AlertKind.ON_OFF:
            optional += [
                CONF_ON_TEMPLATE,
                CONF_ON_TRIGGERS,
                CONF_OFF_TEMPLATE,
                CONF_OFF_TRIGGERS,
            ]
    elif kind in EVENT_KINDS:
        optional += [CONF_CONDITION, CONF_DURATION]
        if kind is AlertKind.EVENT:
            optional.append(CONF_EVENT_DATA)
    for key in optional:
        value = user_input.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, "", {}, []):
            data[key] = value
    if supersedes := [
        _relationship(rel)
        for rel in user_input.get(CONF_SUPERSEDES) or []
        if isinstance(rel, dict) and rel.get(CONF_ALERT)
    ]:
        data[CONF_SUPERSEDES] = supersedes
    if not user_input.get(CONF_USE_DEFAULT_GROUPS, True):
        data[CONF_NOTIFIER_GROUPS] = list(user_input.get(CONF_NOTIFIER_GROUPS, []))
    if not user_input.get(CONF_USE_DEFAULT_REMINDERS, True):
        # Raises ValueError for a schedule that won't parse.
        data[CONF_REMINDER_SCHEDULE] = list(
            parse_schedule(user_input.get(CONF_REMINDER_SCHEDULE, ""))
        )
    return data


async def _async_check_alert(
    hass: HomeAssistant, kind: AlertKind, data: dict[str, Any]
) -> str | None:
    """Return an error key for a kind's own fields, if they don't make sense."""
    if kind is AlertKind.EVENT:
        if not data[CONF_EVENT_TYPE]:
            return "event_type_missing"
        if not isinstance(data.get(CONF_EVENT_DATA, {}), dict):
            return "invalid_event_data"
    elif kind is AlertKind.THRESHOLD:
        return _check_threshold(data)
    elif kind is AlertKind.ON_OFF:
        if error := _check_on_off(data):
            return error
        for key in (CONF_ON_TRIGGERS, CONF_OFF_TRIGGERS):
            if key in data and not await _async_triggers_valid(hass, data[key]):
                return "invalid_trigger"
    elif kind is AlertKind.TRIGGER:
        if not await _async_triggers_valid(hass, data[CONF_TRIGGERS]):
            return "invalid_trigger"
    return None


def _relationship(rel: dict[str, Any]) -> dict[str, Any]:
    """Return a submitted relationship as stored: no propagation means none.

    A snooze duration is kept only for the snooze propagation.
    """
    relationship: dict[str, Any] = {CONF_ALERT: rel[CONF_ALERT]}
    propagation = rel.get(CONF_PROPAGATION) or Propagation.NONE
    if propagation != Propagation.NONE:
        relationship[CONF_PROPAGATION] = propagation
    if propagation == Propagation.SNOOZE and rel.get(CONF_SNOOZE_DURATION):
        relationship[CONF_SNOOZE_DURATION] = rel[CONF_SNOOZE_DURATION]
    return relationship


def _referrers(hass: HomeAssistant, entry: ConfigEntry, subentry_id: str) -> str:
    """Return the names of the alerts that refer to an alert, for its edit form.

    Deleting an alert that others refer to is allowed, but leaves their
    references dangling (spec §12.4), so the edit form lists them.
    """
    own = _alert_entity_id(hass, subentry_id)
    names = sorted(
        other.title
        for other_id, other in entry.subentries.items()
        if other.subentry_type == SUBENTRY_ALERT
        and other_id != subentry_id
        and own is not None
        and (
            other.data.get(CONF_ALERT) == own
            or own in relationship_targets(other.data.get(CONF_SUPERSEDES, []))
        )
    )
    return ", ".join(names) if names else "none"


def _alert_entity_id(hass: HomeAssistant, subentry_id: str) -> str | None:
    """Return the entity ID of an alert subentry's entity, if it has one."""
    return er.async_get(hass).async_get_entity_id(DOMAIN, DOMAIN, subentry_id)


def _check_references(
    hass: HomeAssistant,
    entry: ConfigEntry,
    own: str,
    subentry_id: str | None,
    data: dict[str, Any],
) -> str | None:
    """Return an error key for references to other alerts that don't make sense.

    own is the alert's entity ID, or the one it will get if it's new.
    """
    if data.get(CONF_ALERT) == own:
        return "alert_state_self"
    if CONF_ALERT_STATES in data and not data[CONF_ALERT_STATES]:
        return "alert_states_missing"
    relationships = data.get(CONF_SUPERSEDES, [])
    targets = relationship_targets(relationships)
    if own in targets:
        return "supersedes_self"
    if len(set(targets)) != len(targets):
        return "supersedes_duplicate"
    for rel in relationships:
        propagation = propagation_of(rel)
        # Propagating to an alert that can't be acknowledged is an error (§8.3).
        if propagation is not Propagation.NONE and not data[CONF_ACKNOWLEDGEABLE]:
            return "propagation_unacknowledgeable"
        if propagation is Propagation.SNOOZE and not to_timedelta(
            rel.get(CONF_SNOOZE_DURATION)
        ):
            return "snooze_duration_missing"
    edges = {own: targets}
    for other_id, other in entry.subentries.items():
        if other.subentry_type != SUBENTRY_ALERT or other_id == subentry_id:
            continue
        if other_eid := _alert_entity_id(hass, other_id):
            edges[other_eid] = relationship_targets(other.data.get(CONF_SUPERSEDES, []))
    if find_cycle(edges):
        return "supersedes_cycle"
    return None


async def _async_triggers_valid(hass: HomeAssistant, triggers: Any) -> bool:
    """Return whether triggers are valid, and can be stored."""
    if not triggers or not is_storable(triggers):
        return False
    try:
        await async_validate_triggers(hass, triggers)
    except (vol.Invalid, HomeAssistantError):
        return False
    return True


def _check_threshold(data: dict[str, Any]) -> str | None:
    """Check a threshold alert: one value source, and at least one limit."""
    has_entity = CONF_ENTITY_ID in data
    if has_entity == (CONF_VALUE_TEMPLATE in data) or (
        CONF_ATTRIBUTE in data and not has_entity
    ):
        return "value_source"
    if CONF_MINIMUM not in data and CONF_MAXIMUM not in data:
        return "limit_required"
    try:
        low, high = float(data[CONF_MINIMUM]), float(data[CONF_MAXIMUM])
    except (KeyError, ValueError):
        # A limit that's missing, or a template: only known when it renders.
        return None
    return "invalid_limits" if low >= high else None


def _check_on_off(data: dict[str, Any]) -> str | None:
    """Check an on/off alert: each side needs a criterion, and delays a template.

    A delay needs its side to hold, which a trigger on its own can't (§4.1).
    """
    for template, triggers in (
        (CONF_ON_TEMPLATE, CONF_ON_TRIGGERS),
        (CONF_OFF_TEMPLATE, CONF_OFF_TRIGGERS),
    ):
        if template not in data and triggers not in data:
            return "criterion_required"
    for delay, template in (
        (CONF_DELAY_ON, CONF_ON_TEMPLATE),
        (CONF_DELAY_OFF, CONF_OFF_TEMPLATE),
    ):
        if (to_timedelta(data.get(delay)) or timedelta(0)) > timedelta(0) and (
            template not in data
        ):
            return "delay_needs_template"
    return None


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
