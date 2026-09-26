"""Tests for the notifier module on its own (spec §9.1–§9.4, §15.2)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import replace
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
    MobileFeatures,
    Notification,
    Notifier,
    PersistentMember,
    QuietBehaviour,
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
PERSISTENT_DISMISS = "custom_components.alert_redux.notifier.members.persistent_notification.async_dismiss"
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
                "tag": "alert_redux_back_door_open",
            },
            "target": ["device"],
        }
    ]


async def test_persistent_member(hass: HomeAssistant, persistent: MagicMock) -> None:
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PersistentMember(),)))
    await _send(notifier, ["g"])
    persistent.assert_called_once_with(
        hass,
        "The back door is open.",
        "Back Door Open",
        notification_id="alert_redux_back_door_open",
    )


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
    persistent.assert_called_once_with(
        hass,
        "The back door is open.",
        "Back Door Open",
        notification_id="alert_redux_back_door_open",
    )
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


# Replacing and clearing (spec §9.10)

KEY = NOTIFICATION.key
DONE = Notification("Back Door Open", "Closed.", KEY, final=True)
PHONE = ActionMember("mobile_app_phone", target=("device",))


def _messages(calls: list[ServiceCall]) -> list[tuple[str, Any]]:
    return [(call.data["message"], call.data.get("data")) for call in calls]


def test_member_settings_from_dict() -> None:
    group = GroupConfig.from_dict(
        "g",
        "G",
        {
            "actions": [
                {"action": "notify.mobile_app_phone"},
                {"action": "notify.all_phones", "mobile": "no_buttons"},
                {
                    "action": "notify.mobile_app_tablet",
                    "mobile": "none",
                    "keep_on_ack": True,
                    "clear_when_ended": True,
                },
                {"action": "notify.telegram"},
            ],
            "persistent": True,
            "persistent_clear_on_ack": False,
            "persistent_clear_when_ended": True,
        },
    )
    phone, phones, tablet, telegram, persistent = group.members
    assert (phone.replaces, phone.shows_buttons) == (True, True)
    assert (phones.replaces, phones.shows_buttons) == (True, False)
    assert (tablet.replaces, tablet.shows_buttons) == (False, False)
    assert (tablet.clear_on_ack, tablet.clear_when_ended) == (False, True)
    assert (telegram.replaces, telegram.shows_buttons) == (False, False)
    assert ActionMember("telegram", mobile=MobileFeatures.ALL).shows_buttons
    assert persistent == PersistentMember(clear_on_ack=False, clear_when_ended=True)


async def test_mobile_replaced_and_cleared_when_acknowledged(
    hass: HomeAssistant,
) -> None:
    """Each notification carries the key as its tag; acknowledging clears it."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PHONE,)))
    await _send(notifier, ["g"])
    notifier.async_acknowledged(KEY)
    await hass.async_block_till_done()
    assert _messages(calls) == [
        ("The back door is open.", {"tag": KEY}),
        ("clear_notification", {"tag": KEY}),
    ]
    assert calls[1].data["target"] == ["device"]
    # Nothing is showing any more.
    notifier.async_acknowledged(KEY)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_keep_on_ack(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    member = ActionMember("mobile_app_phone", clear_on_ack=False)
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (member,)))
    await _send(notifier, ["g"])
    notifier.async_acknowledged(KEY)
    await hass.async_block_till_done()
    assert len(calls) == 1
    # Clearing it outright still reaches it.
    notifier.async_clear(KEY)
    await hass.async_block_till_done()
    assert _messages(calls)[-1] == ("clear_notification", {"tag": KEY})


async def test_final_notification_replaces_and_ends_the_record(
    hass: HomeAssistant,
) -> None:
    """The done notification stays on show; there's nothing left to clear."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PHONE,)))
    await _send(notifier, ["g"])
    notifier.async_send(["g"], DONE)
    await hass.async_block_till_done()
    notifier.async_acknowledged(KEY)
    notifier.async_clear(KEY)
    await hass.async_block_till_done()
    assert _messages(calls) == [
        ("The back door is open.", {"tag": KEY}),
        ("Closed.", {"tag": KEY}),
    ]


async def test_clear_when_ended(hass: HomeAssistant, persistent: MagicMock) -> None:
    """A member set to clear gets a clear instead of the final notification, and
    that doesn't count as undelivered."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    member = ActionMember("mobile_app_phone", clear_when_ended=True)
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (member,)))
    await _send(notifier, ["g"])
    notifier.async_send(["g"], DONE)
    await hass.async_block_till_done()
    assert _messages(calls) == [
        ("The back door is open.", {"tag": KEY}),
        ("clear_notification", {"tag": KEY}),
    ]
    persistent.assert_not_called()


async def test_persistent_replaced_and_dismissed(
    hass: HomeAssistant, persistent: MagicMock
) -> None:
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PersistentMember(),)))
    await _send(notifier, ["g"])
    assert persistent.call_args.kwargs == {"notification_id": KEY}
    with patch(PERSISTENT_DISMISS) as dismiss:
        notifier.async_acknowledged(KEY)
        await hass.async_block_till_done()
    dismiss.assert_called_once_with(hass, KEY)


async def test_entity_and_plain_action_members_not_cleared(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set("notify.kitchen", "unknown")
    entity = async_mock_service(hass, "notify", "send_message")
    telegram = async_mock_service(hass, "notify", "telegram")
    notifier = await _new_notifier(
        hass,
        GroupConfig("g", "G", (EntityMember("notify.kitchen"), ActionMember("telegram"))),
    )
    await _send(notifier, ["g"])
    notifier.async_clear(KEY)
    await hass.async_block_till_done()
    assert len(entity) == 1
    assert _messages(telegram) == [("The back door is open.", None)]


async def test_clearing_drops_a_waiting_retry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, persistent: MagicMock
) -> None:
    """A notification still waiting for its retry doesn't arrive after the
    acknowledgement, and isn't sent to the fallback either."""
    calls = _failing(hass, "mobile_app_phone", failures=1)
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PHONE,)))
    await _send(notifier, ["g"])
    notifier.async_acknowledged(KEY)
    await _tick(hass, freezer, 600)
    assert len(calls) == 1
    persistent.assert_not_called()


async def test_newer_notification_drops_a_waiting_retry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, persistent: MagicMock
) -> None:
    calls = _failing(hass, "mobile_app_phone", failures=1)
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PHONE,)))
    await _send(notifier, ["g"])
    notifier.async_send(["g"], DONE)
    await _tick(hass, freezer, 600)
    assert [message for message, _ in _messages(calls)] == [
        "The back door is open.",
        "Closed.",
    ]
    persistent.assert_not_called()


async def test_fallback_notification_cleared(hass: HomeAssistant) -> None:
    """Clearing reaches a notification that went to the fallback."""
    with patch(PERSISTENT_CREATE), patch(PERSISTENT_DISMISS) as dismiss:
        notifier = await _new_notifier(hass)
        notifier.async_send_fallback(NOTIFICATION)
        await hass.async_block_till_done()
        notifier.async_acknowledged(KEY)
        await hass.async_block_till_done()
    dismiss.assert_called_once_with(hass, KEY)


async def test_cleared_after_group_edit(hass: HomeAssistant) -> None:
    """Clearing goes to where the notification was shown, not the group now."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PHONE,)))
    await _send(notifier, ["g"])
    notifier.async_set_groups([GroupConfig("g", "G", (PersistentMember(),))])
    notifier.async_acknowledged(KEY)
    await hass.async_block_till_done()
    assert _messages(calls)[-1] == ("clear_notification", {"tag": KEY})


async def test_rekey(hass: HomeAssistant) -> None:
    """After a key changes, what's showing under the old tag is cleared by the
    next notification, or by clearing the new key."""
    new = "alert_redux_side_door_open"
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    notifier = await _new_notifier(hass, GroupConfig("g", "G", (PHONE,)))
    await _send(notifier, ["g"])
    notifier.async_rekey(KEY, new)
    notifier.async_clear(new)
    await hass.async_block_till_done()
    assert _messages(calls)[-1] == ("clear_notification", {"tag": KEY})

    await _send(notifier, ["g"])
    notifier.async_rekey(KEY, new)
    notifier.async_send(["g"], Notification("Side Door Open", "Open.", new))
    await hass.async_block_till_done()
    assert _messages(calls)[-2:] == [
        ("clear_notification", {"tag": KEY}),
        ("Open.", {"tag": new}),
    ]


async def test_live_records_survive_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    group = GroupConfig("g", "G", (PHONE,))
    notifier = await _new_notifier(hass, group)
    await _send(notifier, ["g"])
    await notifier.async_stop()
    assert list(hass_storage[STORE_KEY]["data"]["live"]) == [KEY]

    notifier = await _new_notifier(hass, group)
    notifier.async_acknowledged(KEY)
    await hass.async_block_till_done()
    assert _messages(calls)[-1] == ("clear_notification", {"tag": KEY})


async def test_old_store_format_loads(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """A retry queue saved by 0.8, before tags and member settings, still works."""
    hass_storage[STORE_KEY] = {
        "version": 1,
        "key": STORE_KEY,
        "data": {
            "deliveries": [
                {
                    "id": "d1",
                    "notification": {
                        "title": "Back Door Open",
                        "message": "The back door is open.",
                        "key": KEY,
                        "variables": {},
                    },
                    "deadline": "2099-01-01T00:00:00+00:00",
                    "is_fallback": False,
                    "delivered": False,
                    "attempts": [
                        {
                            "id": "a1",
                            "group_id": "g",
                            "group_name": "G",
                            "member": {
                                "kind": "action",
                                "action": "mobile_app_phone",
                                "data": None,
                                "target": [],
                            },
                            "tries": 1,
                            "next_try": None,
                        }
                    ],
                }
            ],
            "issues": {},
        },
    }
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await _new_notifier(hass, GroupConfig("g", "G", (ActionMember("mobile_app_phone"),)))
    await _tick(hass, freezer, 1)
    assert _messages(calls) == [("The back door is open.", {"tag": KEY})]


# Quiet hours (spec §9.9)

QUIET = "input_boolean.quiet"


async def _quiet_notifier(hass: HomeAssistant, *groups: GroupConfig) -> Notifier:
    notifier = await _new_notifier(hass, *groups)
    notifier.async_configure(
        fallback_group=None,
        retry_timeout=timedelta(minutes=5),
        quiet_entity=QUIET,
        quiet_threshold=2,
    )
    return notifier


def test_group_quiet_settings_from_dict() -> None:
    group = GroupConfig.from_dict(
        "g",
        "Speaker",
        {
            "loud": True,
            "actions": [{"action": "speaker", "quiet_data": {"volume": 0.2}}],
            "quiet_entity": "input_boolean.bedroom",
            "quiet_threshold": "critical",
            "quiet_behaviour": "soften",
        },
        {"critical": 3}.__getitem__,
    )
    assert (group.quiet_entity, group.quiet_threshold) == ("input_boolean.bedroom", 3)
    assert group.quiet_behaviour is QuietBehaviour.SOFTEN
    assert group.members == (ActionMember("speaker", quiet_data={"volume": 0.2}),)
    # Members that can soften don't hold.
    assert group.holding_members() == ()


async def test_held_never_goes_to_the_fallback(
    hass: HomeAssistant, persistent: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set(QUIET, "on")
    calls = async_mock_service(hass, "notify", "speaker")
    notifier = await _quiet_notifier(
        hass, GroupConfig("g", "G", (ActionMember("speaker"),), loud=True)
    )
    assert notifier.is_quiet("g")
    await _send(notifier, ["g"])
    await _tick(hass, freezer, 600)
    assert calls == []
    persistent.assert_not_called()


async def test_urgent_notifications_get_through(hass: HomeAssistant) -> None:
    hass.states.async_set(QUIET, "on")
    calls = async_mock_service(hass, "notify", "speaker")
    notifier = await _quiet_notifier(
        hass, GroupConfig("g", "G", (ActionMember("speaker"),), loud=True)
    )
    notifier.async_send(["g"], replace(NOTIFICATION, urgency=2))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_without_owner_the_latest_of_each_key_is_sent(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(QUIET, "on")
    calls = async_mock_service(hass, "notify", "speaker")
    notifier = await _quiet_notifier(
        hass, GroupConfig("g", "G", (ActionMember("speaker"),), loud=True)
    )
    await _send(notifier, ["g"])
    notifier.async_send(["g"], DONE)
    notifier.async_rekey(KEY, "alert_redux_side_door_open")
    hass.states.async_set(QUIET, "off")
    await hass.async_block_till_done()
    assert [(call.data["message"]) for call in calls] == ["Closed."]


async def test_folded_final_clears_what_was_shown(hass: HomeAssistant) -> None:
    """A key that ended while held, and gets nothing sent, has its earlier
    notification cleared from the members that held, as its final notification
    would have done."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    notifier = Notifier(
        hass,
        store_key=STORE_KEY,
        issue_domain=ISSUE_DOMAIN,
        on_quiet_ended=lambda _group_id, _held: [],
    )
    _RUNNING.append(notifier)
    await notifier.async_load()
    notifier.async_configure(
        fallback_group=None, retry_timeout=timedelta(minutes=5), quiet_entity=QUIET
    )
    notifier.async_set_groups([GroupConfig("g", "G", (PHONE,), loud=True)])
    notifier.async_start()
    await _send(notifier, ["g"])
    hass.states.async_set(QUIET, "on")
    notifier.async_send(["g"], DONE)
    await hass.async_block_till_done()
    assert len(calls) == 1
    hass.states.async_set(QUIET, "off")
    await hass.async_block_till_done()
    assert _messages(calls)[-1] == ("clear_notification", {"tag": KEY})


async def test_held_survive_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    hass.states.async_set(QUIET, "on")
    calls = async_mock_service(hass, "notify", "speaker")
    group = GroupConfig("g", "G", (ActionMember("speaker"),), loud=True)
    notifier = await _quiet_notifier(hass, group)
    await _send(notifier, ["g"])
    await notifier.async_stop()
    assert list(hass_storage[STORE_KEY]["data"]["held"]["g"]) == [KEY]

    hass.states.async_set(QUIET, "off")
    await _quiet_notifier(hass, group)
    await hass.async_block_till_done()
    assert len(calls) == 1
