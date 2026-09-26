"""Tests for the logbook descriptions (spec §11.4)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.alert_redux.const import (
    DOMAIN,
    EVENT_ACKED,
    EVENT_CREATED,
    EVENT_DATA_RESTORED,
    EVENT_DELETED,
    EVENT_DISABLED,
    EVENT_ENABLED,
    EVENT_ENDED,
    EVENT_FIRED,
    EVENT_NO_DATA,
    EVENT_SNOOZE_EXPIRED,
    EVENT_SNOOZED,
    EVENT_SUPERSEDED,
    EVENT_UNACKED,
)
from custom_components.alert_redux.logbook import async_describe_events

from .conftest import SetupAlerts, alert_subentry

DOOR = "alert_redux.back_door_open"
COMMON = {"entity_id": DOOR, "name": "Back Door Open"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_db_url, enable_custom_integrations):
    """Prepare the recorder's database before hass, which it must precede."""
    yield


@pytest.fixture
def describers(hass: HomeAssistant) -> dict[str, Callable[..., dict[str, Any]]]:
    found: dict[str, Callable[..., dict[str, Any]]] = {}

    def _describe(domain: str, event_type: str, describe) -> None:
        assert domain == DOMAIN
        found[event_type] = describe

    async_describe_events(hass, _describe)
    return found


def _message(describers, event_type: str, **data: Any) -> str:
    row = describers[event_type](SimpleNamespace(data={**COMMON, **data}))
    assert row["name"] == "Back Door Open"
    assert row["entity_id"] == DOOR
    return row["message"]


def test_only_events_that_add_to_state_rows(describers) -> None:
    """Changes the state rows already show get no rows of their own."""
    assert set(describers) == {
        EVENT_SNOOZED,
        EVENT_SNOOZE_EXPIRED,
        EVENT_DISABLED,
        EVENT_SUPERSEDED,
        EVENT_NO_DATA,
        EVENT_DATA_RESTORED,
        EVENT_CREATED,
        EVENT_DELETED,
    }
    for event_type in (
        EVENT_FIRED,
        EVENT_ACKED,
        EVENT_UNACKED,
        EVENT_ENABLED,
        EVENT_ENDED,
    ):
        assert event_type not in describers


async def test_messages(hass: HomeAssistant, describers) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    today = dt_util.now().replace(hour=14, minute=30, second=0, microsecond=0)
    later = datetime(2030, 3, 5, 18, 0, tzinfo=dt_util.get_default_time_zone())
    assert (
        _message(describers, EVENT_SNOOZED, snoozed_until=dt_util.as_utc(today))
        == "snoozed until 14:30"
    )
    # Read back from the database, times are strings.
    assert (
        _message(describers, EVENT_SNOOZED, snoozed_until=later.isoformat())
        == "snoozed until Tue 05 Mar 18:00"
    )
    assert _message(describers, EVENT_SNOOZE_EXPIRED) == "snooze ran out"
    assert _message(describers, EVENT_DISABLED, disabled_until=None) == "disabled"
    assert (
        _message(describers, EVENT_DISABLED, disabled_until=later)
        == "suspended until Tue 05 Mar 18:00"
    )
    hass.states.async_set(
        "alert_redux.door_left_open", "active", {"friendly_name": "Door Left Open"}
    )
    assert (
        _message(
            describers,
            EVENT_SUPERSEDED,
            superseded_by=["alert_redux.door_left_open", "alert_redux.gone"],
        )
        == "superseded by Door Left Open, alert_redux.gone"
    )
    assert (
        _message(describers, EVENT_NO_DATA, missing_inputs=["sensor.a", "sensor.b"])
        == "lost data from sensor.a, sensor.b"
    )
    assert _message(describers, EVENT_DATA_RESTORED) == "data restored"
    assert _message(describers, EVENT_CREATED) == "created"
    assert _message(describers, EVENT_DELETED) == "deleted"


async def test_activity_rows(
    recorder_mock,
    hass: HomeAssistant,
    setup_alerts: SetupAlerts,
    hass_ws_client,
    hass_admin_user,
) -> None:
    """An acknowledgement makes one row; a snooze adds its own row."""
    # The frontend (a logbook dependency) isn't installed for tests.
    hass.config.components.add("frontend")
    assert await async_setup_component(hass, "logbook", {})
    start = dt_util.utcnow() - timedelta(seconds=1)
    await setup_alerts(alert_subentry("Back Door Open"))
    for service, data in (
        ("fire", {}),
        ("ack", {}),
        ("unack", {}),
        ("snooze", {"duration": {"minutes": 30}}),
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"entity_id": DOOR, **data},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "logbook/get_events",
            "start_time": start.isoformat(),
            "entity_ids": [DOOR],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    rows = [
        (row.get("state") or row.get("message"), row.get("context_user_id"))
        for row in response["result"]
        if row.get("entity_id") == DOOR
    ]
    assert [message for message, _ in rows[:5]] == [
        "created",
        "active",
        "ack",
        "active",
        "ack",
    ]
    assert rows[5][0].startswith("snoozed until ")
    assert len(rows) == 6
    # The user shows on state rows and on described rows alike.
    assert [user for _, user in rows] == [None, *[hass_admin_user.id] * 5]
