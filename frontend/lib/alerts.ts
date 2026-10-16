import type { AlertItem } from "./api";

export interface WaiverTarget {
  player_id: string;
  name: string;
  position?: string | null;
  team?: string | null;
  projected: number;
  gain: number;
  /** The sentence after the name: "(WR, SEA): projected 11.4, +4.2 over ...". */
  detail?: string;
  /** The whole sentence, name included (used if there is no detail). */
  line: string;
}

/** The pickups in a waiver alert's data, ignoring anything that is not shaped like one. */
export function waiverTargets(alert: AlertItem): WaiverTarget[] {
  const raw = alert.data?.targets;
  if (alert.kind !== "waiver_targets" || !Array.isArray(raw)) return [];
  return raw.filter(
    (t): t is WaiverTarget =>
      typeof t === "object" &&
      t !== null &&
      typeof (t as WaiverTarget).player_id === "string" &&
      typeof (t as WaiverTarget).name === "string" &&
      typeof (t as WaiverTarget).line === "string" &&
      typeof (t as WaiverTarget).projected === "number" &&
      typeof (t as WaiverTarget).gain === "number",
  );
}

export interface AdvicePick {
  player_id: string;
  name: string;
  position?: string | null;
  team?: string | null;
  /** "bench" (already on the team) or "pickup" (available). */
  action: string;
  drop_id?: string | null;
  drop_name?: string | null;
  reason: string;
}

export interface Advice {
  summary: string;
  picks: AdvicePick[];
}

/** The model-written advice stored on an alert, or null when absent or not shaped like advice. */
export function alertAdvice(alert: AlertItem): Advice | null {
  const raw = alert.data?.advice as Partial<Advice> | undefined;
  if (
    !raw ||
    typeof raw !== "object" ||
    typeof raw.summary !== "string" ||
    !Array.isArray(raw.picks)
  ) {
    return null;
  }
  const picks = raw.picks.filter(
    (p): p is AdvicePick =>
      typeof p === "object" &&
      p !== null &&
      typeof (p as AdvicePick).player_id === "string" &&
      typeof (p as AdvicePick).name === "string" &&
      typeof (p as AdvicePick).reason === "string",
  );
  return picks.length > 0 ? { summary: raw.summary, picks } : null;
}

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

/**
 * The alert types a person can choose between, in plain words (keep in step with the detectors
 * in the backend: the ``kind`` is the stored alert's kind).
 */
export const ALERT_TYPES = [
  {
    kind: "injury_out",
    title: "A player on your team is ruled out",
    text: "We say where they start and who to start instead: a healthy bench player, the next player up on their depth chart (even if you own them), or the best free agent. It arrives soon after the app next checks for news.",
  },
  {
    kind: "waiver_targets",
    title: "Waiver targets",
    text: "From 9 am Eastern the day before your league's waiver day: the best available pickups for your lineup, each with its projected points and what it adds over the player it would replace.",
  },
] as const;

/** Things worth knowing that are not a choice. */
export const ALERT_NOTES = [
  {
    title: "AI suggestion",
    text: "When an AI model is connected, a ruled-out or waiver alert also carries a suggested move, labelled as AI.",
  },
  {
    title: "Text messages",
    text: "Not on yet. Alerts are shown here; texting them to your phone is planned.",
  },
] as const;

/** The alert kinds switched off in the viewer's cookie; unknown or malformed values are ignored. */
export function parseOff(raw: string | null | undefined): string[] {
  if (!raw) return [];
  let text = raw;
  try {
    text = decodeURIComponent(raw);
  } catch {
    return [];
  }
  const known: string[] = ALERT_TYPES.map((t) => t.kind);
  return [...new Set(text.split(",").filter((k) => known.includes(k)))];
}

/** The cookie value for a set of switched-off kinds. */
export function serializeOff(off: string[]): string {
  return [...new Set(off)].sort().join(",");
}

/** The alerts the viewer wants: those whose kind they have not switched off. */
export function visibleAlerts(alerts: AlertItem[], off: string[]): AlertItem[] {
  return off.length === 0 ? alerts : alerts.filter((a) => !off.includes(a.kind));
}
