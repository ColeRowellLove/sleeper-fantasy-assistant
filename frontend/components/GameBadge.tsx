"use client";

import { useSyncExternalStore } from "react";

import type { GameInfo } from "../lib/api";
import { formatKickoff, gameLabel } from "../lib/game";

const noSubscription = () => () => {};

/** Whether a player's NFL game is upcoming, live, played, or the team is on a bye. */
export default function GameBadge({ game }: { game?: GameInfo | null }) {
  // The kickoff is shown in the viewer's time zone, which only the browser knows. The server
  // render (and the first client render) shows the date, then the time appears.
  const kickoff = useSyncExternalStore(
    noSubscription,
    () => formatKickoff(game?.kickoff),
    () => null,
  );
  const label = gameLabel(game, kickoff);
  if (!label) return null;
  return (
    <span className={`game game-${label.state}`}>
      <span className="game-state">{label.text}</span>
      {label.detail && <span className="game-detail">{label.detail}</span>}
    </span>
  );
}
