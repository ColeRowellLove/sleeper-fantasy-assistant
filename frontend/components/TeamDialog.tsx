"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import type { TeamDepth } from "../lib/api";
import TeamDepthChart from "./TeamDepthChart";

/**
 * A team's depth chart as a pop-up, opened from any team code in the app. A native dialog, so focus
 * stays inside and Escape closes it; closing goes back to the same page without ?depth.
 */
export default function TeamDialog({
  data,
  closeHref,
  myRosterId,
}: {
  data: TeamDepth;
  closeHref: string;
  myRosterId: number | null;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const router = useRouter();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    closeButton.current?.focus(); // start on Close so keyboard and screen-reader users land inside
  }, []);

  return (
    <dialog
      ref={ref}
      className="player-dialog team-dialog"
      aria-labelledby="team-dialog-title"
      onClose={() => router.replace(closeHref, { scroll: false })}
      onClick={(event) => {
        if (event.target === event.currentTarget) ref.current?.close();
      }}
    >
      <div className="player-dialog-body">
        <div className="team-dialog-bar">
          <button
            type="button"
            className="btn btn-quiet player-dialog-close"
            onClick={() => ref.current?.close()}
            ref={closeButton}
          >
            Close
          </button>
        </div>
        <TeamDepthChart
          data={data}
          myRosterId={myRosterId}
          headingId="team-dialog-title"
          landmark={false}
        />
      </div>
    </dialog>
  );
}
