# Alert Redux with HA-MCP

How the tasks in the other files map onto the
[HA-MCP](https://github.com/homeassistant-ai/ha-mcp) server's tools, and the
quirks met in practice. Tool names can change between HA-MCP releases; if one is
missing, search its tools for the same purpose.

## Contents
- Finding things
- Creating, editing, deleting
- Options
- Actions, states, history
- Quirks

## Finding things

| Need | Call |
|---|---|
| The config entry ID | `ha_get_integration(query="alert_redux")` |
| Subentry IDs (alerts, generators, groups) | `ha_get_integration(entry_id=…, include_subentries=True)` |
| An alert's edit form, pre-filled | `ha_get_integration(entry_id=…, include_subentry_schema=True, subentry_type="alert", subentry_id=…)` |
| What an alert is configured with (button actions, message templates, …) | the edit form's `suggested_value` and `default` entries: attributes show only some settings, e.g. button labels, and `message` only while firing |
| What refers to an alert, before deleting it | the edit form's `description_placeholders.referrers`: `"none."`, or the referrers' names followed by a warning |
| All alerts and states | `ha_search(domain_filter="alert_redux", result_fields=["entity_id", "state"])` |
| One alert's details | `ha_get_state("alert_redux.x", attribute_keys=[…])` |

## Creating, editing, deleting

Create (the `next_step_id` answers the kind menu):

```python
ha_config_set_helper(
    helper_type="config_subentry", action="create",
    entry_id=ENTRY, subentry_type="alert",
    config={"next_step_id": "state", "name": "…", …,
            "notifications": {…}, "supersession": {}},
)
```

Edit: `action="update"` with `subentry_id`, passing the **whole** form (see
Quirks). Notifier groups and generators work the same way, with
`subentry_type="notifier_group"` or `"generator"` (a group has no menu, so no
`next_step_id`).

A **create** form can't be read beforehand: `include_subentry_schema` without a
`subentry_id` shows only the kind menu. Use the tables in
[configuring.md](configuring.md); a refused submission returns the form's full
`data_schema` with the error, and an existing alert of the same kind shows its
fields in its edit form.

Delete:

```python
ha_remove_helpers_integrations(
    target=ENTRY, helper_type="config_subentry", subentry_id=SUB, confirm=True)
```

## Options

`ha_set_integration(entry_id=ENTRY, config={…})` drives the options flow, as a
patch: omitted fields keep their values. Sections (`event_durations`,
`quiet_hours`, `supersession`) are nested objects.

## Actions, states, history

- Actions: `ha_call_service("alert_redux", "ack", entity_id="alert_redux.x")`;
  `fire` with `data={"data": {…}}`; `snooze` with
  `data={"duration": {"minutes": 30}}`. `export` returns its definitions only
  with `return_response=True` (they come back as `service_response`); `import`
  takes `data={"definitions": {…}, "overwrite": …, "dry_run": …}`.
- Logbook: `ha_get_logs(entity_id="alert_redux.x")`. Log messages:
  `ha_get_logs(source="system", search="alert_redux")`.
- Repairs issues: `ha_call_service(ws_command="repairs/list_issues", data={})`.
- Dashboards: `ha_config_set_dashboard` with cards of `type:
  custom:alert-redux-card`.

## Quirks

- **Acknowledgment key.** In HA-MCP's strict best-practices mode, write tools
  (such as `ha_config_set_helper`) refuse calls without a `BestPracticeKey`. The
  refusal's suggestion names the exact `ha_get_skill_guide` call (its parameters
  differ between HA-MCP versions); the key is on the first line of the content it
  returns. Pass it as `BestPracticeKey`, with `MandatoryBPS=False` so later writes
  don't return the whole guide inline. The key rotates hourly: when a call is
  refused again, read it again.
- **Edits must pass the whole form**, whatever the tool's own description says
  about updates being a patch. An update doesn't carry over sections that are
  empty in the stored data, so a partial one fails with `supersession: required
  key not provided`. Read the edit form, and send every field you want kept, with
  `"supersession": {}` when there are no relationships.
- **Phantom option keys.** `ha_get_integration` may show the options with extra,
  flattened copies of section fields (`hours`, `minutes`, `critical`, … at the top
  level). That's an HA-MCP display bug
  ([ha-mcp#2538](https://github.com/homeassistant-ai/ha-mcp/issues/2538)), not
  stored data: ignore it, and don't re-save the options to "clean" it.
- **Refused actions look like server errors.** An Alert Redux validation error
  (`not_manual`, …) comes back from `ha_call_service` as an HTTP 500. The real
  message is in `ha_get_logs(source="error_log", search="alert_redux")`.
- **Restarts.** After `ha_restart`, allow a couple of minutes before checking
  states; integrations that load late can make an early check misleading.
