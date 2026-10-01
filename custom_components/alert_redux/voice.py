"""Voice control through Assist (spec §14.1).

Four intents carry the behaviour: acknowledging, removing an acknowledgement,
snoozing, and asking which alerts are firing. They're reached three ways: by
the English sentences below, attached as Home Assistant's own conversation
triggers (which an Assist pipeline checks before any conversation agent, LLM
agents included); by LLM agents, as tools (llm.py, or by Home Assistant itself
before 2026.6); and by anyone's custom sentences, in any language.

The intents act through the alert actions, with the speaker's context, so the
rules of §6 and §16 apply unchanged; they check the alert's state first only to
say why nothing happened.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components.homeassistant.exposed_entities import (
    async_should_expose,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    intent,
)
from homeassistant.helpers.script import ScriptRunResult
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.trigger import async_initialize_triggers
from homeassistant.util import dt as dt_util

from . import speech
from .const import (
    ATTR_DURATION,
    DATA_ENTITIES,
    DOMAIN,
    SERVICE_ACK,
    SERVICE_SNOOZE,
    SERVICE_UNACK,
    AlertState,
)
from .entity import AlertEntity
from .speech import Candidate, Firing
from .triggers import async_validate_triggers

_LOGGER = logging.getLogger(__name__)

INTENT_ACK = "AlertReduxAcknowledge"
INTENT_UNACK = "AlertReduxUnacknowledge"
INTENT_SNOOZE = "AlertReduxSnooze"
INTENT_LIST = "AlertReduxListFiring"
INTENTS = (INTENT_ACK, INTENT_UNACK, INTENT_SNOOZE, INTENT_LIST)

SLOT_NAME = "name"
SLOT_MINUTES = "minutes"

# The assistant that voice commands answer to; an alert must be exposed to it.
ASSISTANT = "conversation"

# English sentences, as conversation triggers. Every {…} is a wildcard: it
# captures whatever was said, and the intent does the matching. "Acknowledge
# the alert" captures "alert", which names no alert.
SENTENCES: dict[str, list[str]] = {
    INTENT_ACK: ["(acknowledge|ack) [the] {alert}"],
    INTENT_UNACK: [
        "(unacknowledge|un acknowledge|unack) [the] {alert}",
        "remove [the] acknowledgement (from|for|on) [the] {alert}",
    ],
    INTENT_SNOOZE: ["snooze [the] {alert} for {duration}", "snooze [the] {alert}"],
    INTENT_LIST: [
        "(what|which) alerts are (firing|active|on)",
        "are there any [active|firing] alerts",
        "list [the] [active|firing] alerts",
    ],
}


@callback
def async_exposed_alerts(
    hass: HomeAssistant, assistant: str | None = None
) -> list[AlertEntity]:
    """Return the alerts exposed to an assistant (Assist, by default)."""
    assistant = assistant or ASSISTANT
    return [
        entity
        for entity in hass.data[DOMAIN].get(DATA_ENTITIES, {}).values()
        if entity.hass is not None
        and hass.states.get(entity.entity_id) is not None
        and async_should_expose(hass, assistant, entity.entity_id)
    ]


def _candidate(hass: HomeAssistant, entity: AlertEntity) -> Candidate:
    """Return what an alert can be called: its name as shown, and its aliases."""
    state = hass.states.get(entity.entity_id)
    name = state.name if state is not None else entity.entity_id
    aliases: tuple[str, ...] = ()
    if (entry := er.async_get(hass).async_get(entity.entity_id)) is not None:
        aliases = tuple(alias for alias in entry.aliases if isinstance(alias, str))
    return Candidate(entity.entity_id, name, aliases)


class _AlertIntent(intent.IntentHandler):
    """An intent that acts on one alert, named or the only one that fits."""

    platforms = {DOMAIN}
    action = ""
    service = ""

    @property
    def slot_schema(self) -> dict | None:
        """Return the slots: the alert's name, optional."""
        return {vol.Optional(SLOT_NAME): cv.string}

    def fits(self, entity: AlertEntity) -> bool:
        """Return whether the action would do something to the alert."""
        raise NotImplementedError

    def refusal(self, entity: AlertEntity, name: str) -> str | None:
        """Return why the action wouldn't do anything to the alert, if it wouldn't."""
        raise NotImplementedError

    def done(self, entity: AlertEntity, name: str, slots: dict[str, Any]) -> str:
        """Return the reply once the action is done."""
        raise NotImplementedError

    def service_data(
        self, entity: AlertEntity, slots: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the action's data, besides the entity."""
        return {}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Act on the alert, or say why not."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        spoken = slots.get(SLOT_NAME, {}).get("value") or ""
        alerts = {
            e.entity_id: e for e in async_exposed_alerts(hass, intent_obj.assistant)
        }
        candidates = [_candidate(hass, entity) for entity in alerts.values()]
        names = {candidate.entity_id: candidate.name for candidate in candidates}

        if speech.normalise(spoken):
            matches = speech.match(spoken, candidates)
            if not matches:
                return _reply(intent_obj, speech.no_such_alert(spoken))
            if len(matches) > 1:
                return _reply(intent_obj, speech.which_one([m.name for m in matches]))
            entity = alerts[matches[0].entity_id]
        else:
            fitting = [entity for entity in alerts.values() if self.fits(entity)]
            if not fitting:
                return _reply(intent_obj, speech.nothing_to(self.action))
            if len(fitting) > 1:
                return _reply(
                    intent_obj, speech.which_one([names[e.entity_id] for e in fitting])
                )
            entity = fitting[0]

        name = names[entity.entity_id]
        if (refusal := self.refusal(entity, name)) is not None:
            return _reply(intent_obj, refusal)
        try:
            await hass.services.async_call(
                DOMAIN,
                self.service,
                {ATTR_ENTITY_ID: entity.entity_id, **self.service_data(entity, slots)},
                blocking=True,
                context=intent_obj.context,
            )
        except HomeAssistantError as err:
            return _reply(intent_obj, str(err) or f"Couldn't {self.action} {name}.")
        return _reply(intent_obj, self.done(entity, name, slots))


class AcknowledgeIntent(_AlertIntent):
    """Acknowledge an alert (§6.1)."""

    intent_type = INTENT_ACK
    description = (
        "Acknowledges a firing Alert Redux alert, which stops its reminders. "
        "Give the alert's name, or leave it out if only one alert needs "
        "acknowledging."
    )
    action = "acknowledge"
    service = SERVICE_ACK

    def fits(self, entity: AlertEntity) -> bool:
        """Return whether the alert is unacknowledged, and can be acknowledged."""
        return entity.state == AlertState.ACTIVE and entity.acknowledgeable

    def refusal(self, entity: AlertEntity, name: str) -> str | None:
        """Return why the alert can't be acknowledged now, if it can't."""
        if not entity.firing:
            return speech.not_firing(name)
        if not entity.acknowledgeable:
            return speech.not_acknowledgeable(name)
        if entity.state == AlertState.ACK and entity.snoozed_until is None:
            return speech.already_acknowledged(name)
        return None

    def done(self, entity: AlertEntity, name: str, slots: dict[str, Any]) -> str:
        """Return the reply."""
        return speech.acknowledged(name)


class UnacknowledgeIntent(_AlertIntent):
    """Remove an alert's acknowledgement (§6.1)."""

    intent_type = INTENT_UNACK
    description = (
        "Removes the acknowledgement from an acknowledged (or snoozed) Alert "
        "Redux alert, so that it reminds again. Give the alert's name, or leave "
        "it out if only one alert is acknowledged."
    )
    action = "unacknowledge"
    service = SERVICE_UNACK

    def fits(self, entity: AlertEntity) -> bool:
        """Return whether the alert is acknowledged."""
        return entity.state == AlertState.ACK

    def refusal(self, entity: AlertEntity, name: str) -> str | None:
        """Return why the acknowledgement can't be removed, if it can't."""
        if not entity.firing:
            return speech.not_firing(name)
        if entity.state != AlertState.ACK:
            return speech.not_acknowledged(name)
        return None

    def done(self, entity: AlertEntity, name: str, slots: dict[str, Any]) -> str:
        """Return the reply."""
        return speech.unacknowledged(name)


class SnoozeIntent(_AlertIntent):
    """Snooze an alert (§6.2)."""

    intent_type = INTENT_SNOOZE
    description = (
        "Snoozes a firing Alert Redux alert: acknowledges it for a number of "
        "minutes, after which it reminds again. Without minutes, the alert's "
        "own snooze duration is used. Give the alert's name, or leave it out "
        "if only one alert can be snoozed."
    )
    action = "snooze"
    service = SERVICE_SNOOZE

    @property
    def slot_schema(self) -> dict | None:
        """Return the slots: the alert's name, and the minutes, both optional."""
        return {
            vol.Optional(SLOT_NAME): cv.string,
            vol.Optional(SLOT_MINUTES): vol.All(
                vol.Coerce(float), vol.Range(min=0, min_included=False)
            ),
        }

    def fits(self, entity: AlertEntity) -> bool:
        """Return whether the alert is firing, and can be snoozed."""
        return entity.firing and entity.acknowledgeable

    def refusal(self, entity: AlertEntity, name: str) -> str | None:
        """Return why the alert can't be snoozed now, if it can't."""
        if not entity.firing:
            return speech.not_firing(name)
        if not entity.acknowledgeable:
            return speech.not_acknowledgeable(name)
        return None

    def _duration(self, entity: AlertEntity, slots: dict[str, Any]) -> timedelta:
        if (minutes := slots.get(SLOT_MINUTES, {}).get("value")) is not None:
            return timedelta(minutes=minutes)
        return entity.button_snooze

    def service_data(
        self, entity: AlertEntity, slots: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the snooze's duration."""
        return {ATTR_DURATION: self._duration(entity, slots)}

    def done(self, entity: AlertEntity, name: str, slots: dict[str, Any]) -> str:
        """Return the reply."""
        return speech.snoozed(name, self._duration(entity, slots))


class ListFiringIntent(intent.IntentHandler):
    """Say which alerts are firing."""

    intent_type = INTENT_LIST
    description = (
        "Lists the Alert Redux alerts that are firing, highest priority first, "
        "saying which are acknowledged or snoozed."
    )
    platforms = {DOMAIN}

    @property
    def slot_schema(self) -> dict | None:
        """Return the slots: none."""
        return {}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """List the firing alerts."""
        hass = intent_obj.hass
        now = dt_util.utcnow()
        firing = sorted(
            (e for e in async_exposed_alerts(hass, intent_obj.assistant) if e.firing),
            key=lambda e: (e.priority.rank, e.state != AlertState.ACTIVE),
        )
        return _reply(
            intent_obj,
            speech.firing_alerts(
                [
                    Firing(
                        _candidate(hass, entity).name,
                        entity.state == AlertState.ACK,
                        None
                        if entity.snoozed_until is None
                        else entity.snoozed_until - now,
                    )
                    for entity in firing
                ]
            ),
        )


def _reply(intent_obj: intent.Intent, text: str) -> intent.IntentResponse:
    response = intent_obj.create_response()
    response.async_set_speech(text)
    return response


HANDLERS: tuple[Callable[[], intent.IntentHandler], ...] = (
    AcknowledgeIntent,
    UnacknowledgeIntent,
    SnoozeIntent,
    ListFiringIntent,
)


@callback
def async_setup_voice(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Register the intents, and attach their sentences once HA has started."""
    for handler in HANDLERS:
        intent.async_register(hass, handler())
    unsubs: list[CALLBACK_TYPE] = []
    unloaded = False

    async def _attach() -> None:
        # Without the conversation integration, there's nothing to hear them.
        if "conversation" not in hass.config.components:
            return
        for intent_type, sentences in SENTENCES.items():
            config = await async_validate_triggers(
                hass, [{"trigger": "conversation", "command": sentences}]
            )
            unsub = await async_initialize_triggers(
                hass, config, _sentence_action(hass, intent_type), DOMAIN, "voice", _log
            )
            if unsub is not None:
                if unloaded:
                    unsub()
                    return
                unsubs.append(unsub)

    @callback
    def _started(_hass: HomeAssistant) -> None:
        hass.async_create_task(_attach(), f"{DOMAIN} voice sentences")

    unsubs.append(async_at_started(hass, _started))

    @callback
    def _unload() -> None:
        nonlocal unloaded
        unloaded = True
        while unsubs:
            unsubs.pop()()
        for intent_type in INTENTS:
            intent.async_remove(hass, intent_type)

    return _unload


def _sentence_action(hass: HomeAssistant, intent_type: str) -> Callable[..., Any]:
    """Return a sentence trigger's action: the intent, with the spoken slots."""

    async def _action(
        run_variables: dict[str, Any], context: Context | None = None
    ) -> ScriptRunResult:
        trigger = run_variables["trigger"]
        spoken = trigger.get("slots", {})
        user_input = trigger.get("user_input", {})
        caller = user_input.get("context", {})
        slots: dict[str, Any] = {}
        if alert := spoken.get("alert"):
            slots[SLOT_NAME] = {"value": alert}
        if intent_type == INTENT_SNOOZE and (said := spoken.get("duration")):
            if (duration := speech.parse_duration(said)) is None:
                return _result(speech.how_long())
            slots[SLOT_MINUTES] = {"value": duration.total_seconds() / 60}
        response = await intent.async_handle(
            hass,
            DOMAIN,
            intent_type,
            slots,
            text_input=trigger.get("sentence"),
            context=Context(user_id=caller.get("user_id"), parent_id=caller.get("id")),
            language=user_input.get("language"),
            assistant=ASSISTANT,
            device_id=trigger.get("device_id"),
        )
        return _result(response.speech.get("plain", {}).get("speech", ""))

    return _action


def _result(text: str) -> ScriptRunResult:
    return ScriptRunResult(
        conversation_response=text, service_response=None, variables={}
    )


def _log(level: int, message: str, **kwargs: Any) -> None:
    _LOGGER.log(level, "voice: %s", message, **kwargs)
