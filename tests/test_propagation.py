"""Tests for propagating acknowledgements along supersession (spec §8.2, §8.3)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_FIRED,
    EVENT_SNOOZED,
    STORAGE_KEY,
)

from .conftest import SetupAlerts, alert_subentry, group_subentry, state_alert

OPEN = "alert_redux.workshop_door_open"
LEFT_OPEN = "alert_redux.workshop_door_left_open"
OVERNIGHT = "alert_redux.workshop_door_open_overnight"
DOOR = "binary_sensor.workshop_door"
PHONE = group_subentry("Phones", "phones", actions=[{"action": "notify.phone"}])
DEFAULTS = {"default_groups": ["phones"]}


def _supersedes(entity_id: str, propagation: str | None = None, **rel: Any) -> list:
    relationship = {"alert": entity_id, **rel}
    if propagation:
        relationship["propagation"] = propagation
    return [relationship]


async def _call(
    hass: HomeAssistant, service: str, entity_id: str, **data: Any
) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": entity_id, **data}, blocking=True
    )
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _titles(calls: list[ServiceCall]) -> list[str]:
    return [call.data["title"] for call in calls]


def _attrs(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    return dict(hass.states.get(entity_id).attributes)


async def _pair(
    setup_alerts: SetupAlerts, propagation: str | None, **rel: Any
) -> None:
    """Workshop Door Open, superseded by Workshop Door Left Open (manual alerts)."""
    await setup_alerts(
        alert_subentry("Workshop Door Open"),
        alert_subentry(
            "Workshop Door Left Open",
            supersedes=_supersedes(OPEN, propagation, **rel),
            reminder_schedule=[15, 30, 60],
        ),
        PHONE,
        options=DEFAULTS,
    )


async def test_workshop_example(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Spec §8.3: acknowledging Open covers Left Open; one done notification."""
    hass.states.async_set(DOOR, "off")
    calls = async_mock_service(hass, "notify", "phone")
    fired = async_capture_events(hass, EVENT_FIRED)
    acked = async_capture_events(hass, EVENT_ACKED)
    await setup_alerts(
        state_alert("Workshop Door Open", DOOR),
        state_alert(
            "Workshop Door Left Open",
            DOOR,
            delay_on={"minutes": 5},
            supersedes=_supersedes(OPEN, "acknowledge"),
        ),
        PHONE,
        options=DEFAULTS,
    )

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _tick(hass, freezer, 0.1)
    assert _titles(calls) == ["Workshop Door Open"]

    await _call(hass, "ack", OPEN)
    attributes = _attrs(hass, LEFT_OPEN)
    assert attributes["pre_acked_by"] == [OPEN]
    assert attributes["pre_snoozed_until"] is None

    # Left Open fires acknowledged, without an on notification.
    await _tick(hass, freezer, 5)
    assert hass.states.get(LEFT_OPEN).state == "ack"
    assert _titles(calls) == ["Workshop Door Open"]
    assert [event.data["entity_id"] for event in fired] == [OPEN, LEFT_OPEN]
    left_acked = [event for event in acked if event.data["entity_id"] == LEFT_OPEN]
    assert len(left_acked) == 1
    assert left_acked[0].data["pre_acked_by"] == [OPEN]
    assert left_acked[0].data["old_state"] == "active"
    assert left_acked[0].data["new_state"] == "ack"

    # Closing the door: exactly one done notification, Left Open's.
    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    await _tick(hass, freezer, 0.2)
    assert _titles(calls) == ["Workshop Door Open", "Workshop Door Left Open"]
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []


async def test_back_door_pre_snooze(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Spec §8.3's example: fired 10:00 on [15, 30, 60], pre-snooze ends 10:50;
    a reminder at 10:50 ("50 minutes"), the next at 11:45, and no on message."""
    calls = async_mock_service(hass, "notify", "phone")
    await _pair(setup_alerts, "snooze", snooze_duration={"minutes": 60})

    # 09:50: Open fires and is acknowledged, pre-snoozing Left Open until 10:50.
    await _call(hass, "fire", OPEN)
    await _call(hass, "ack", OPEN)
    deadline = _attrs(hass, LEFT_OPEN)["pre_snoozed_until"]
    assert deadline is not None
    calls.clear()

    # 10:00: Left Open fires, snoozed until 10:50.
    await _tick(hass, freezer, 10)
    await _call(hass, "fire", LEFT_OPEN)
    state = hass.states.get(LEFT_OPEN)
    assert state.state == "ack"
    assert state.attributes["snoozed_until"] == deadline
    assert calls == []

    # 10:50: the snooze runs out; a reminder, but no on message.
    await _tick(hass, freezer, 50)
    assert hass.states.get(LEFT_OPEN).state == "active"
    assert [call.data["message"] for call in calls] == [
        "Workshop Door Left Open is still firing (50 minutes)."
    ]
    # The next is 11:45, on the original schedule (10:15, 10:45, 11:45).
    await _tick(hass, freezer, 54)
    assert len(calls) == 1
    await _tick(hass, freezer, 1)
    assert calls[-1].data["message"] == (
        "Workshop Door Left Open is still firing (1 hour 45 minutes)."
    )


async def test_pre_snooze_runs_out_before_firing(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Firing after the deadline starts active, as normal."""
    calls = async_mock_service(hass, "notify", "phone")
    await _pair(setup_alerts, "snooze", snooze_duration={"minutes": 30})
    await _call(hass, "fire", OPEN)
    await _call(hass, "ack", OPEN)
    await _tick(hass, freezer, 31)
    # Forgotten once it runs out, so the attributes stay right.
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []
    calls.clear()
    await _call(hass, "fire", LEFT_OPEN)
    assert hass.states.get(LEFT_OPEN).state == "active"
    assert _titles(calls) == ["Workshop Door Left Open"]


async def test_no_propagation_by_default(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Server room (spec §8.2): acknowledging the Warning leaves the Critical."""
    await _pair(setup_alerts, None)
    await _call(hass, "fire", OPEN)
    await _call(hass, "ack", OPEN)
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []
    await _call(hass, "fire", LEFT_OPEN)
    assert hass.states.get(LEFT_OPEN).state == "active"


async def test_acknowledges_an_active_superseder(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user
) -> None:
    """An already active superseding alert is acknowledged at once, by the same
    user."""
    acked = async_capture_events(hass, EVENT_ACKED)
    await _pair(setup_alerts, "acknowledge")
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await hass.services.async_call(
        DOMAIN,
        "ack",
        {"entity_id": OPEN},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()
    state = hass.states.get(LEFT_OPEN)
    assert state.state == "ack"
    assert state.attributes["last_acked_by"] == hass_admin_user.id
    (left,) = [event for event in acked if event.data["entity_id"] == LEFT_OPEN]
    assert left.data["pre_acked_by"] == [OPEN]
    assert left.data["user_id"] == hass_admin_user.id


async def test_snoozes_an_active_superseder(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    await _pair(setup_alerts, "snooze", snooze_duration={"minutes": 60})
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _call(hass, "ack", OPEN)
    state = hass.states.get(LEFT_OPEN)
    assert state.state == "ack"
    assert state.attributes["snoozed_until"] == state.attributes["pre_snoozed_until"]
    assert [event.data["entity_id"] for event in snoozed] == [LEFT_OPEN]


async def test_already_acknowledged_superseder_is_left_alone(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await _pair(setup_alerts, "snooze", snooze_duration={"minutes": 60})
    await _call(hass, "fire", OPEN)
    await _call(hass, "fire", LEFT_OPEN)
    await _call(hass, "ack", LEFT_OPEN)
    await _call(hass, "ack", OPEN)
    assert _attrs(hass, LEFT_OPEN)["snoozed_until"] is None


async def test_cancelled_by_unack_and_end(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The pre-acknowledgement lasts while the superseded alert is acknowledged."""
    await _pair(setup_alerts, "acknowledge")
    await _call(hass, "fire", OPEN)

    await _call(hass, "ack", OPEN)
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == [OPEN]
    await _call(hass, "unack", OPEN)
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []

    await _call(hass, "ack", OPEN)
    await _call(hass, "dismiss", OPEN)
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []

    # A snooze counts as acknowledging; its running out cancels it.
    await _call(hass, "fire", OPEN)
    await _call(hass, "snooze", OPEN, duration={"minutes": 5})
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == [OPEN]
    await _tick(hass, freezer, 6)
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []
    await _call(hass, "fire", LEFT_OPEN)
    assert hass.states.get(LEFT_OPEN).state == "active"


async def test_several_sources(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A plain pre-acknowledgement beats a pre-snooze; the latest deadline wins."""
    other = "alert_redux.workshop_window_open"
    await setup_alerts(
        alert_subentry("Workshop Door Open"),
        alert_subentry("Workshop Window Open"),
        alert_subentry(
            "Workshop Door Left Open",
            supersedes=[
                {
                    "alert": OPEN,
                    "propagation": "snooze",
                    "snooze_duration": {"minutes": 30},
                },
                {"alert": other, "propagation": "acknowledge"},
            ],
        ),
    )
    for entity_id in (OPEN, other):
        await _call(hass, "fire", entity_id)
    await _call(hass, "ack", OPEN)
    snooze_deadline = _attrs(hass, LEFT_OPEN)["pre_snoozed_until"]
    assert snooze_deadline is not None
    await _call(hass, "ack", other)
    attributes = _attrs(hass, LEFT_OPEN)
    assert attributes["pre_acked_by"] == [OPEN, other]
    assert attributes["pre_snoozed_until"] is None
    await _call(hass, "unack", other)
    assert _attrs(hass, LEFT_OPEN)["pre_snoozed_until"] == snooze_deadline


async def test_chains_through_a_pre_acknowledged_firing(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """A superseding alert that fires pre-acknowledged passes it on in turn."""
    await setup_alerts(
        alert_subentry("Workshop Door Open"),
        alert_subentry(
            "Workshop Door Left Open", supersedes=_supersedes(OPEN, "acknowledge")
        ),
        alert_subentry(
            "Workshop Door Open Overnight",
            supersedes=_supersedes(LEFT_OPEN, "acknowledge"),
        ),
    )
    await _call(hass, "fire", OPEN)
    await _call(hass, "ack", OPEN)
    # Not chained while Left Open isn't firing.
    assert _attrs(hass, OVERNIGHT)["pre_acked_by"] == []
    await _call(hass, "fire", LEFT_OPEN)
    assert hass.states.get(LEFT_OPEN).state == "ack"
    assert _attrs(hass, OVERNIGHT)["pre_acked_by"] == [LEFT_OPEN]
    await _call(hass, "fire", OVERNIGHT)
    assert hass.states.get(OVERNIGHT).state == "ack"


async def test_pre_acks_survive_a_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_storage: dict[str, Any]
) -> None:
    """Kept while the source is still acknowledged; swept if it isn't."""
    await _pair(setup_alerts, "acknowledge")
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    await _call(hass, "fire", OPEN)
    await _call(hass, "ack", OPEN)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == [OPEN]

    # Open's acknowledgement is gone from storage, as if it had ended while down.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    del hass.data[DOMAIN]["store"]
    alerts = hass_storage[STORAGE_KEY]["data"]["alerts"]
    (open_record,) = [
        record for record in alerts.values() if record["entity_id"] == OPEN
    ]
    open_record["runtime"] |= {"acked": False, "firing": False, "firing_since": None}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []


async def test_deleting_the_source_drops_its_pre_ack(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Propagation from an alert that's gone does nothing (spec §12.4)."""
    await setup_alerts(
        alert_subentry("Workshop Door Open", "open"),
        alert_subentry(
            "Workshop Door Left Open", supersedes=_supersedes(OPEN, "acknowledge")
        ),
    )
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    await _call(hass, "fire", OPEN)
    await _call(hass, "ack", OPEN)
    assert hass.config_entries.async_remove_subentry(entry, "open")
    await hass.async_block_till_done()
    assert _attrs(hass, LEFT_OPEN)["pre_acked_by"] == []
