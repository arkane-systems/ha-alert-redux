"""Tests for the converter tools (spec §17, phase 14): their output must be a file
`alert_redux.import` accepts."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pytest
import yaml
from homeassistant.core import HomeAssistant

from custom_components.alert_redux.const import DOMAIN

from .conftest import SetupAlerts, group_subentry

TOOLS = Path(__file__).parent.parent / "tools"
FIXTURES = Path(__file__).parent / "fixtures" / "converters"
sys.path.insert(0, str(TOOLS))

import _convert_common as common  # noqa: E402
import convert_alert  # noqa: E402
import convert_alert2  # noqa: E402


def _convert(module: Any, fixture: str, mapping: dict[str, Any] | None = None):
    data = common.load_yaml((FIXTURES / fixture).read_text())
    alerts, report = module.convert(data, common.GroupMap(mapping))
    return {a["name"]: a for a in alerts}, report


def test_alert_section() -> None:
    """The built-in alert's options become a state alert's."""
    alerts, report = _convert(convert_alert, "alert.yaml")
    garage = alerts["Garage door left open"]
    assert garage["kind"] == "state"
    assert garage["entity_id"] == "binary_sensor.garage_door"
    assert garage["reminder_schedule"] == [15, 30, 60]
    assert garage["notifier_groups"] == ["mobile_app_pixel", "family"]
    assert alerts["Freezer warm"]["reminder_schedule"] == [30]
    assert alerts["Freezer warm"]["acknowledgeable"] is False
    assert any("skip_first" in w for w in report.warnings)
    assert any("title" in w for w in report.warnings)
    assert report.groups == {"mobile_app_pixel", "family"}


def test_skip_first_as_delay() -> None:
    """With the option, skip_first becomes a delay_on of the first repeat interval."""
    data = common.load_yaml((FIXTURES / "alert.yaml").read_text())
    alerts, report = convert_alert.convert(data, common.GroupMap(), skip_first_as_delay=True)
    garage = next(a for a in alerts if a["name"] == "Garage door left open")
    assert garage["delay_on"] == {"seconds": 900}
    assert any("became a delay_on of 15 minutes" in w for w in report.warnings)
    assert "delay_on" not in next(a for a in alerts if a["name"] == "Freezer warm")


def test_cli_skip_first_option(tmp_path: Path) -> None:
    """The command takes --skip-first-as-delay."""
    out = tmp_path / "out.yaml"
    source = str(FIXTURES / "alert.yaml")
    args = [source, "-o", str(out), "--skip-first-as-delay"]
    assert common.main(args, "x", convert_alert.convert, convert_alert.OPTIONS) == 0
    assert "delay_on" in out.read_text()


def test_alert_without_section_line_and_group_map() -> None:
    """The bare section works, and a group map renames or drops notifiers."""
    data = common.load_yaml(
        "a:\n  entity_id: light.x\n  repeat: 5\n  notifiers: [one, two]\n"
    )
    alerts, report = convert_alert.convert(
        data, common.GroupMap({"notify.one": "Phones", "two": []})
    )
    assert alerts[0]["notifier_groups"] == ["Phones"]
    assert report.groups == {"Phones"}


def test_alert_include_is_refused() -> None:
    """A section behind !include can't be followed."""
    data = common.load_yaml("alert: !include alert.yaml\n")
    with pytest.raises(ValueError, match="can't be followed"):
        convert_alert.convert(data, common.GroupMap())


def test_alert2_block() -> None:
    """Each Alert2 kind of alert becomes the matching kind."""
    alerts, report = _convert(convert_alert2, "alert2.yaml")
    door = alerts["House Door open"]
    assert door["kind"] == "state"
    assert door["priority"] == "warning"  # from the defaults
    assert door["delay_on"] == {"seconds": 120}
    assert door["message"] == "Open for {{ duration }}"
    assert door["reminder_schedule"] == [10, 60]
    assert door["notifier_groups"] == ["mobile_app_pixel"]

    leak = alerts["Water leak"]
    assert leak["kind"] == "template"
    assert leak["priority"] == "critical"
    assert leak["supersedes"] == [{"alert": "alert_redux.house_door_open"}]
    assert leak["throttle"] == [5, 30]

    assert alerts["House Temp high"]["kind"] == "threshold"
    assert alerts["House Temp high"]["entity_id"] == "sensor.temp"
    assert alerts["House Temp high"]["hysteresis"] == 2
    assert alerts["House Doorbell"]["kind"] == "trigger"
    assert alerts["Sys Cycle"]["kind"] == "on_off"
    assert alerts["House Reported"]["kind"] == "manual"
    assert alerts["House Reported"]["ends_by_itself"] is True
    assert "House Per door" not in alerts
    assert any("per_door" in s for s in report.skipped)
    # The generator's body, as the settings of an Alert Redux generator.
    (suggestion,) = report.suggestions
    assert "house_per_door" in suggestion
    assert "kind: template" in suggestion
    assert "template: '{{ true }}'" in suggestion
    assert "mobile_app_pixel" in suggestion
    assert "targets:" in suggestion
    assert any("early_start" in w for w in report.warnings)


def test_alert2_single_alert_and_list() -> None:
    """A single alert, as the Alert Manager card shows it, converts, as does a list."""
    alerts, report = _convert(convert_alert2, "alert2_single.yaml")
    assert alerts["House Door open"]["priority"] == "notice"  # Alert2's default, low
    assert alerts["House Door open"]["supersedes"] == [
        {"alert": "alert_redux.house_elsewhere"}
    ]
    assert any("elsewhere" in w for w in report.warnings)

    data = common.load_yaml("- {domain: a, name: x, condition: s.a}\n- {domain: b, name: x, condition: s.b}\n")
    listed, _ = convert_alert2.convert(data, common.GroupMap())
    assert [a["name"] for a in listed] == ["A X", "B X"]  # domain and name

    named = common.load_yaml(
        "- {domain: a, name: x, friendly_name: Same, condition: s.a}\n"
        "- {domain: b, name: y, friendly_name: Same, condition: s.b}\n"
        "- {domain: c, name: z, friendly_name: '{{ 1 }}', condition: s.c}\n"
    )
    names = [a["name"] for a in convert_alert2.convert(named, common.GroupMap())[0]]
    assert names == ["A Same", "B Same", "C Z"]  # a clash, and a template


def test_alert2_rejects_other_input() -> None:
    """Something that isn't alerts is an error."""
    with pytest.raises(ValueError):
        convert_alert2.convert({"foo": 1}, common.GroupMap())


@pytest.mark.parametrize(
    ("module", "fixture"),
    [(convert_alert, "alert.yaml"), (convert_alert2, "alert2.yaml"),
     (convert_alert2, "alert2_single.yaml")],
)
async def test_output_imports(
    hass: HomeAssistant, setup_alerts: SetupAlerts, module: Any, fixture: str
) -> None:
    """The import action accepts what the converters write."""
    data = common.load_yaml((FIXTURES / fixture).read_text())
    alerts, report = module.convert(data, common.GroupMap())
    await setup_alerts(*(group_subentry(name) for name in sorted(report.groups)))
    document = yaml.safe_load(yaml.safe_dump(common.envelope(alerts)))
    result = await hass.services.async_call(
        DOMAIN,
        "import",
        {"definitions": document, "dry_run": True},
        blocking=True,
        return_response=True,
    )
    assert len(result["created"]) == len(alerts)


def test_cli_writes_file_and_strict_fails(tmp_path: Path, capsys) -> None:
    """The command writes the file, and --strict refuses when there are warnings."""
    out = tmp_path / "out.yaml"
    source = str(FIXTURES / "alert.yaml")
    assert common.main([source, "-o", str(out)], "x", convert_alert.convert) == 0
    assert yaml.safe_load(out.read_text())["format"] == "alert_redux"
    out.unlink()
    assert common.main([source, "-o", str(out), "--strict"], "x", convert_alert.convert) == 1
    assert not out.exists()
    assert common.main([str(tmp_path / "missing.yaml")], "x", convert_alert.convert) == 2
