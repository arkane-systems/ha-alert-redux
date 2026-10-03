"""Tests for latching alerts: kept until acknowledged (spec §10)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    MockUser,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_SNOOZE_EXPIRED,
    EVENT_SNOOZED,
    EVENT_UNACKED,
)

from .conftest import (
    SetupAlerts,
    alert_state_alert,
    alert_subentry,
    event_alert,
    group_subentry,
    state_alert,
)

DOOR = "alert_redux.back_door_open"
SENSOR = "binary_sensor.back_door"
MOBILE = group_subentry(
    "Phones", "phones", actions=[{"action": "notify.mobile_app_phone"}]
)
DEFAULTS = {"default_groups": ["phones"]}
TAG = "alert_redux_back_door_open"


async def _call(
    hass: HomeAssistant, service: str, context: Context | None = None, **data: Any
) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": DOOR, **data}, blocking=True, context=context
    )
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _door(hass: HomeAssistant, state: str) -> None:
    hass.states.async_set(SENSOR, state)
    await hass.async_block_till_done()


def _messages(calls: list[ServiceCall]) -> list[str]:
    return [call.data["message"] for call in calls]


def _state(hass: HomeAssistant) -> str:
    return hass.states.get(DOOR).state


async def test_condition_alert_latches_and_ack_releases(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: MockUser
) -> None:
    """An unacknowledged firing that ends latches; acknowledging releases it."""
    await _door(hass, "off")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR, latching=True), MOBILE, options=DEFAULTS
    )
    ended = async_capture_events(hass, EVENT_ENDED)
    acked = async_capture_events(hass, EVENT_ACKED)
    await _door(hass, "on")
    await _door(hass, "off")
    state = hass.states.get(DOOR)
    assert state.state == "latched"
    assert state.attributes["latching"] is True
    assert state.attributes["fire_count"] == 1
    assert state.attributes["message"] == "Back Door Open is firing."
    assert ended[0].data["new_state"] == "latched"

    await _call(hass, "ack", Context(user_id=hass_admin_user.id))
    state = hass.states.get(DOOR)
    assert state.state == "idle"
    assert state.attributes["fire_count"] == 0
    assert state.attributes["last_acked_by"] == hass_admin_user.id
    assert acked[0].data["old_state"] == "latched"
    assert acked[0].data["new_state"] == "idle"


async def test_acknowledged_firing_ends_idle(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A firing acknowledged, or snoozed, before it ends doesn't latch."""
    await _door(hass, "off")
    await setup_alerts(state_alert("Back Door Open", SENSOR, latching=True))
    await _door(hass, "on")
    await _call(hass, "ack")
    await _door(hass, "off")
    assert _state(hass) == "idle"

    await _door(hass, "on")
    await _call(hass, "snooze", duration={"minutes": 30})
    await _door(hass, "off")
    assert _state(hass) == "idle"


async def test_without_the_setting_nothing_latches(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await _door(hass, "off")
    await setup_alerts(state_alert("Back Door Open", SENSOR))
    await _door(hass, "on")
    await _door(hass, "off")
    assert _state(hass) == "idle"
    assert hass.states.get(DOOR).attributes["latching"] is False


async def test_firing_again_is_the_same_item(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A latched alert that fires again carries its fire count on; an
    acknowledgement then covers the whole item."""
    await _door(hass, "off")
    await setup_alerts(state_alert("Back Door Open", SENSOR, latching=True))
    fired = async_capture_events(hass, EVENT_FIRED)
    for _ in range(3):
        await _door(hass, "on")
        await _door(hass, "off")
    state = hass.states.get(DOOR)
    assert state.state == "latched"
    assert state.attributes["fire_count"] == 3
    assert [event.data["old_state"] for event in fired] == [
        "idle",
        "latched",
        "latched",
    ]

    await _door(hass, "on")
    await _call(hass, "ack")
    await _door(hass, "off")
    assert _state(hass) == "idle"
    await _door(hass, "on")
    assert hass.states.get(DOOR).attributes["fire_count"] == 1


async def test_reminders_carry_on_and_done_keeps_buttons(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The done notification of a firing that latched keeps its buttons, and
    reminders carry on from the original schedule until acknowledged, which
    clears them."""
    await _door(hass, "off")
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        state_alert(
            "Back Door Open", SENSOR, latching=True, reminder_schedule=[10, 20]
        ),
        MOBILE,
        options=DEFAULTS,
    )
    await _door(hass, "on")
    await _tick(hass, freezer, 5)
    await _door(hass, "off")
    done = calls[-1]
    assert done.data["message"] == (
        "Back Door Open stopped firing after 5 minutes. "
        "It's kept until acknowledged."
    )
    titles = [action["title"] for action in done.data["data"]["actions"]]
    assert titles[0] == "Acknowledge"
    assert titles[1].startswith("Snooze Alert")
    # The first slot is 10 minutes after it started firing.
    await _tick(hass, freezer, 5)
    assert _messages(calls)[-1] == (
        "Back Door Open stopped firing 5 minutes ago and hasn't been acknowledged."
    )
    assert hass.states.get(DOOR).attributes["next_reminder"] is not None
    await _tick(hass, freezer, 20)
    assert _messages(calls)[-1] == (
        "Back Door Open stopped firing 25 minutes ago and hasn't been acknowledged."
    )
    await _call(hass, "ack")
    assert calls[-1].data["message"] == "clear_notification"
    assert calls[-1].data["data"]["tag"] == TAG
    assert hass.states.get(DOOR).attributes["next_reminder"] is None


async def test_latched_reminder_with_own_template(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """An alert's own reminder message is used while latched, with latched."""
    await _door(hass, "off")
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        state_alert(
            "Back Door Open",
            SENSOR,
            latching=True,
            reminder_schedule=[10],
            reminder_message="{{ 'latched' if latched else 'firing' }} {{ duration }}",
        ),
        MOBILE,
        options=DEFAULTS,
    )
    await _door(hass, "on")
    await _tick(hass, freezer, 10)
    await _door(hass, "off")
    await _tick(hass, freezer, 10)
    assert _messages(calls)[1] == "firing 10 minutes"
    assert _messages(calls)[-1] == "latched 10 minutes"


async def test_snoozing_a_latched_alert_puts_off_reminders(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """It stays latched while snoozed, and reminds again when the snooze ends."""
    await _door(hass, "off")
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        state_alert("Back Door Open", SENSOR, latching=True, reminder_schedule=[60]),
        MOBILE,
        options=DEFAULTS,
    )
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    expired = async_capture_events(hass, EVENT_SNOOZE_EXPIRED)
    acked = async_capture_events(hass, EVENT_ACKED)
    unacked = async_capture_events(hass, EVENT_UNACKED)
    await _door(hass, "on")
    await _door(hass, "off")
    await _call(hass, "snooze", duration={"minutes": 30})
    state = hass.states.get(DOOR)
    assert state.state == "latched"
    assert state.attributes["snoozed_until"] is not None
    assert state.attributes["next_reminder"] is None
    assert len(snoozed) == 1 and not acked

    sent = len(calls)
    await _tick(hass, freezer, 30)
    assert len(expired) == 1 and not unacked
    assert _state(hass) == "latched"
    assert hass.states.get(DOOR).attributes["snoozed_until"] is None
    # The snooze-end reminder: the next slot (at 60) isn't within the window.
    assert len(calls) == sent + 1
    assert "hasn't been acknowledged" in calls[-1].data["message"]

    # Unacknowledging a latched alert does nothing: it isn't acknowledged.
    await _call(hass, "unack")
    assert _state(hass) == "latched"


async def test_event_alert_latches_with_reminders(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A short event alert reminds once it has latched (spec §9.6, §10)."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        event_alert(
            "Back Door Open",
            "doorbell",
            latching=True,
            duration={"minutes": 1},
            reminder_schedule=[10],
        ),
        MOBILE,
        options=DEFAULTS,
    )
    assert hass.states.get(DOOR).attributes["reminder_schedule"] == [10]
    hass.bus.async_fire("doorbell")
    await hass.async_block_till_done()
    await _tick(hass, freezer, 1)
    assert _state(hass) == "latched"
    await _tick(hass, freezer, 9)
    assert "hasn't been acknowledged" in calls[-1].data["message"]


async def test_dismissal_latches_only_without_a_user(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: MockUser
) -> None:
    """A person dismissing the alert has seen it; an automation hasn't."""
    await setup_alerts(alert_subentry("Back Door Open", latching=True))
    await _call(hass, "fire")
    await _call(hass, "dismiss", Context(user_id=hass_admin_user.id))
    assert _state(hass) == "idle"

    await _call(hass, "fire")
    await _call(hass, "dismiss")
    assert _state(hass) == "latched"


async def test_disable_clears_the_latch(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(alert_subentry("Back Door Open", latching=True))
    await _call(hass, "fire")
    await _call(hass, "dismiss")
    ended = async_capture_events(hass, EVENT_ENDED)
    await _call(hass, "disable")
    assert _state(hass) == "disabled"
    assert not ended
    await _call(hass, "enable")
    assert _state(hass) == "idle"
    assert hass.states.get(DOOR).attributes["fire_count"] == 0


async def test_latch_survives_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The latch is kept; a reminder due while down is sent once (§15.1)."""
    await _door(hass, "off")
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = await setup_alerts(
        state_alert("Back Door Open", SENSOR, latching=True, reminder_schedule=[10]),
        MOBILE,
        options=DEFAULTS,
    )
    await _door(hass, "on")
    await _door(hass, "off")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=15))
    sent = len(calls)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass) == "latched"
    assert len(calls) == sent + 1
    assert "hasn't been acknowledged" in calls[-1].data["message"]


async def test_turning_the_setting_off_releases(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(
        alert_subentry("Back Door Open", subentry_id="door", latching=True)
    )
    await _call(hass, "fire")
    await _call(hass, "dismiss")
    assert _state(hass) == "latched"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = entry.subentries["door"]
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, "latching": False}
    )
    await hass.async_block_till_done()
    state = hass.states.get(DOOR)
    assert state.state == "idle"
    assert state.attributes["last_acked"] is None


async def test_summary_counts_latched_as_unacknowledged(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(
        alert_subentry("Back Door Open", latching=True, priority="critical")
    )
    await _call(hass, "fire")
    await _call(hass, "dismiss")
    assert hass.states.get("sensor.alert_redux_latched").state == "1"
    assert hass.states.get("sensor.alert_redux_latched").attributes[
        "entity_ids"
    ] == [DOOR]
    assert hass.states.get("sensor.alert_redux_active").state == "1"
    assert hass.states.get("sensor.alert_redux_firing").state == "0"
    assert (
        hass.states.get("sensor.alert_redux_highest_unacked_priority").state
        == "critical"
    )
    assert hass.states.get("sensor.alert_redux_highest_priority").state == "none"
    await _call(hass, "ack")
    assert hass.states.get("sensor.alert_redux_latched").state == "0"
    assert hass.states.get("sensor.alert_redux_active").state == "0"


async def test_latching_needs_acknowledgeable(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An unacknowledgeable alert stored as latching doesn't latch: it could
    never be released (the forms refuse it)."""
    await setup_alerts(
        alert_subentry("Back Door Open", latching=True, acknowledgeable=False)
    )
    await _call(hass, "fire")
    await _call(hass, "dismiss")
    assert _state(hass) == "idle"
    assert hass.states.get(DOOR).attributes["latching"] is False


# Supersession (spec §8, §10)

OPEN = "alert_redux.workshop_door_open"
LEFT_OPEN = "alert_redux.workshop_door_left_open"


async def _workshop(setup_alerts: SetupAlerts, propagation: str | None) -> None:
    relationship: dict[str, Any] = {"alert": OPEN}
    if propagation:
        relationship["propagation"] = propagation
        if propagation == "snooze":
            relationship["snooze_duration"] = {"minutes": 30}
    await setup_alerts(
        alert_subentry("Workshop Door Open", latching=True),
        alert_subentry(
            "Workshop Door Left Open", latching=True, supersedes=[relationship]
        ),
    )


async def _both_latched(hass: HomeAssistant) -> None:
    for service in ("fire", "dismiss"):
        for entity_id in (OPEN, LEFT_OPEN):
            await hass.services.async_call(
                DOMAIN, service, {"entity_id": entity_id}, blocking=True
            )
    await hass.async_block_till_done()
    assert hass.states.get(OPEN).state == "latched"
    assert hass.states.get(LEFT_OPEN).state == "latched"


async def test_latched_alert_supersedes_nothing(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A latched superseding alert isn't firing, so the alert it supersedes
    isn't hidden; one that is firing still hides a latched alert."""
    await _workshop(setup_alerts, None)
    await _both_latched(hass)
    assert hass.states.get(OPEN).attributes["superseded_by"] == []

    await hass.services.async_call(
        DOMAIN, "fire", {"entity_id": LEFT_OPEN}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(OPEN).attributes["superseded_by"] == [LEFT_OPEN]
    assert hass.states.get("sensor.alert_redux_superseded").attributes[
        "entity_ids"
    ] == [OPEN]
    assert hass.states.get("sensor.alert_redux_active").attributes[
        "entity_ids"
    ] == [LEFT_OPEN]


async def test_acknowledging_a_latched_alert_propagates_to_latched(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await _workshop(setup_alerts, "acknowledge")
    await _both_latched(hass)
    acked = async_capture_events(hass, EVENT_ACKED)
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": OPEN}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(OPEN).state == "idle"
    assert hass.states.get(LEFT_OPEN).state == "idle"
    assert acked[-1].data["entity_id"] == LEFT_OPEN
    assert acked[-1].data["pre_acked_by"] == [OPEN]


async def test_snooze_propagation_to_latched(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await _workshop(setup_alerts, "snooze")
    await _both_latched(hass)
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": OPEN}, blocking=True)
    await hass.async_block_till_done()
    state = hass.states.get(LEFT_OPEN)
    assert state.state == "latched"
    assert state.attributes["snoozed_until"] is not None


async def test_no_propagation_leaves_latched(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await _workshop(setup_alerts, None)
    await _both_latched(hass)
    await hass.services.async_call(DOMAIN, "ack", {"entity_id": OPEN}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(LEFT_OPEN).state == "latched"


async def test_alert_state_alert_watches_latched(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """An alert state alert can escalate a latched alert (spec §4.1)."""
    await setup_alerts(
        alert_subentry("Back Door Open", latching=True),
        alert_state_alert("Back Door Unseen", DOOR, ["latched"]),
    )
    await _call(hass, "fire")
    assert hass.states.get("alert_redux.back_door_unseen").state == "idle"
    await _call(hass, "dismiss")
    assert hass.states.get("alert_redux.back_door_unseen").state == "active"
    await _call(hass, "ack")
    assert hass.states.get("alert_redux.back_door_unseen").state == "idle"
