"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/** How often a page with a live game asks the server for fresh data. */
export const REFRESH_SECONDS = 15;

/**
 * Keeps a page current while a game is on: every few seconds it asks Next to re-render the page's
 * data in place (no reload, so scroll position and open sections stay). It does nothing when no
 * game is live, waits while the tab is hidden and catches up the moment it is shown again.
 *
 * Auto-updating content must be stoppable (WCAG 2.2.2), so there is a Pause button. The status
 * line is a plain paragraph, not a live region, so a screen reader is not interrupted every tick.
 */
export default function LiveRefresh({
  active,
  seconds = REFRESH_SECONDS,
}: {
  active: boolean;
  seconds?: number;
}) {
  const router = useRouter();
  const [paused, setPaused] = useState(false);
  const [updated, setUpdated] = useState<string | null>(null);
  const refresh = useRef(() => {});

  useEffect(() => {
    refresh.current = () => {
      router.refresh();
      setUpdated(new Date().toLocaleTimeString());
    };
  }, [router]);

  useEffect(() => {
    if (!active || paused) return;
    const tick = () => {
      if (!document.hidden) refresh.current();
    };
    const onVisible = () => {
      if (!document.hidden) refresh.current();
    };
    const timer = window.setInterval(tick, seconds * 1000);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [active, paused, seconds]);

  if (!active) return null;
  return (
    <p className="live-refresh">
      <span className="live-dot" aria-hidden="true" />
      {paused ? "Live updates paused." : `Live: updating every ${seconds} seconds.`}
      {updated && !paused && <span className="muted"> Last update {updated}.</span>}{" "}
      <button type="button" className="btn btn-quiet" onClick={() => setPaused((p) => !p)}>
        {paused ? "Resume live updates" : "Pause live updates"}
      </button>
    </p>
  );
}
