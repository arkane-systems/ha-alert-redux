# Converter tools

Standalone scripts that turn another alerting setup into a file for
`alert_redux.import` (see [Exporting and importing](../README.md#exporting-and-importing)).
They aren't part of the integration and aren't installed by HACS: run them from a
checkout of this repository, anywhere with Python 3.10+ and PyYAML
(`pip install pyyaml`). Home Assistant isn't needed.

```sh
python3 tools/convert_alert.py  alert.yaml  -o alert-redux.yaml   # built-in `alert:`
python3 tools/convert_alert2.py alert2.yaml -o alert-redux.yaml   # Alert2
```

Both take `-` for standard input, and these options:

| Option | Meaning |
|---|---|
| `-o FILE` | Write the import file there instead of to standard output. |
| `--group-map FILE` | YAML mapping old notifiers to notifier group names (below). |
| `--format json` | Write JSON instead of YAML. |
| `--strict` | Write nothing and exit 1 if anything wasn't converted exactly. |

`convert_alert.py` also takes `--skip-first-as-delay` (below).

A report goes to standard error: what was converted, what wasn't, and the notifier
groups the file needs. Exit status is 2 if the input can't be read.

## A good way to migrate

Converting is the easy part; moving alerting you rely on deserves a little care.

1. **Convert, and read the report.** Everything that wasn't converted exactly is
   listed, with the reason. Decide each one: fix it by hand in the file, accept
   the difference, or recreate it (generators) from the suggested settings.
2. **Settle the notifier groups.** Create the groups the report names, or map the
   old notifiers onto groups you already have with `--group-map` and convert again.
   An import naming a group that doesn't exist is refused.
3. **Dry-run the import.** `alert_redux.import` with `dry_run: true` makes every
   check a real import would and changes nothing. It lists what would be created,
   updated, or left alone, or refuses with every problem at once. Fix and repeat
   until it's clean.
4. **Import for real, then look.** Check the alerts on the admin card, and the
   ones that now use the default groups because their notifier couldn't be mapped.
5. **Run both side by side for a while** if you can: leave the old alerts in place
   (or just their notifiers off) until the new ones have fired, notified, and been
   acknowledged the way you expect. Then remove the old configuration.
6. **Keep the files.** The converted file and the original YAML are a record of what
   you moved; importing the file again is harmless.

## Notifier groups

Alert Redux alerts name notifier **groups**, which an import file can't create. Each
old notifier (a `notify.` service name) becomes a group of the same name, without
`notify.`. Create those groups (Settings → Devices & services → Alert Redux), or
rename and merge them with a map before importing:

```yaml
# group-map.yaml: old notifier -> group name, or a list of names; empty drops it
mobile_app_pixel: Phones
mobile_app_ipad: Phones
persistent_notification: []
```

## The built-in `alert` integration

Input: the `alert:` section, with or without its `alert:` line, or a whole
`configuration.yaml`. (An `!include` can't be followed: convert the included file.)
Every alert becomes a state alert: `entity_id` and `state`, `repeat` as the
reminder schedule, `can_acknowledge`, `message`, `done_message`, and `notifiers`.
A `done_message` of `clear_notification` (the mobile app's way to clear a
notification) isn't kept as text: set the group member's "clear instead of showing
the done message" option. Not converted, with a warning: `title` (notifications are titled with the alert's
name), `data` (set it on the group's members), and `skip_first`. The built-in
`skip_first` has no exact equivalent, but people moving to Alert2 usually use a delay
before the alert fires. With `--skip-first-as-delay`, an alert with `skip_first`
gets a `delay_on` of its first `repeat` interval. That isn't the same behaviour: the
alert notifies as soon as its condition has held that long, rather than being seen
at once and notified later, and a shorter blip is never seen at all. The report says
which alerts it applied to.

After converting, check the file with `alert_redux.import` and `dry_run: true`,
then import it. Re-importing is harmless: alerts match by name.

## Alert2

Input: an `alert2:` block (`defaults:` apply to its `alerts:`), a **single alert's
YAML**, as the Alert Manager card shows it, or a list of alerts.

| Alert2 | Alert Redux |
|---|---|
| `condition`: an entity | state alert, target state `on` |
| `condition`: a template that only compares one entity's state (`{{ states('x') == 'v' }}`, `{{ is_state('x', 'v') }}`) | state alert (with a note in the report) |
| `condition`: any other template | template alert |
| `condition_on` / `condition_off`, `trigger_on` / `trigger_off` | on/off alert |
| `trigger` (and `condition`) | trigger alert |
| `threshold` | threshold alert |
| neither (reported with `alert2.report`) | manual alert that ends by itself |
| `priority` low / medium / high | notice / warning / critical |
| `delay_on_secs`, `reminder_frequency_mins`, `throttle_fires_per_mins` | `delay_on`, `reminder_schedule`, `throttle` |
| `message`, `done_message`, `reminder_message`, `display_msg`, `icon` | the same; `on_time_str` and `on_secs` become `duration` and `duration_seconds` |
| `notifier` | notifier groups |
| `supersedes` | supersedes (by the converted alerts' entity IDs) |

Notifiers may be a name, a list, or `notify.<name>`. A template or an entity (which
Alert2 allows) can't be mapped: it's dropped with a warning, leaving the alert on
the default groups. An explicit `null` or empty list means nobody. `defaults:`
options that can't be converted are reported once, not for every alert.

An alert with `condition_on` but no off side (`manual_off`) becomes a template
alert that ends when its condition does; one with only trigger criteria becomes a
trigger alert. `condition: true` (YAML's boolean) is accepted.

Alerts are named by a plain `friendly_name`; otherwise by both `domain` and `name`,
with underscores as spaces (`house` and `door_open` give "House Door open"), since a
name alone is often cryptic and clashes across domains. A `friendly_name` shared by
two alerts gets the domain in front. A reference to an alert that isn't in
the input is kept as a dangling reference, which import allows.

Not converted, with a warning or in the report: generators (see below), `ack_required` and
`ack_reminders_only` (Alert Redux's equivalent, latching alerts, is a later feature,
after which the converter will handle them), `done_notifier: false`, and `early_start`, `manual_on`,
`manual_off`, `actions_on`, `title`, `target`, `data`, and a few other options with
no equivalent.

After converting, check the file with `alert_redux.import` and `dry_run: true`,
then import it. Re-importing is harmless: alerts match by name.

### Generators

Alert2 generators make alerts from a list or template; Alert Redux generators
choose entities by criteria (label, area, domain, device class, entity ID
pattern), so they can't be converted. The report instead gives, under "Suggested
settings", the settings of an Alert Redux generator that match the generator's
body: its kind, messages, priority, delays, reminders, and notifier groups, with
`genElem` and `genEntityId` rewritten to `target`. For a generator that selects
entities from `states.<domain>` with a pattern (`'match'`, or `entity_regex`),
the targets are the domain and the pattern as an entity ID glob, to check; for a
list, they're a label to put on those entities, or, if the list's values aren't
entities (limits, say), fixed alerts are suggested instead. A templated name isn't
carried over (Alert Redux names alerts after their target), and the report quotes
it. Create the generator from
those settings in the integration's forms. Only condition kinds (state, threshold,
template, on/off) can be generated; supersession in a generator isn't carried over.
