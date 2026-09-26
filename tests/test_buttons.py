"""Tests for notification buttons and taps on them (spec §9.11)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    MockUser,
    async_mock_service,
)

from custom_components.alert_redux.buttons import (
    alert_buttons,
    custom_button_key,
    parse_action_id,
)
from custom_components.alert_redux.const import DOMAIN
from custom_components.alert_redux.notifier import (
    ActionMember,
    Button,
    GroupConfig,
    MobileFeatures,
    Notification,
    Notifier,
)
from custom_components.alert_redux.notifier.model import (
    notification_from_dict,
    notification_to_dict,
)

from .conftest import SetupAlerts, alert_subentry, group_subentry

DOOR = "alert_redux.garage_door_left_open"
UID = "01GARAGE"
CLOSE = {"label": "Close door", "action": [{"action": "test.close_door"}]}
MOBILE = group_subentry(
    "Phones", "phones", actions=[{"action": "notify.mobile_app_phone"}]
)
DEFAULTS = {"default_groups": ["phones"]}


def _garage(**data: Any) -> dict[str, Any]:
    return alert_subentry("Garage Door Left Open", subentry_id=UID, **data)


def _actions(call: ServiceCall) -> list[dict[str, Any]] | None:
    return call.data.get("data", {}).get("actions")


async def _tap(hass: HomeAssistant, action: str, user: MockUser) -> None:
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": action},
        context=Context(user_id=user.id),
    )
    await hass.async_block_till_done()


async def _call(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": DOOR}, blocking=True
    )
    await hass.async_block_till_done()


# Building buttons


def test_alert_buttons_order() -> None:
    """Custom buttons first, then Acknowledge and Snooze."""
    key = custom_button_key(CLOSE)
    assert alert_buttons(
        UID,
        [{**CLOSE, "require_unlock": True}],
        acknowledgeable=True,
        snooze=timedelta(hours=1),
    ) == (
        Button(f"ALERT_REDUX_{UID}_{key}", "Close door", True),
        Button(f"ALERT_REDUX_{UID}_ACK", "Acknowledge"),
        Button(f"ALERT_REDUX_{UID}_SNOOZE", "Snooze 1 hour"),
    )
    # No built-in buttons for unacknowledgeable alerts.
    assert alert_buttons(
        UID, [], acknowledgeable=False, snooze=timedelta(hours=1)
    ) == ()


def test_custom_button_key() -> None:
    """The key is stable, and changes when the button's label or action does."""
    key = custom_button_key(CLOSE)
    assert key.startswith("B")
    assert len(key) == 9
    assert custom_button_key(dict(CLOSE)) == key
    assert custom_button_key({**CLOSE, "label": "Shut door"}) != key
    assert custom_button_key({**CLOSE, "action": [{"action": "test.x"}]}) != key
    # Requiring unlock doesn't change what the button does.
    assert custom_button_key({**CLOSE, "require_unlock": True}) == key


def test_parse_action_id() -> None:
    assert parse_action_id(f"ALERT_REDUX_{UID}_ACK") == (UID, "ACK")
    assert parse_action_id("ALERT_REDUX_ACK") is None
    assert parse_action_id("SOMETHING_ELSE") is None
    assert parse_action_id(None) is None


def test_buttons_stored_with_notification() -> None:
    """A notification waiting in the retry queue keeps its buttons."""
    notification = Notification(
        "T", "M", "k", buttons=(Button("A", "One", True), Button("B", "Two"))
    )
    assert notification_from_dict(notification_to_dict(notification)) == notification


# Sending buttons


async def test_buttons_as_mobile_actions(hass: HomeAssistant) -> None:
    """Mobile members get up to three buttons as actions; others get none."""
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    telegram = async_mock_service(hass, "notify", "telegram")
    phones = async_mock_service(hass, "notify", "all_phones")
    notifier = Notifier(hass, store_key="test.notifier", issue_domain="test")
    await notifier.async_load()
    notifier.async_set_groups(
        [
            GroupConfig(
                "g",
                "G",
                (
                    ActionMember("mobile_app_phone"),
                    ActionMember("telegram"),
                    ActionMember("all_phones", mobile=MobileFeatures.NO_BUTTONS),
                ),
            )
        ]
    )
    notifier.async_start()
    buttons = (
        Button("A", "One", require_unlock=True),
        Button("B", "Two"),
        Button("C", "Three"),
        Button("D", "Four"),
    )
    notifier.async_send(["g"], Notification("T", "M", "k", buttons=buttons))
    notifier.async_send(["g"], Notification("T", "Done", "k", buttons=buttons, final=True))
    await hass.async_block_till_done()
    await notifier.async_stop()
    assert _actions(phone[0]) == [
        {"action": "A", "title": "One", "authenticationRequired": True},
        {"action": "B", "title": "Two"},
        {"action": "C", "title": "Three"},
    ]
    assert _actions(phone[1]) is None  # final: no buttons
    assert "data" not in telegram[0].data
    assert phones[0].data["data"] == {"tag": "k"}


async def test_alert_notifications_carry_buttons(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """On and reminder notifications have the buttons; done doesn't."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        _garage(buttons=[CLOSE], button_snooze_duration={"minutes": 30}),
        MOBILE,
        options=DEFAULTS,
    )
    assert hass.states.get(DOOR).attributes["buttons"] == ["Close door"]
    await _call(hass, "fire")
    await _call(hass, "dismiss")
    assert [action["title"] for action in _actions(calls[0])] == [
        "Close door",
        "Acknowledge",
        "Snooze 30 minutes",
    ]
    assert _actions(calls[1]) is None


async def test_snooze_duration_default_option(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        _garage(),
        MOBILE,
        options={**DEFAULTS, "button_snooze_duration": {"hours": 2}},
    )
    await _call(hass, "fire")
    assert [action["title"] for action in _actions(calls[0])] == [
        "Acknowledge",
        "Snooze 2 hours",
    ]


async def test_unacknowledgeable_has_no_built_in_buttons(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(_garage(acknowledgeable=False), MOBILE, options=DEFAULTS)
    await _call(hass, "fire")
    assert _actions(calls[0]) is None


# Taps


async def test_tap_acknowledge(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: MockUser
) -> None:
    """Acknowledge acknowledges as the user who tapped, and clears the
    notification."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(_garage(), MOBILE, options=DEFAULTS)
    await _call(hass, "fire")
    await _tap(hass, f"ALERT_REDUX_{UID}_ACK", hass_admin_user)
    state = hass.states.get(DOOR)
    assert state.state == "ack"
    assert state.attributes["last_acked_by"] == hass_admin_user.id
    assert calls[-1].data["message"] == "clear_notification"


async def test_tap_snooze(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: MockUser
) -> None:
    async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(
        _garage(button_snooze_duration={"minutes": 30}), MOBILE, options=DEFAULTS
    )
    await _call(hass, "fire")
    await _tap(hass, f"ALERT_REDUX_{UID}_SNOOZE", hass_admin_user)
    state = hass.states.get(DOOR)
    assert state.state == "ack"
    assert state.attributes["last_snoozed_by"] == hass_admin_user.id
    snoozed = state.attributes["snoozed_until"] - state.attributes["last_snoozed"]
    assert snoozed == timedelta(minutes=30)


async def test_tap_custom_runs_only_its_action(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: MockUser
) -> None:
    """A custom button runs its action, as the user who tapped, even after the
    alert has ended; Acknowledge then does nothing."""
    closes = async_mock_service(hass, "test", "close_door")
    await setup_alerts(_garage(buttons=[CLOSE]), MOBILE, options={})
    await _tap(hass, f"ALERT_REDUX_{UID}_{custom_button_key(CLOSE)}", hass_admin_user)
    assert len(closes) == 1
    assert closes[0].context.user_id == hass_admin_user.id
    await _tap(hass, f"ALERT_REDUX_{UID}_ACK", hass_admin_user)
    assert hass.states.get(DOOR).state == "idle"


async def test_stale_and_unknown_taps_ignored(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: MockUser
) -> None:
    """An edited button's old ID, another alert's, or someone else's does
    nothing."""
    closes = async_mock_service(hass, "test", "close_door")
    old = {**CLOSE, "label": "Shut door"}
    await setup_alerts(_garage(buttons=[CLOSE]), MOBILE, options={})
    await _call(hass, "fire")
    for action in (
        f"ALERT_REDUX_{UID}_{custom_button_key(old)}",
        f"ALERT_REDUX_01GONE_{custom_button_key(CLOSE)}",
        "ALERT_REDUX_01GONE_ACK",
        "OTHER_ACTION",
    ):
        await _tap(hass, action, hass_admin_user)
    assert not closes
    assert hass.states.get(DOOR).state == "active"


async def test_tap_on_unacknowledgeable_ignored(
    hass: HomeAssistant, setup_alerts: SetupAlerts, hass_admin_user: MockUser
) -> None:
    await setup_alerts(_garage(acknowledgeable=False), options={})
    await _call(hass, "fire")
    await _tap(hass, f"ALERT_REDUX_{UID}_ACK", hass_admin_user)
    assert hass.states.get(DOOR).state == "active"
