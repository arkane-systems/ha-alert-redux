"""Tests for alerts' on, reminder, and done notifications (spec §9.4–§9.7)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alert_redux.const import DOMAIN, ISSUE_DEFAULT_GROUPS_UNSET

from .conftest import SetupAlerts, alert_subentry, group_subentry, state_alert

DOOR = "alert_redux.back_door_open"
PHONE = group_subentry(
    "Phones",
    "phones",
    actions=[{"action": "notify.phone", "data": {"x": "{{ reason }}"}}],
)
DEFAULTS = {"default_groups": ["phones"]}
PERSISTENT_CREATE = "custom_components.alert_redux.notifier.members.persistent_notification.async_create"


async def _call(hass: HomeAssistant, service: str, **data: Any) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": DOOR, **data}, blocking=True
    )
    await hass.async_block_till_done()


def _sent(calls: list[ServiceCall]) -> list[tuple[str, str]]:
    return [(call.data["title"], call.data["message"]) for call in calls]


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_manual_on_and_done(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Firing sends the on message; dismissing sends the done message."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(alert_subentry("Back Door Open"), PHONE, options=DEFAULTS)

    await _call(hass, "fire")
    assert _sent(calls) == [("Back Door Open", "Back Door Open is firing.")]
    assert calls[0].data["data"] == {"x": "on"}

    freezer.tick(timedelta(minutes=5))
    await _call(hass, "dismiss")
    assert _sent(calls)[1] == (
        "Back Door Open",
        "Back Door Open stopped firing after 5 minutes.",
    )
    assert calls[1].data["data"] == {"x": "done"}


async def test_fire_again_notifies_only_while_active(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Firing again resends the on message, unless acknowledged (spec §4.2)."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open", message="Fired {{ fire_count }}x"),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    await _call(hass, "fire")
    assert [message for _, message in _sent(calls)] == ["Fired 1x", "Fired 2x"]

    await _call(hass, "ack")
    await _call(hass, "fire")
    assert len(calls) == 2


async def test_condition_alert_on_and_done(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    hass.states.async_set("binary_sensor.back_door", "off")
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        state_alert(
            "Back Door Open",
            "binary_sensor.back_door",
            message="{{ subject_entity_name }} is open",
            done_message="Closed: {{ end_reason }}",
        ),
        PHONE,
        options=DEFAULTS,
    )
    hass.states.async_set(
        "binary_sensor.back_door", "on", {"friendly_name": "Back door"}
    )
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.back_door", "off")
    await hass.async_block_till_done()
    assert [message for _, message in _sent(calls)] == [
        "Back door is open",
        "Closed: resolved",
    ]


async def test_no_data_end_says_so(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The default done message doesn't make a lost-data end look resolved."""
    hass.states.async_set("binary_sensor.back_door", "on")
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        state_alert("Back Door Open", "binary_sensor.back_door"),
        PHONE,
        options={**DEFAULTS, "no_data_grace": {"minutes": 1}},
    )
    hass.states.async_set("binary_sensor.back_door", "unavailable")
    await hass.async_block_till_done()
    await _tick(hass, freezer, 1)
    assert _sent(calls)[-1] == (
        "Back Door Open",
        "Back Door Open lost its data; stopped firing after 1 minute.",
    )


async def test_render_failure_falls_back_to_default(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open", message="{{ 1 / 0 }}"),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    assert _sent(calls) == [("Back Door Open", "Back Door Open is firing.")]


async def test_explicit_empty_list_notifies_nobody(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    with patch(PERSISTENT_CREATE) as create:
        await setup_alerts(alert_subentry("Back Door Open", notifier_groups=[]), PHONE)
        await _call(hass, "fire")
    assert not calls
    create.assert_not_called()
    assert hass.states.get(DOOR).attributes["notifier_groups"] == []


async def test_own_groups_override_default(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    phone = async_mock_service(hass, "notify", "phone")
    pager = async_mock_service(hass, "notify", "pager")
    await setup_alerts(
        alert_subentry("Back Door Open", notifier_groups=["pagers"]),
        PHONE,
        group_subentry("Pagers", "pagers", actions=[{"action": "notify.pager"}]),
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    assert not phone
    assert len(pager) == 1
    assert hass.states.get(DOOR).attributes["notifier_groups"] == ["Pagers"]


async def test_no_default_uses_fallback_and_raises_issue(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Without default groups, alerts relying on them notify the fallback, and
    a Repairs issue says why until defaults are set."""
    registry = ir.async_get(hass)
    with patch(PERSISTENT_CREATE) as create:
        entry = await setup_alerts(alert_subentry("Back Door Open"), PHONE)
        await _call(hass, "fire")
    create.assert_called_once_with(
        hass,
        "Back Door Open is firing.",
        "Back Door Open",
        notification_id="alert_redux_back_door_open",
    )
    assert hass.states.get(DOOR).attributes["notifier_groups"] == ["Fallback"]
    issue = registry.async_get_issue(DOMAIN, ISSUE_DEFAULT_GROUPS_UNSET)
    assert issue is not None
    assert issue.translation_placeholders == {"count": "1", "alerts": "Back Door Open"}

    hass.config_entries.async_update_entry(entry, options=DEFAULTS)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, ISSUE_DEFAULT_GROUPS_UNSET) is None
    assert hass.states.get(DOOR).attributes["notifier_groups"] == ["Phones"]


async def test_no_issue_when_no_alert_relies_on_default(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    await setup_alerts(
        alert_subentry("Back Door Open", notifier_groups=["phones"]), PHONE
    )
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_DEFAULT_GROUPS_UNSET) is None
    )


async def test_reminder_schedule(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """The default schedule [10, 20, 30, 60] reminds at 10, 30, 60 min, then hourly."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(alert_subentry("Back Door Open"), PHONE, options=DEFAULTS)
    await _call(hass, "fire")
    attributes = hass.states.get(DOOR).attributes
    assert attributes["reminder_schedule"] == [10, 20, 30, 60]

    reminded_at = []
    for minute in range(1, 190):
        await _tick(hass, freezer, 1)
        if len(calls) > 1 + len(reminded_at):
            reminded_at.append(minute)
    assert reminded_at == [10, 30, 60, 120, 180]
    assert calls[-1].data["message"] == ("Back Door Open is still firing (3 hours).")
    assert calls[-1].data["data"] == {"x": "reminder"}


async def test_ack_stops_and_unack_resumes_reminders(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Unacknowledging resumes the original schedule; missed slots aren't sent."""
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open", reminder_schedule=[10]),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    await _tick(hass, freezer, 5)
    await _call(hass, "ack")
    assert hass.states.get(DOOR).attributes["next_reminder"] is None
    await _tick(hass, freezer, 20)  # slots at 10 and 20 pass while acked
    assert len(calls) == 1

    await _call(hass, "unack")  # at 25 min
    await _tick(hass, freezer, 4)
    assert len(calls) == 1
    await _tick(hass, freezer, 1)  # the 30-minute slot
    assert len(calls) == 2
    assert calls[-1].data["message"] == "Back Door Open is still firing (30 minutes)."


async def test_no_reminders_with_empty_schedule(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    await setup_alerts(
        alert_subentry("Back Door Open", reminder_schedule=[]),
        PHONE,
        options=DEFAULTS,
    )
    await _call(hass, "fire")
    await _tick(hass, freezer, 120)
    assert len(calls) == 1


async def test_schedule_change_replans(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """Changing the default schedule applies to firing alerts from now on."""
    calls = async_mock_service(hass, "notify", "phone")
    entry = await setup_alerts(
        alert_subentry("Back Door Open"), PHONE, options=DEFAULTS
    )
    await _call(hass, "fire")
    await _tick(hass, freezer, 3)
    hass.config_entries.async_update_entry(
        entry, options={**DEFAULTS, "default_reminder_schedule": [5]}
    )
    await hass.async_block_till_done()
    await _tick(hass, freezer, 2)
    assert len(calls) == 2


async def _restart(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_restored_firing_is_quiet_and_keeps_reminders(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A restored firing sends no on notification, and its reminder slot is kept;
    one that fell due while down is sent once when back (spec §15.1)."""
    calls = async_mock_service(hass, "notify", "phone")
    entry = await setup_alerts(
        alert_subentry("Back Door Open", subentry_id="door"), PHONE, options=DEFAULTS
    )
    await _call(hass, "fire")
    await _tick(hass, freezer, 5)
    await _restart(hass, entry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(calls) == 1
    await _tick(hass, freezer, 5)
    assert len(calls) == 2  # the 10-minute slot

    await _restart(hass, entry)
    freezer.tick(timedelta(minutes=25))  # the 30-minute slot passes while down
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer, 0.1)
    assert len(calls) == 3
    assert calls[-1].data["message"] == "Back Door Open is still firing (35 minutes)."
    # Then the schedule carries on: the next slot is at 60 minutes.
    await _tick(hass, freezer, 20)
    assert len(calls) == 3
    await _tick(hass, freezer, 5)
    assert len(calls) == 4


async def test_group_edit_applies_in_place(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    phone = async_mock_service(hass, "notify", "phone")
    pager = async_mock_service(hass, "notify", "pager")
    entry = await setup_alerts(
        alert_subentry("Back Door Open"), PHONE, options=DEFAULTS
    )
    hass.config_entries.async_update_subentry(
        entry,
        entry.subentries["phones"],
        title="Pagers",
        data={**PHONE["data"], "actions": [{"action": "notify.pager"}]},
    )
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).attributes["notifier_groups"] == ["Pagers"]
    await _call(hass, "fire")
    assert not phone
    assert len(pager) == 1


async def test_deleted_group_is_skipped(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    phone = async_mock_service(hass, "notify", "phone")
    entry = await setup_alerts(
        alert_subentry("Back Door Open", notifier_groups=["phones", "pagers"]),
        PHONE,
        group_subentry("Pagers", "pagers", actions=[{"action": "notify.pager"}]),
    )
    hass.config_entries.async_remove_subentry(entry, "pagers")
    await hass.async_block_till_done()
    assert hass.states.get(DOOR).attributes["notifier_groups"] == ["Phones"]
    await _call(hass, "fire")
    assert len(phone) == 1


async def test_fallback_group_option(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """With a fallback group chosen, alerts without default groups use it."""
    pager = async_mock_service(hass, "notify", "pager")
    with patch(PERSISTENT_CREATE) as create:
        await setup_alerts(
            alert_subentry("Back Door Open"),
            group_subentry("Pagers", "pagers", actions=[{"action": "notify.pager"}]),
            options={"fallback_group": "pagers"},
        )
        assert hass.states.get(DOOR).attributes["notifier_groups"] == ["Pagers"]
        await _call(hass, "fire")
    assert len(pager) == 1
    create.assert_not_called()


async def test_unreachable_groups_fall_back(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """If no member of the alert's groups can be notified within the retry
    timeout, the fallback gets the notification (spec §9.4, §15.2)."""
    with patch(PERSISTENT_CREATE) as create:
        await setup_alerts(
            alert_subentry("Back Door Open"),
            group_subentry("Gone", "gone", actions=[{"action": "notify.gone"}]),
            options={
                "default_groups": ["gone"],
                "retry_timeout": {"minutes": 1},
            },
        )
        await _call(hass, "fire")
        create.assert_not_called()
        for _ in range(61):
            freezer.tick(timedelta(seconds=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
    create.assert_called_once_with(
        hass,
        "Back Door Open is firing.",
        "Back Door Open",
        notification_id="alert_redux_back_door_open",
    )


async def test_pending_retry_survives_restart(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """A notification waiting for a notifier is still delivered after a restart."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open"),
        group_subentry("Late", "late", actions=[{"action": "notify.late"}]),
        options={"default_groups": ["late"]},
    )
    await _call(hass, "fire")
    await _restart(hass, entry)
    calls = async_mock_service(hass, "notify", "late")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer, 1)
    assert _sent(calls) == [("Back Door Open", "Back Door Open is firing.")]


async def test_deleted_group_leaves_the_options(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """Deleting a group removes it from the default and fallback groups; deleting
    the last default raises the unset-defaults issue."""
    entry = await setup_alerts(
        alert_subentry("Back Door Open"),
        PHONE,
        group_subentry("Pagers", "pagers", actions=[{"action": "notify.pager"}]),
        options={"default_groups": ["phones", "pagers"], "fallback_group": "pagers"},
    )
    hass.config_entries.async_remove_subentry(entry, "pagers")
    await hass.async_block_till_done()
    assert entry.options["default_groups"] == ["phones"]
    assert entry.options["fallback_group"] is None

    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, ISSUE_DEFAULT_GROUPS_UNSET) is None
    hass.config_entries.async_remove_subentry(entry, "phones")
    await hass.async_block_till_done()
    assert entry.options["default_groups"] == []
    assert registry.async_get_issue(DOMAIN, ISSUE_DEFAULT_GROUPS_UNSET) is not None
    assert hass.states.get(DOOR).attributes["notifier_groups"] == ["Fallback"]


# Replacing and clearing (spec §9.10)

MOBILE = group_subentry(
    "Phones", "phones", actions=[{"action": "notify.mobile_app_phone"}]
)
TAG = "alert_redux_back_door_open"


def _mobile(calls: list[ServiceCall]) -> list[tuple[str, Any]]:
    """Return the messages with their tags (buttons are tested on their own)."""
    return [
        (call.data["message"], {"tag": call.data["data"]["tag"]}) for call in calls
    ]


async def test_notifications_replace_and_ack_clears(
    hass: HomeAssistant, setup_alerts: SetupAlerts, freezer: FrozenDateTimeFactory
) -> None:
    """On and reminder share a tag; acknowledging clears; the done message
    replaces what's there."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(alert_subentry("Back Door Open"), MOBILE, options=DEFAULTS)
    await _call(hass, "fire")
    await _tick(hass, freezer, 10)
    await _call(hass, "ack")
    await _call(hass, "dismiss")
    assert _mobile(calls) == [
        ("Back Door Open is firing.", {"tag": TAG}),
        ("Back Door Open is still firing (10 minutes).", {"tag": TAG}),
        ("clear_notification", {"tag": TAG}),
        ("Back Door Open stopped firing after 10 minutes.", {"tag": TAG}),
    ]


async def test_snooze_clears(hass: HomeAssistant, setup_alerts: SetupAlerts) -> None:
    """Snoozing is acknowledging; unacknowledging clears nothing more."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(alert_subentry("Back Door Open"), MOBILE, options=DEFAULTS)
    await _call(hass, "fire")
    await _call(hass, "snooze", duration={"minutes": 30})
    await _call(hass, "unack")
    assert _mobile(calls) == [
        ("Back Door Open is firing.", {"tag": TAG}),
        ("clear_notification", {"tag": TAG}),
    ]


async def test_deleted_alert_cleared(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = await setup_alerts(
        alert_subentry("Back Door Open", subentry_id="door"), MOBILE, options=DEFAULTS
    )
    await _call(hass, "fire")
    hass.config_entries.async_remove_subentry(entry, "door")
    await hass.async_block_till_done()
    assert _mobile(calls)[-1] == ("clear_notification", {"tag": TAG})


async def test_renamed_alert_still_clears(
    hass: HomeAssistant, setup_alerts: SetupAlerts
) -> None:
    """After a rename, acknowledging clears what was shown under the old tag."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await setup_alerts(alert_subentry("Back Door Open"), MOBILE, options=DEFAULTS)
    await _call(hass, "fire")
    renamed = "alert_redux.side_door_open"
    er.async_get(hass).async_update_entity(DOOR, new_entity_id=renamed)
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, "ack", {"entity_id": renamed}, blocking=True
    )
    await hass.async_block_till_done()
    assert _mobile(calls)[-1] == ("clear_notification", {"tag": TAG})
