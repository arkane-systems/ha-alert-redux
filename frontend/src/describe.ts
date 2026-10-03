// A plain-text summary of an alert's or generator's settings, made from its exported
// definition (the alert_redux.export action's alerts and generators, spec §16), to
// copy when setting up a matching alert. Pure: no Home Assistant, no DOM.

/** One definition as the export action returns it: its id, name, and stored data. */
export type Definition = { id?: string; name: string; kind: string } & Record<string, unknown>;

type Duration = Record<string, number>;

const PRIORITY_NOTES: Record<string, string> = {
  emergency: "emergency",
  critical: "critical",
  warning: "warning",
  notice: "notice",
  informational: "informational",
};

const KIND_TEXT: Record<string, string> = {
  manual: "manual",
  state: "state",
  on_off: "on/off",
  threshold: "threshold",
  template: "template",
  alert_state: "alert state",
  trigger: "trigger",
  event: "bus event",
};

/** A duration object ({hours, minutes, seconds}) as words, e.g. "1 h 30 min". */
export function durationText(value: unknown): string {
  if (value === null || typeof value !== "object") return String(value ?? "");
  const d = value as Duration;
  const seconds =
    (d.days ?? 0) * 86400 +
    (d.hours ?? 0) * 3600 +
    (d.minutes ?? 0) * 60 +
    (d.seconds ?? 0) +
    (d.milliseconds ?? 0) / 1000;
  if (seconds === 0) return "0 s";
  const parts: string[] = [];
  let rest = seconds;
  for (const [size, unit] of [
    [86400, "d"],
    [3600, "h"],
    [60, "min"],
  ] as const) {
    const count = Math.floor(rest / size);
    if (count) parts.push(`${count} ${unit}`);
    rest -= count * size;
  }
  if (rest) parts.push(`${Number(rest.toFixed(3))} s`);
  return parts.join(" ");
}

const quote = (text: unknown): string => `"${String(text)}"`;

const list = (items: unknown): string[] => (Array.isArray(items) ? items.map(String) : []);

/** A template or free text, kept to one line. */
const oneLine = (text: unknown): string => String(text).replace(/\s*\n\s*/g, " ").trim();

function triggerText(trigger: unknown): string {
  if (trigger === null || typeof trigger !== "object") return String(trigger);
  const { trigger: platform, platform: legacy, ...rest } = trigger as Record<string, unknown>;
  const details = Object.entries(rest)
    .map(([key, value]) => `${key} ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(", ");
  return `${platform ?? legacy ?? "trigger"}${details ? ` (${details})` : ""}`;
}

function triggersText(triggers: unknown): string {
  return list(Array.isArray(triggers) ? triggers.map(triggerText) : []).join("; ");
}

/** What makes the alert fire, for each kind; null for kinds that say it elsewhere. */
function firesWhen(d: Definition, generator: boolean): string[] {
  const target = generator ? "the target entity" : String(d.entity_id ?? "");
  const lines: string[] = [];
  switch (d.kind) {
    case "manual":
      lines.push("Fired and dismissed by actions (fire, dismiss)");
      if (d.user_dismissable) lines.push("Dismissable from the card");
      if (d.ends_by_itself || d.duration) {
        lines.push(`Ends by itself${d.duration ? ` after ${durationText(d.duration)}` : ""}`);
      }
      return lines;
    case "state":
      lines.push(`${target} is ${quote(d.target_state)}`);
      break;
    case "template":
      lines.push(`This template is true: ${oneLine(d.template)}`);
      break;
    case "alert_state": {
      const watched = generator ? "the target alert" : String(d.alert ?? "");
      lines.push(`${watched} is in state ${list(d.alert_states).join(" or ")}`);
      break;
    }
    case "threshold": {
      const value = d.value_template
        ? `the value of this template: ${oneLine(d.value_template)}`
        : `${target}${d.attribute ? ` attribute ${d.attribute}` : ""}`;
      const limits: string[] = [];
      if (d.maximum !== undefined) limits.push(`above ${oneLine(d.maximum)}`);
      if (d.minimum !== undefined) limits.push(`below ${oneLine(d.minimum)}`);
      const hysteresis = Number(d.hysteresis ?? 0);
      lines.push(
        `${value} is ${limits.join(" or ")}` +
          (hysteresis ? ` (ends ${hysteresis} inside the limit)` : ""),
      );
      break;
    }
    case "on_off": {
      for (const side of ["on", "off"] as const) {
        const parts: string[] = [];
        if (d[`${side}_template`]) parts.push(`template ${oneLine(d[`${side}_template`])}`);
        if (d[`${side}_triggers`]) parts.push(`triggers ${triggersText(d[`${side}_triggers`])}`);
        lines.push(`Turns ${side} on: ${parts.join(" and ")}`);
      }
      break;
    }
    case "trigger":
      lines.push(`Fires on: ${triggersText(d.triggers)}`);
      break;
    case "event": {
      let text = `Fires on the event ${d.event_type}`;
      if (d.event_data && typeof d.event_data === "object") {
        text += ` with data ${JSON.stringify(d.event_data)}`;
      }
      lines.push(text);
      break;
    }
  }
  if (d.condition) lines.push(`Only while this template is true: ${oneLine(d.condition)}`);
  if (d.delay_on) lines.push(`Fires after the condition has held for ${durationText(d.delay_on)}`);
  if (d.delay_off) lines.push(`Ends after it has been false for ${durationText(d.delay_off)}`);
  if (d.no_data_grace) lines.push(`No-data grace period: ${durationText(d.no_data_grace)}`);
  if (d.kind === "trigger" || d.kind === "event") {
    lines.push(
      d.duration
        ? `Stays firing for ${durationText(d.duration)}`
        : "Stays firing for the priority's default duration",
    );
  }
  return lines;
}

function targetsText(targets: unknown): string[] {
  if (targets === null || typeof targets !== "object") return [];
  const t = targets as Record<string, unknown>;
  const lines: string[] = [];
  for (const [key, label] of [
    ["labels", "labels"],
    ["areas", "areas"],
    ["domains", "domains"],
    ["device_classes", "device classes"],
  ] as const) {
    if (list(t[key]).length) lines.push(`${label}: ${list(t[key]).join(", ")}`);
  }
  if (t.pattern) lines.push(`entity ID matches ${t.pattern}`);
  if (list(t.exclude).length) lines.push(`excluding ${list(t.exclude).join(", ")}`);
  return lines;
}

function relationshipText(rel: unknown): string {
  const r = (rel ?? {}) as Record<string, unknown>;
  const other = String(r.alert ?? r.generator ?? "");
  const what =
    r.propagation === "acknowledge"
      ? "acknowledging it also acknowledges this alert"
      : r.propagation === "snooze"
        ? `acknowledging it also snoozes this alert for ${durationText(r.snooze_duration)}`
        : "";
  return `${other}${r.generator ? " (generator)" : ""}${what ? ` — ${what}` : ""}`;
}

function notificationLines(d: Definition): string[] {
  const lines: string[] = [];
  lines.push(
    d.notifier_groups === undefined
      ? "Notifies: the default groups"
      : list(d.notifier_groups).length
        ? `Notifies: ${list(d.notifier_groups).join(", ")}`
        : "Notifies: no groups",
  );
  if (d.reminder_schedule !== undefined) {
    const schedule = list(d.reminder_schedule);
    lines.push(
      schedule.length
        ? `Reminders: gaps of ${schedule.join(", ")} min, the last gap repeating`
        : "Reminders: none",
    );
  } else {
    lines.push("Reminders: the default schedule");
  }
  if (d.throttle !== undefined) {
    const [count, minutes] = Array.isArray(d.throttle) ? d.throttle : [];
    lines.push(
      count ? `Throttle: at most ${count} per ${minutes} min` : "Throttle: not throttled",
    );
  }
  return lines;
}

/** Return the text summary of a definition; generator is whether it is a generator's. */
export function describe(d: Definition, generator = false): string {
  const kind = KIND_TEXT[d.kind] ?? d.kind;
  const lines: string[] = [`${d.name} (${generator ? "generator of " : ""}${kind} alert)`];
  const priority = PRIORITY_NOTES[String(d.priority)] ?? String(d.priority ?? "warning");
  lines.push(
    `Priority: ${priority}, ${d.acknowledgeable === false ? "can't be acknowledged" : "acknowledgeable"}`,
  );
  if (d.latching) lines.push("Kept until acknowledged, even once it stops firing");
  if (generator) {
    if (d.name_template) lines.push(`Alert names: ${oneLine(d.name_template)}`);
    lines.push(`Targets: ${targetsText(d.targets).join("; ") || "none"}`);
  } else if (d.subject_entity) {
    lines.push(`Subject: ${d.subject_entity}`);
  }
  lines.push(...firesWhen(d, generator).map((line, i) => (i ? `  ${line}` : `Fires when: ${line}`)));
  for (const [key, label] of [
    ["message", "On message"],
    ["display_message", "Card message"],
    ["reminder_message", "Reminder message"],
    ["done_message", "Done message"],
  ] as const) {
    if (d[key]) lines.push(`${label}: ${quote(oneLine(d[key]))}`);
  }
  lines.push(...notificationLines(d));
  const buttons = Array.isArray(d.buttons) ? d.buttons : [];
  if (buttons.length) {
    const labels = buttons.map((b: { label?: string; require_unlock?: boolean }) =>
      b.require_unlock ? `${b.label} (unlocked phone only)` : String(b.label),
    );
    lines.push(`Notification buttons: ${labels.join(", ")}`);
  }
  if (d.button_snooze_duration) {
    lines.push(`Snooze button: ${durationText(d.button_snooze_duration)}`);
  }
  const relationships = Array.isArray(d.supersedes) ? d.supersedes : [];
  if (relationships.length) {
    lines.push(`Supersedes: ${relationships.map(relationshipText).join("; ")}`);
  }
  const proxies = [d.proxy_switch ? "switch" : "", d.proxy_snooze_button ? "snooze button" : ""]
    .filter(Boolean)
    .join(" and ");
  if (proxies) lines.push(`Voice proxies: ${proxies}`);
  return lines.join("\n");
}
