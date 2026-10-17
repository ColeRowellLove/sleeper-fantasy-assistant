"use client";

import { useSyncExternalStore } from "react";

import type { GameInfo, MatchupRank } from "../lib/api";
import { formatKickoffShort, gameLineParts, matchupText, weatherIcon } from "../lib/game";

const noSubscription = () => () => {};

/**
 * A player's game as one short line, the way Sleeper words it: "Mon 5:15 PM @ SF". The opponent's
 * code is coloured by how hard the matchup is (green easy, red tough) with the word for a screen
 * reader, and a small icon appears only for notable weather. Used wherever a row has room for one
 * line; the Games screen keeps the full detail.
 */
export default function GameLine({
  game,
  matchup,
  position,
}: {
  game?: GameInfo | null;
  matchup?: MatchupRank | null;
  position?: string | null;
}) {
  // the kickoff is shown in the viewer's time zone, which only the browser knows
  const kickoff = useSyncExternalStore(
    noSubscription,
    () => formatKickoffShort(game?.kickoff),
    () => null,
  );
  const parts = gameLineParts(game, kickoff);
  if (!parts) return null;
  const difficulty = parts.state === "bye" ? null : matchupText(matchup, position);
  const weather = weatherIcon(game);
  return (
    <span className={`game-line game-line-${parts.state}`}>
      <span className="gl-time">{parts.time}</span>
      {parts.score && <span className="gl-score">{parts.score}</span>}
      {parts.versus && parts.opponent && (
        <span className="gl-versus">
          {parts.versus}{" "}
          <span
            className={`gl-opponent${difficulty ? ` diff-${difficulty.difficulty}` : ""}`}
            title={difficulty?.description}
          >
            {parts.opponent}
          </span>
          {difficulty && <span className="visually-hidden"> ({difficulty.spoken})</span>}
        </span>
      )}
      {weather && (
        <span role="img" aria-label={weather.label} title={weather.label} className="gl-weather">
          {weather.icon}
        </span>
      )}
    </span>
  );
}
