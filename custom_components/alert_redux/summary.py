"""The summary of all alerts, for the summary sensors (spec §11.2).

summarise is HA-free: it turns each alert's state, priority, and whether it's
missing data into the counts. SummaryCoordinator keeps the alerts' latest
reports, recomputes once per burst of changes, and tells its listeners.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import NamedTuple

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import AlertState, Priority


class AlertReport(NamedTuple):
    """What the summary needs to know about one alert."""

    entity_id: str
    state: AlertState
    priority: Priority
    missing_data: bool


@dataclass(frozen=True, slots=True)
class Summary:
    """Counts and entity IDs across all alerts; lists are sorted."""

    firing: tuple[str, ...] = ()
    active: tuple[str, ...] = ()
    acknowledged: tuple[str, ...] = ()
    no_data: tuple[str, ...] = ()
    disabled: tuple[str, ...] = ()
    highest_priority: Priority | None = None
    highest_unacked_priority: Priority | None = None
    firing_by_priority: dict[Priority, int] = field(default_factory=dict)
    active_by_priority: dict[Priority, int] = field(default_factory=dict)


def summarise(alerts: Iterable[AlertReport]) -> Summary:
    """Summarise the alerts.

    Firing is active or acknowledged; disabled includes suspended. An alert
    missing data counts as no data whatever its state, so a firing alert in its
    grace period counts both as firing and as no data (fail loud).
    """
    firing: list[AlertReport] = []
    active: list[AlertReport] = []
    acknowledged: list[str] = []
    no_data: list[str] = []
    disabled: list[str] = []
    for alert in alerts:
        if alert.state is AlertState.ACTIVE:
            firing.append(alert)
            active.append(alert)
        elif alert.state is AlertState.ACK:
            firing.append(alert)
            acknowledged.append(alert.entity_id)
        elif alert.state is AlertState.DISABLED:
            disabled.append(alert.entity_id)
        if alert.missing_data or alert.state is AlertState.NO_DATA:
            no_data.append(alert.entity_id)
    return Summary(
        firing=_ids(alert.entity_id for alert in firing),
        active=_ids(alert.entity_id for alert in active),
        acknowledged=_ids(acknowledged),
        no_data=_ids(no_data),
        disabled=_ids(disabled),
        highest_priority=_highest(firing),
        highest_unacked_priority=_highest(active),
        firing_by_priority=_by_priority(firing),
        active_by_priority=_by_priority(active),
    )


def _ids(entity_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(entity_ids))


def _highest(alerts: list[AlertReport]) -> Priority | None:
    return min((alert.priority for alert in alerts), key=lambda p: p.rank, default=None)


def _by_priority(alerts: list[AlertReport]) -> dict[Priority, int]:
    counts = dict.fromkeys(Priority, 0)
    for alert in alerts:
        counts[alert.priority] += 1
    return counts


class SummaryCoordinator:
    """Keeps the alerts' reports, and the summary of them, up to date.

    Alerts report by unique ID, which survives renames, each time they write
    their state, and withdraw when removed. A burst of reports (a supersession
    cascade, say) is summarised once, on the next turn of the event loop.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize, with no alerts."""
        self._hass = hass
        self._reports: dict[str, AlertReport] = {}
        self._listeners: list[Callable[[], None]] = []
        self._pending = False
        self.summary = summarise(())

    @callback
    def async_report(self, unique_id: str, report: AlertReport) -> None:
        """Take an alert's latest state."""
        if self._reports.get(unique_id) != report:
            self._reports[unique_id] = report
            self._async_schedule()

    @callback
    def async_withdraw(self, unique_id: str) -> None:
        """Forget a removed alert."""
        if self._reports.pop(unique_id, None) is not None:
            self._async_schedule()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call listener when the summary changes; returns the remover."""
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    @callback
    def _async_schedule(self) -> None:
        if not self._pending:
            self._pending = True
            self._hass.loop.call_soon(self._async_refresh)

    @callback
    def _async_refresh(self) -> None:
        self._pending = False
        summary = summarise(self._reports.values())
        if summary == self.summary:
            return
        self.summary = summary
        for listener in list(self._listeners):
            listener()
