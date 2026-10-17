"use client";

import { useSyncExternalStore } from "react";

import { localDateTime, utcDateTime } from "../lib/time";

const noSubscription = () => () => {};

/**
 * A moment shown in the visitor's own time zone ("Mon, Oct 12, 12:05 PM EDT"). The server and the
 * first render show it in UTC, then the browser swaps in the local time, so the page never
 * disagrees with itself while it loads. The machine-readable time is kept in the element.
 */
export default function LocalTime({ iso }: { iso: string }) {
  const local = useSyncExternalStore(
    noSubscription,
    () => localDateTime(iso),
    () => null,
  );
  const text = local || utcDateTime(iso);
  if (!text) return null;
  return <time dateTime={iso}>{text}</time>;
}
