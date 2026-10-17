/**
 * Times in the visitor's own time zone. Only the browser knows the zone, so these are called
 * from a client component after the page has loaded; the server and the first render use the UTC
 * text (utcDateTime) so both print the same thing and nothing flickers into a mismatch.
 */

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

const FIELDS = {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
} as const;

/** "Mon, Oct 12, 4:05 PM UTC": the same text on the server and in the browser. */
export function utcDateTime(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return "";
  return `${date.toLocaleString("en-US", { ...FIELDS, timeZone: "UTC" })} UTC`;
}

/** "Mon, Oct 12, 12:05 PM EDT": the viewer's zone, named. Browser only. */
export function localDateTime(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return "";
  return date.toLocaleString(undefined, { ...FIELDS, timeZoneName: "short" });
}

/** "12:05 PM": the time of day in the viewer's zone. Browser only. */
export function localTime(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return "";
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
