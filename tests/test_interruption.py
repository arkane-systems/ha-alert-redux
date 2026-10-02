"""Tests for iOS interruption levels on mobile notifications (spec §9.3)."""

from __future__ import annotations

from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.notifier import (
    ActionMember,
    MobileFeatures,
    Notification,
)
from custom_components.alert_redux.notifier.model import (
    notification_from_dict,
    notification_to_dict,
)

from .conftest import SetupAlerts, alert_subentry, group_subentry

DOOR = "alert_redux.back_door_open"
PHONES = group_subentry(
    "Phones",
    "phones",
    actions=[
        {"action": "notify.mobile_app_phone"},
        {"action": "notify.telegram"},
        {"action": "notify.mobile_app_old", "mobile": "none"},
    ],
)
DEFAULTS = {"default_groups": ["phones"]}


def _level(call: ServiceCall) -> str | None:
    return call.data.get("data", {}).get("push", {}).get("interruption-level")


async def _fire_and_end(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.services.async_call(
        "alert_redux", "fire", {"entity_id": DOOR}, blocking=True
    )
    await hass.async_block_till_done()
    freezer.tick(11 * 60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "alert_redux", "dismiss", {"entity_id": DOOR}, blocking=True
    )
    await hass.async_block_till_done()


async def test_priority_sets_the_level(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Emergency is critical and Critical is time-sensitive, on the on and reminder
    notifications of mobile members; the done notification has none."""
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    telegram = async_mock_service(hass, "notify", "telegram")
    old = async_mock_service(hass, "notify", "mobile_app_old")
    await setup_alerts(
        alert_subentry("Back Door Open", priority="emergency"),
        PHONES,
        options=DEFAULTS,
    )

    await _fire_and_end(hass, freezer)

    # On, reminder (after 10 minutes), and done.
    assert [_level(call) for call in phone] == ["critical", "critical", None]
    # Not a mobile app, or told not to be: no push key at all.
    assert all("push" not in call.data.get("data", {}) for call in telegram)
    assert all("push" not in call.data.get("data", {}) for call in old)


async def test_critical_is_time_sensitive_and_lower_priorities_are_not_set(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    async_mock_service(hass, "notify", "telegram")
    async_mock_service(hass, "notify", "mobile_app_old")
    await setup_alerts(
        alert_subentry("Back Door Open", priority="critical"),
        alert_subentry("Side Door Open", priority="warning"),
        PHONES,
        options=DEFAULTS,
    )
    for entity_id in (DOOR, "alert_redux.side_door_open"):
        await hass.services.async_call(
            "alert_redux", "fire", {"entity_id": entity_id}, blocking=True
        )
    await hass.async_block_till_done()
    assert sorted((call.data["title"], _level(call)) for call in phone) == [
        ("Back Door Open", "time-sensitive"),
        ("Side Door Open", None),
    ]


async def test_the_members_own_level_wins_and_push_keys_merge(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    pinned = async_mock_service(hass, "notify", "mobile_app_pinned")
    merged = async_mock_service(hass, "notify", "mobile_app_merged")
    await setup_alerts(
        alert_subentry("Back Door Open", priority="emergency"),
        group_subentry(
            "Phones",
            "phones",
            actions=[
                {
                    "action": "notify.mobile_app_pinned",
                    "data": {"push": {"interruption-level": "active", "badge": 1}},
                },
                {
                    "action": "notify.mobile_app_merged",
                    "data": {"push": {"badge": 2}},
                },
            ],
        ),
        options=DEFAULTS,
    )
    await hass.services.async_call(
        "alert_redux", "fire", {"entity_id": DOOR}, blocking=True
    )
    await hass.async_block_till_done()
    assert pinned[0].data["data"]["push"] == {
        "interruption-level": "active",
        "badge": 1,
    }
    assert merged[0].data["data"]["push"] == {
        "interruption-level": "critical",
        "badge": 2,
    }


async def test_a_softened_delivery_never_escalates(hass: HomeAssistant) -> None:
    """Quiet hours soften with the member's quiet data; the level isn't added."""
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    from custom_components.alert_redux.notifier.members import async_deliver

    member = ActionMember(
        "mobile_app_phone", quiet_data={"push": {"interruption-level": "passive"}}
    )
    notification = Notification("T", "M", "k", interruption="critical")
    await async_deliver(hass, member, notification, "k", soft=True)
    await async_deliver(hass, member, notification, "k", soft=False)
    assert [_level(call) for call in phone] == ["passive", "critical"]


def test_the_level_survives_storage() -> None:
    """A retried or held notification keeps its level."""
    notification = Notification("T", "M", "k", urgency=4, interruption="time-sensitive")
    stored: dict[str, Any] = notification_to_dict(notification)
    assert notification_from_dict(stored) == notification
    # Older records have none.
    del stored["interruption"]
    assert notification_from_dict(stored).interruption is None


def test_mobile_app_detection() -> None:
    assert ActionMember("mobile_app_phone").mobile_app
    assert not ActionMember("telegram").mobile_app
    assert ActionMember("all_phones", mobile=MobileFeatures.NO_BUTTONS).mobile_app
    assert not ActionMember("mobile_app_phone", mobile=MobileFeatures.NONE).mobile_app
