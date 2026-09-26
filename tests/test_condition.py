"""Tests for condition alerts: state and template kinds (spec §4.1, §4.4)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_DATA_RESTORED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_NO_DATA,
)

from .conftest import SetupAlerts, state_alert, template_alert

SENSOR = "binary_sensor.back_door"
ALERT = "alert_redux.back_door_open"
TEMP = "sensor.server_room"
HOT = "alert_redux.server_room_hot"


async def _set(hass: HomeAssistant, entity_id: str, state: str) -> None:
    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str = ALERT) -> str:
    return hass.states.get(entity_id).state


@pytest.fixture
def events(hass: HomeAssistant) -> dict[str, list]:
    return {
        name: async_capture_events(hass, event)
        for name, event in (
            ("fired", EVENT_FIRED),
            ("ended", EVENT_ENDED),
            ("no_data", EVENT_NO_DATA),
            ("acked", EVENT_ACKED),
            ("restored", EVENT_DATA_RESTORED),
        )
    }


async def test_state_alert_fires_and_ends(
    hass: HomeAssistant, setup_alerts: SetupAlerts, events: dict[str, list]
) -> None:
    hass.states.async_set(SENSOR, "off")
    await setup_alerts(state_alert("Back Door Open", SENSOR))

    state = hass.states.get(ALERT)
    assert state.state == "idle"
    assert state.attributes["kind"] == "state"
    assert state.attributes["source_entity"] == SENSOR
    assert state.attributes["target_state"] == "on"
    assert state.attributes["subject_entity"] == SENSOR
    assert state.attributes["no_data_since"] is None
    assert "user_dismissable" not in state.attributes

    await _set(hass, SENSOR, "on")
    assert _state(hass) == "active"
    assert len(events["fired"]) == 1
    assert events["fired"][0].data["kind"] == "state"
    assert events["fired"][0].data["user_id"] is None

    await _set(hass, SENSOR, "off")
    assert _state(hass) == "idle"
    assert len(events["ended"]) == 1
    assert events["ended"][0].data["reason"] == "resolved"
    assert events["ended"][0].data["old_state"] == "active"


async def test_already_true_at_setup(
    hass: HomeAssistant, setup_alerts: SetupAlerts, events: dict[str, list]
) -> None:
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(state_alert("Back Door Open", SENSOR))
    assert _state(hass) == "active"
    assert len(events["fired"]) == 1


async def test_delays(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    events: dict[str, list],
    freezer: FrozenDateTimeFactory,
) -> None:
    """delay_on needs the condition throughout; delay_off absorbs a flicker."""
    hass.states.async_set(SENSOR, "off")
    await setup_alerts(
        state_alert(
            "Back Door Open",
            SENSOR,
            delay_on={"minutes": 5},
            delay_off={"seconds": 30},
        )
    )
    assert hass.states.get(ALERT).attributes["delay_on"] == 300

    await _set(hass, SENSOR, "on")
    assert _state(hass) == "idle"
    assert hass.states.get(ALERT).attributes["delay_on_until"] is not None
    await _tick(hass, freezer, timedelta(minutes=3))
    await _set(hass, SENSOR, "off")
    await _tick(hass, freezer, timedelta(minutes=3))
    assert _state(hass) == "idle"
    assert not events["fired"]

    await _set(hass, SENSOR, "on")
    await _tick(hass, freezer, timedelta(minutes=4, seconds=59))
    assert _state(hass) == "idle"
    await _tick(hass, freezer, timedelta(seconds=1))
    assert _state(hass) == "active"
    assert len(events["fired"]) == 1

    await hass.services.async_call(DOMAIN, "ack", {"entity_id": ALERT}, blocking=True)
    await _set(hass, SENSOR, "off")
    await _tick(hass, freezer, timedelta(seconds=20))
    await _set(hass, SENSOR, "on")
    await _tick(hass, freezer, timedelta(minutes=1))
    assert _state(hass) == "ack"
    assert not events["ended"]

    await _set(hass, SENSOR, "off")
    await _tick(hass, freezer, timedelta(seconds=30))
    assert _state(hass) == "idle"
    assert len(events["ended"]) == 1


async def test_dropout_within_grace(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    events: dict[str, list],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A firing alert keeps its state and ack through a short dropout."""
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(state_alert("Back Door Open", SENSOR))
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": ALERT}, blocking=True)

    await _set(hass, SENSOR, "unavailable")
    state = hass.states.get(ALERT)
    assert state.state == "ack"
    assert state.attributes["no_data_since"] is not None
    assert state.attributes["missing_inputs"] == [SENSOR]
    assert state.attributes["no_data_grace"] == 600
    assert state.attributes["no_data_grace_until"] is not None
    assert len(events["no_data"]) == 1
    assert events["no_data"][0].data["old_state"] == "ack"
    assert events["no_data"][0].data["new_state"] == "ack"
    assert events["no_data"][0].data["missing_inputs"] == [SENSOR]
    # The alert's own change isn't attributed to whoever last acknowledged it.
    assert events["no_data"][0].data["user_id"] is None

    await _tick(hass, freezer, timedelta(minutes=9))
    await _set(hass, SENSOR, "on")
    state = hass.states.get(ALERT)
    assert state.state == "ack"
    assert state.attributes["no_data_since"] is None
    assert state.attributes["missing_inputs"] == []
    # No state changed, but the return is announced, with what was missing.
    assert len(events["restored"]) == 1
    assert events["restored"][0].data["old_state"] == "ack"
    assert events["restored"][0].data["new_state"] == "ack"
    assert events["restored"][0].data["missing_inputs"] == [SENSOR]
    await _tick(hass, freezer, timedelta(minutes=5))
    assert _state(hass) == "ack"
    assert not events["ended"]
    assert len(events["fired"]) == 1


async def test_dropout_past_grace(
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    events: dict[str, list],
    freezer: FrozenDateTimeFactory,
) -> None:
    """The per-alert grace period overrides the default; running out ends it."""
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR, no_data_grace={"minutes": 2})
    )
    await _set(hass, SENSOR, "unavailable")
    await _tick(hass, freezer, timedelta(minutes=2))
    assert _state(hass) == "no_data"
    assert len(events["ended"]) == 1
    assert events["ended"][0].data["reason"] == "no_data"
    assert events["ended"][0].data["new_state"] == "no_data"
    assert len(events["no_data"]) == 1

    # Data returning is announced, then starts a new firing.
    order: list[str] = []
    for event_type in (EVENT_DATA_RESTORED, EVENT_FIRED):
        hass.bus.async_listen(
            event_type, callback(lambda event: order.append(event.event_type))
        )
    await _set(hass, SENSOR, "on")
    assert _state(hass) == "active"
    assert len(events["fired"]) == 2
    assert events["restored"][0].data["old_state"] == "no_data"
    assert order == [EVENT_DATA_RESTORED, EVENT_FIRED]


async def test_dropout_while_idle(
    hass: HomeAssistant, setup_alerts: SetupAlerts, events: dict[str, list]
) -> None:
    hass.states.async_set(SENSOR, "off")
    await setup_alerts(state_alert("Back Door Open", SENSOR))
    await _set(hass, SENSOR, "unknown")
    assert _state(hass) == "no_data"
    assert events["no_data"][0].data["old_state"] == "idle"
    assert events["no_data"][0].data["new_state"] == "no_data"
    await _set(hass, SENSOR, "off")
    assert _state(hass) == "idle"


async def test_late_entity(
    hass: HomeAssistant, setup_alerts: SetupAlerts, events: dict[str, list]
) -> None:
    """An alert whose entity doesn't exist yet waits in no_data, quietly."""
    await setup_alerts(state_alert("Back Door Open", SENSOR))
    state = hass.states.get(ALERT)
    assert state.state == "no_data"
    assert state.attributes["missing_inputs"] == [SENSOR]
    assert not events["no_data"]
    await _set(hass, SENSOR, "on")
    assert _state(hass) == "active"


async def test_target_unavailable(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set("lock.front", "locked")
    await setup_alerts(
        state_alert("Front Lock Offline", "lock.front", target_state="unavailable")
    )
    entity_id = "alert_redux.front_lock_offline"
    assert _state(hass, entity_id) == "idle"
    await _set(hass, "lock.front", "unavailable")
    assert _state(hass, entity_id) == "active"


async def test_template_alert(
    hass: HomeAssistant, setup_alerts: SetupAlerts, events: dict[str, list]
) -> None:
    hass.states.async_set(TEMP, "20")
    await setup_alerts(
        template_alert(
            "Server Room Hot",
            "{{ states('sensor.server_room') | float > 30 }}",
            subject_entity=TEMP,
        )
    )
    state = hass.states.get(HOT)
    assert state.state == "idle"
    assert state.attributes["kind"] == "template"
    assert state.attributes["template"].startswith("{{")
    assert state.attributes["subject_entity"] == TEMP
    assert "source_entity" not in state.attributes

    await _set(hass, TEMP, "35")
    assert _state(hass, HOT) == "active"
    await _set(hass, TEMP, "unavailable")
    state = hass.states.get(HOT)
    assert state.state == "active"
    assert state.attributes["missing_inputs"] == [TEMP]
    await _set(hass, TEMP, "25")
    assert _state(hass, HOT) == "idle"


async def test_extra_condition(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """The extra condition is ANDed with the main criterion, both ways."""
    hass.states.async_set(SENSOR, "on")
    hass.states.async_set("input_boolean.away", "off")
    await setup_alerts(
        state_alert(
            "Back Door Open",
            SENSOR,
            condition="{{ is_state('input_boolean.away', 'on') }}",
        )
    )
    assert hass.states.get(ALERT).attributes["condition"].startswith("{{")
    assert _state(hass) == "idle"
    await _set(hass, "input_boolean.away", "on")
    assert _state(hass) == "active"
    await _set(hass, "input_boolean.away", "off")
    assert _state(hass) == "idle"


async def test_fire_and_dismiss_refused(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(state_alert("Back Door Open", SENSOR))
    for service in ("fire", "dismiss"):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, service, {"entity_id": ALERT}, blocking=True
            )


async def test_default_grace_from_options(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set(SENSOR, "on")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR),
        options={"no_data_grace": {"minutes": 3}},
    )
    assert hass.states.get(ALERT).attributes["no_data_grace"] == 180
