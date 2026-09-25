"""Tests for the notifier module on its own (spec §9.1–§9.4, §15.2)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.notifier import (
    ActionMember,
    EntityMember,
    GroupConfig,
    Notification,
    Notifier,
    PersistentMember,
)
from custom_components.alert_redux.notifier.model import parse_target
from custom_components.alert_redux.notifier.retry import backoff

NOTIFICATION = Notification(
    title="Back Door Open",
    message="The back door is open.",
    key="alert_redux_back_door_open",
    variables={"name": "Back Door Open", "priority": "critical"},
)
PERSISTENT_CREATE = "custom_components.alert_redux.notifier.members.persistent_notification.async_create"
STORE_KEY = "test.notifier"
ISSUE_DOMAIN = "test"


_RUNNING: list[Notifier] = []


@pytest.fixture(autouse=True)
async def stop_notifiers() -> AsyncGenerator[None]:
    """Stop the notifiers a test started, so that no timers linger."""
    yield
    while _RUNNING:
        await _RUNNING.pop().async_stop()


async def _new_notifier(hass: HomeAssistant, *groups: GroupConfig) -> Notifier:
    notifier = Notifier(hass, store_key=STORE_KEY, issue_domain=ISSUE_DOMAIN)
    _RUNNING.append(notifier)
    await notifier.async_load()
    notifier.async_configure(fallback_group=None, retry_timeout=timedelta(minutes=5))
    notifier.async_set_groups(groups)
    notifier.async_start()
    return notifier


@pytest.fixture
async def persistent() -> AsyncGenerator[MagicMock]:
    """Capture persistent notifications, which are the built-in fallback."""
    with patch(PERSISTENT_CREATE) as create:
        yield create


async def _send(notifier: Notifier, group_ids: list[str]) -> None:
    notifier.async_send(group_ids, NOTIFICATION)
    await notifier.hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Advance time a second at a time, so that timers fire when they're due."""
    for _ in range(int(seconds)):
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


def _failing(hass: HomeAssistant, service: str, failures: int) -> list[ServiceCall]:
    """Register a notify action that fails the given number of times first."""
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) <= failures:
            raise HomeAssistantError("boom")

    hass.services.async_register("notify", service, handler)
    return calls


# Groups and members


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


def test_backoff() -> None:
    assert [backoff(tries).total_seconds() for tries in range(1, 8)] == [
        5,
        10,
        20,
        40,
        60,
        60,
        60,
    ]


async def test_entity_member(hass: HomeAssistant) -> None:
    """A notify entity gets the message and title through notify.send_message."""
    hass.states.async_set("notify.kitchen", "unknown")
    calls = async_mock_service(hass, "notify", "send_message")
    notifier = await _new_notifier(
        hass, GroupConfig("g", "G", (EntityMember("notify.kitchen"),))
    )
    await _send(notifier, ["g"])
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
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (member,)))
    await _send(notifier, ["g"])
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


async def test_persistent_member(hass: HomeAssistant, persistent: MagicMock) -> None:
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PersistentMember(),)))
    await _send(notifier, ["g"])
    persistent.assert_called_once_with(hass, "The back door is open.", "Back Door Open")


async def test_member_in_two_groups_notified_once(hass: HomeAssistant) -> None:
    """Members are compared, not hashed: ones holding data aren't hashable."""
    calls = async_mock_service(hass, "notify", "phone")
    member = ActionMember("phone", {"channel": "alarm"})
    notifier = await _new_notifier(
        hass, GroupConfig("a", "A", (member,)), GroupConfig("b", "B", (member,))
    )
    await _send(notifier, ["a", "b"])
    assert len(calls) == 1


async def test_unknown_group_skipped(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    notifier = await _new_notifier(
        hass, GroupConfig("a", "A", (ActionMember("phone"),))
    )
    await _send(notifier, ["x", "a"])
    assert len(calls) == 1
    assert "notifier group x doesn't exist" in caplog.text


# Retrying (spec §15.2)


async def test_failing_member_retried_with_backoff(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, persistent: MagicMock
) -> None:
    calls = _failing(hass, "phone", failures=2)
    notifier = await _new_notifier(
        hass, GroupConfig("g", "G", (ActionMember("phone"),))
    )
    await _send(notifier, ["g"])
    assert len(calls) == 1
    await _tick(hass, freezer, 4)
    assert len(calls) == 1
    await _tick(hass, freezer, 1)  # 5 s after the first try
    assert len(calls) == 2
    await _tick(hass, freezer, 10)  # then 10 s
    assert len(calls) == 3
    await _tick(hass, freezer, 600)
    assert len(calls) == 3  # delivered; no more tries, no fallback
    persistent.assert_not_called()


async def test_members_retried_independently(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, persistent: MagicMock
) -> None:
    """One broken member doesn't hold up the others, and partial success counts
    as delivered: no fallback."""
    good = async_mock_service(hass, "notify", "phone")
    notifier = await _new_notifier(
        hass, GroupConfig("g", "G", (ActionMember("missing"), ActionMember("phone")))
    )
    await _send(notifier, ["g"])
    assert len(good) == 1
    await _tick(hass, freezer, 600)
    assert len(good) == 1
    persistent.assert_not_called()


async def test_action_appearing_is_retried_at_once(
    hass: HomeAssistant, persistent: MagicMock
) -> None:
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (ActionMember("late"),)))
    await _send(notifier, ["g"])
    calls = async_mock_service(hass, "notify", "late")
    await hass.async_block_till_done()
    assert len(calls) == 1
    persistent.assert_not_called()


async def test_all_failing_goes_to_fallback(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    persistent: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When every member has failed for the retry timeout, the fallback gets it."""
    calls = _failing(hass, "broken", failures=100)
    notifier = await _new_notifier(
        hass,
        GroupConfig("g", "G", (ActionMember("broken"), EntityMember("notify.gone"))),
    )
    await _send(notifier, ["g"])
    await _tick(hass, freezer, 60)
    persistent.assert_not_called()
    for _ in range(5):
        await _tick(hass, freezer, 60)
    persistent.assert_called_once_with(hass, "The back door is open.", "Back Door Open")
    assert len(calls) == 9  # at 0, 5, 15, 35, 75, 135, 195, 255 s, and 300 s
    assert "gave up notifying notify.broken in group G after" in caplog.text
    assert "no one could be notified; sending to the fallback" in caplog.text


async def test_unknown_groups_only_go_to_fallback(
    hass: HomeAssistant, persistent: MagicMock
) -> None:
    notifier = await _new_notifier(hass)
    await _send(notifier, ["gone"])
    persistent.assert_called_once()


async def test_configured_fallback_group(hass: HomeAssistant) -> None:
    pager = async_mock_service(hass, "notify", "pager")
    notifier = await _new_notifier(
        hass, GroupConfig("p", "Pagers", (ActionMember("pager"),))
    )
    notifier.async_configure(fallback_group="p", retry_timeout=timedelta(minutes=5))
    assert notifier.fallback_group.name == "Pagers"
    notifier.async_send_fallback(NOTIFICATION)
    await hass.async_block_till_done()
    assert len(pager) == 1
    # A fallback group that no longer exists means the built-in one.
    notifier.async_set_groups([])
    assert notifier.fallback_group.name == "Fallback"


async def test_failing_fallback_is_only_logged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = _failing(hass, "pager", failures=100)
    notifier = await _new_notifier(
        hass, GroupConfig("p", "Pagers", (ActionMember("pager"),))
    )
    notifier.async_configure(fallback_group="p", retry_timeout=timedelta(seconds=30))
    await _send(notifier, ["gone"])
    for _ in range(10):
        await _tick(hass, freezer, 30)
    assert "the fallback couldn't be notified either" in caplog.text
    assert len(calls) == 4  # at 0, 5, 15, and 30 s: no fallback of the fallback


async def test_queue_survives_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    persistent: MagicMock,
) -> None:
    group = GroupConfig("g", "G", (ActionMember("late"),))
    notifier = await _new_notifier(hass, group)
    await _send(notifier, ["g"])
    await notifier.async_stop()
    assert len(hass_storage[STORE_KEY]["data"]["deliveries"]) == 1

    await _tick(hass, freezer, 60)
    calls = async_mock_service(hass, "notify", "late")
    await _new_notifier(hass, group)
    await _tick(hass, freezer, 1)
    assert len(calls) == 1
    assert calls[0].data["message"] == "The back door is open."
    persistent.assert_not_called()


async def test_queue_expired_while_down_goes_to_fallback(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, persistent: MagicMock
) -> None:
    group = GroupConfig("g", "G", (ActionMember("late"),))
    notifier = await _new_notifier(hass, group)
    await _send(notifier, ["g"])
    await notifier.async_stop()

    freezer.tick(timedelta(minutes=10))
    await _new_notifier(hass, group)
    await hass.async_block_till_done()
    persistent.assert_called_once()


# Missing legacy actions (spec §9.2)


async def test_missing_action_issue_raised_and_cleared(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, persistent: MagicMock
) -> None:
    """Giving up on a missing action raises an issue; it clears when the action
    is registered."""
    registry = ir.async_get(hass)
    notifier = await _new_notifier(
        hass, GroupConfig("g", "Phones", (ActionMember("old_phone"),))
    )
    await _send(notifier, ["g"])
    for _ in range(6):
        await _tick(hass, freezer, 60)
    issue = registry.async_get_issue(ISSUE_DOMAIN, "notify_action_missing_g_old_phone")
    assert issue is not None
    assert issue.translation_placeholders == {
        "group": "Phones",
        "action": "notify.old_phone",
    }

    async_mock_service(hass, "notify", "old_phone")
    await hass.async_block_till_done()
    assert (
        registry.async_get_issue(ISSUE_DOMAIN, "notify_action_missing_g_old_phone")
        is None
    )


async def test_missing_actions_checked_after_startup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Once integrations have had the retry timeout to set up, every missing
    action is raised; removing it from its group clears the issue."""
    registry = ir.async_get(hass)
    ident = "notify_action_missing_g_old_phone"
    notifier = await _new_notifier(
        hass, GroupConfig("g", "Phones", (ActionMember("old_phone"),))
    )
    await _tick(hass, freezer, 60)
    assert registry.async_get_issue(ISSUE_DOMAIN, ident) is None
    await _tick(hass, freezer, 240)
    assert registry.async_get_issue(ISSUE_DOMAIN, ident) is not None

    notifier.async_set_groups([GroupConfig("g", "Phones", (PersistentMember(),))])
    assert registry.async_get_issue(ISSUE_DOMAIN, ident) is None
    # From then on, a group change raises a missing action at once.
    notifier.async_set_groups(
        [GroupConfig("g", "Phones", (ActionMember("old_phone"),))]
    )
    assert registry.async_get_issue(ISSUE_DOMAIN, ident) is not None


async def test_no_issue_for_member_removed_while_retrying(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, persistent: MagicMock
) -> None:
    """A notification still retrying a member that its group has since lost gives
    up without raising an issue for it."""
    registry = ir.async_get(hass)
    notifier = await _new_notifier(
        hass, GroupConfig("g", "Phones", (ActionMember("old_phone"),))
    )
    await _send(notifier, ["g"])
    notifier.async_set_groups([])
    await _tick(hass, freezer, 360)
    persistent.assert_called_once()
    assert (
        registry.async_get_issue(ISSUE_DOMAIN, "notify_action_missing_g_old_phone")
        is None
    )
