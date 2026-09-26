/** A length of time, e.g. "less than a minute", "12 min", "3 h 5 min", "2 d 4 h". */
export function span(ms: number): string {
  const minutes = Math.floor(Math.max(0, ms) / 60_000);
  if (minutes < 1) return "less than a minute";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  const days = Math.floor(hours / 24);
  return hours % 24 ? `${days} d ${hours % 24} h` : `${days} d`;
}

/** How long ago something started. */
export const elapsed = (since: Date, now: number = Date.now()): string =>
  span(now - since.getTime());

/** How long until something happens, rounded up to the minute. */
export const remaining = (until: Date, now: number = Date.now()): string =>
  span(Math.ceil((until.getTime() - now) / 60_000) * 60_000);

/** A time of day, or a date and time if it isn't today. */
export function clockTime(date: Date, language?: string): string {
  const today = new Date().toDateString() === date.toDateString();
  return date.toLocaleString(
    language,
    today
      ? { hour: "numeric", minute: "2-digit" }
      : { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" },
  );
}
