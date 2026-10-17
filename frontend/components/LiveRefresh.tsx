"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/** How often a page with a live game asks the server for fresh data. */
export const REFRESH_SECONDS = 15;

/**
 * Keeps a page current while a game is on: every few seconds it asks Next to re-render the page's
 * data in place (no reload, so scroll position and open sections stay). It does nothing when no
 * game is live, waits while the tab is hidden and catches up the moment it is shown again.
 *
 * It is always on while a game is live (live scores are the point of the page). It never moves
 * focus or scroll and the status line is a plain paragraph, not a live region, so a screen reader
 * is not interrupted every tick.
 */
export default function LiveRefresh({
  active,
  seconds = REFRESH_SECONDS,
}: {
  active: boolean;
  seconds?: number;
}) {
  const router = useRouter();
  const [updated, setUpdated] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    let last = Date.now();
    const refresh = () => {
      // a tick right after a catch-up refresh (or the other way round) would double the request
      if (document.hidden || Date.now() - last < (seconds * 1000) / 2) return;
      last = Date.now();
      router.refresh();
      setUpdated(new Date().toLocaleTimeString());
    };
    const timer = window.setInterval(refresh, seconds * 1000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [active, seconds, router]);

  if (!active) return null;
  return (
    <p className="live-refresh">
      <span className="live-dot" aria-hidden="true" />
      <strong>Live</strong>
      <span className="visually-hidden">: updating every {seconds} seconds.</span>
      {updated && <span className="muted">Updated {updated}</span>}
    </p>
  );
}
