"""Tests for the notifier module on its own (spec §9.1–§9.3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.alert_redux.notifier import (
    ActionMember,
    EntityMember,
    GroupConfig,
    Notification,
    Notifier,
    PersistentMember,
)
from custom_components.alert_redux.notifier.model import parse_target

NOTIFICATION = Notification(
    title="Back Door Open",
    message="The back door is open.",
    key="alert_redux_back_door_open",
    variables={"name": "Back Door Open", "priority": "critical"},
)
PERSISTENT_CREATE = "custom_components.alert_redux.notifier.members.persistent_notification.async_create"


async def _send(
    hass: HomeAssistant, groups: list[GroupConfig], group_ids: list[str]
) -> None:
    notifier = Notifier(hass)
    notifier.async_set_groups(groups)
    notifier.async_send(group_ids, NOTIFICATION)
    await hass.async_block_till_done()


def test_group_from_dict() -> None:
    group = GroupConfig.from_dict(
        "g1",
        "Phones",
        {
            "loud": True,
            "entities": ["notify.kitchen"],
            "actions": [
                {"action": "notify.mobile_app_phone", "data": {"channel": "alarm"}},
                {"action": "telegram", "target": "123, 456"},
            ],
            "persistent": True,
        },
    )
    assert group.loud
    assert group.members == (
        EntityMember("notify.kitchen"),
        ActionMember("mobile_app_phone", {"channel": "alarm"}),
        ActionMember("telegram", target=("123", "456")),
        PersistentMember(),
    )


def test_parse_target() -> None:
    assert parse_target(None) == ()
    assert parse_target("") == ()
    assert parse_target("a, b ,") == ("a", "b")
    assert parse_target(["a", 1]) == ("a", "1")


async def test_entity_member(hass: HomeAssistant) -> None:
    """A notify entity gets the message and title through notify.send_message."""
    hass.states.async_set("notify.kitchen", "unknown")
    calls = async_mock_service(hass, "notify", "send_message")
    await _send(hass, [GroupConfig("g", "G", (EntityMember("notify.kitchen"),))], ["g"])
    assert [call.data for call in calls] == [
        {
            "entity_id": "notify.kitchen",
            "message": "The back door is open.",
            "title": "Back Door Open",
        }
    ]


async def test_action_member_renders_data(hass: HomeAssistant) -> None:
    """A legacy action gets data, with templates rendered from the variables."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    member = ActionMember(
        "mobile_app_phone",
        {"channel": "alarm", "group": "{{ priority }}", "tags": ["{{ name }}"]},
        ("device",),
    )
    await _send(hass, [GroupConfig("g", "G", (member,))], ["g"])
    assert [call.data for call in calls] == [
        {
            "message": "The back door is open.",
            "title": "Back Door Open",
            "data": {
                "channel": "alarm",
                "group": "critical",
                "tags": ["Back Door Open"],
            },
            "target": ["device"],
        }
    ]


async def test_persistent_member(hass: HomeAssistant) -> None:
    with patch(PERSISTENT_CREATE) as create:
        await _send(hass, [GroupConfig("g", "G", (PersistentMember(),))], ["g"])
    create.assert_called_once_with(hass, "The back door is open.", "Back Door Open")


async def test_member_in_two_groups_notified_once(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    member = ActionMember("phone")
    await _send(
        hass,
        [GroupConfig("a", "A", (member,)), GroupConfig("b", "B", (member,))],
        ["a", "b"],
    )
    assert len(calls) == 1


async def test_unknown_group_skipped(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    await _send(hass, [GroupConfig("a", "A", (ActionMember("phone"),))], ["x", "a"])
    assert len(calls) == 1
    assert "notifier group x doesn't exist" in caplog.text


async def test_missing_and_failing_members_dont_stop_others(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A missing or failing member is logged; the others are still notified."""
    calls = async_mock_service(hass, "notify", "phone")

    async def broken(call: ServiceCall) -> None:
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", "broken", broken)
    await _send(
        hass,
        [
            GroupConfig(
                "g",
                "G",
                (
                    ActionMember("missing"),
                    EntityMember("notify.gone"),
                    ActionMember("broken"),
                    ActionMember("phone"),
                ),
            )
        ],
        ["g"],
    )
    assert len(calls) == 1
    assert "couldn't notify notify.missing" in caplog.text
    assert "couldn't notify notify.gone" in caplog.text
    assert "notifying notify.broken in group G failed" in caplog.text


async def test_fallback_is_persistent(hass: HomeAssistant) -> None:
    notifier = Notifier(hass)
    with patch(PERSISTENT_CREATE) as create:
        notifier.async_send_fallback(NOTIFICATION)
        await hass.async_block_till_done()
    create.assert_called_once()


async def test_member_with_data_is_deduplicated_without_hashing(
    hass: HomeAssistant,
) -> None:
    """Members holding data aren't hashable; comparing them must still work."""
    calls = async_mock_service(hass, "notify", "phone")
    member = ActionMember("phone", {"channel": "alarm"})
    await _send(
        hass,
        [GroupConfig("a", "A", (member,)), GroupConfig("b", "B", (member,))],
        ["a", "b"],
    )
    assert len(calls) == 1
