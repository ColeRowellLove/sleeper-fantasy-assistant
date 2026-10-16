import type { AlertItem } from "./api";

/** The viewer's "cleared at" time from their cookie: a valid ISO time, or null (never throws). */
export function parseSeen(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let text = raw;
  try {
    text = decodeURIComponent(raw);
  } catch {
    return null; // a malformed cookie is ignored, not a crash
  }
  return Number.isFinite(Date.parse(text)) ? text : null;
}

/** The alerts created after `seen` (an ISO time from the viewer's cookie); all of them without one. */
export function unreadAlerts(alerts: AlertItem[], seen: string | null | undefined): AlertItem[] {
  const seenAt = seen ? Date.parse(seen) : NaN;
  if (!Number.isFinite(seenAt)) return alerts;
  return alerts.filter((a) => Date.parse(a.created_at) > seenAt);
}

/** The time to remember when the viewer clears their alerts: the newest alert's own time. */
export function newestAlertTime(alerts: AlertItem[]): string | null {
  const times = alerts.map((a) => Date.parse(a.created_at)).filter(Number.isFinite);
  return times.length > 0 ? new Date(Math.max(...times)).toISOString() : null;
}

/** "Alerts" or "Alerts (3 new)": the count is in words, never only a color or a dot. */
export function alertsTabLabel(unread: number): string {
  return unread > 0 ? `Alerts (${unread} new)` : "Alerts";
}

/** "Mon, Oct 12, 4:05 PM" in UTC, so the server and the browser print the same text. */
export function alertTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  })} UTC`;
}
