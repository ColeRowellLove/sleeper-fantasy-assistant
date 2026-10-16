"use client";

import { useSyncExternalStore } from "react";

import type { GameInfo, MatchupRank } from "../lib/api";
import { formatKickoff, gameLabel, matchupText } from "../lib/game";

const noSubscription = () => () => {};

/** Whether a player's NFL game is upcoming, live, played, or the team is on a bye. */
export default function GameBadge({
  game,
  matchup,
  position,
}: {
  game?: GameInfo | null;
  /** The opponent's defense rank against the player's position, shown as "(3rd)". */
  matchup?: MatchupRank | null;
  position?: string | null;
}) {
  // The kickoff is shown in the viewer's time zone, which only the browser knows. The server
  // render (and the first client render) shows the date, then the time appears.
  const kickoff = useSyncExternalStore(
    noSubscription,
    () => formatKickoff(game?.kickoff),
    () => null,
  );
  const label = gameLabel(game, kickoff);
  if (!label) return null;
  const rank = label.state === "bye" ? null : matchupText(matchup, position);
  return (
    <span className={`game game-${label.state}`}>
      <span className="game-state">{label.text}</span>
      {label.detail && <span className="game-detail">{label.detail}</span>}
      {rank && (
        <span className="game-rank" title={rank.description}>
          <span aria-hidden="true">({rank.text})</span>
          <span className="visually-hidden">{rank.spoken}</span>
        </span>
      )}
    </span>
  );
}
