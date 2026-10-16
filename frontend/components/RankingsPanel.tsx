"use client";

import { useState } from "react";

import type { Rankings } from "../lib/api";
import {
  RANK_POSITIONS,
  agreementText,
  rankedFor,
  type RankAvailability,
  type RankPosition,
} from "../lib/rankings";
import { ordinal } from "../lib/game";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PlayerLink from "./PlayerLink";
import PositionChip from "./PositionChip";
import TeamLink from "./TeamLink";
import WeekChips from "./WeekChips";

const AVAILABILITY: { value: RankAvailability; label: string }[] = [
  { value: "all", label: "All players" },
  { value: "available", label: "Available" },
  { value: "mine", label: "My team" },
];

const number = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined ? "–" : n.toFixed(digits);

/**
 * Weekly rankings by position: the consensus of several signals, with the numbers behind each
 * rank and how far apart the signals are. Pick a position, a week, and who to include.
 */
export default function RankingsPanel({
  data,
  leagueId,
  myRosterId,
  initialPosition = "RB",
}: {
  data: Rankings;
  leagueId: string;
  myRosterId: number | null;
  initialPosition?: RankPosition;
}) {
  const [position, setPosition] = useState<RankPosition>(initialPosition);
  const [availability, setAvailability] = useState<RankAvailability>("all");
  const rows = rankedFor(data.players, position, availability, myRosterId);
  const flex = position === "FLEX";
  const labels = Object.values(data.signals);

  return (
    <section aria-labelledby="rankings-heading">
      <h2 id="rankings-heading">Weekly rankings</h2>
      <p className="note">
        {data.week ? `Week ${data.week}. ` : ""}Each player is ranked by {labels.join(", ")} and the
        consensus is the average of those ranks, using this league&apos;s scoring. Rank 1 is best.
      </p>
      {data.weeks.length > 0 && (
        <WeekChips
          leagueId={leagueId}
          weeks={data.weeks}
          selected={data.week}
          currentWeek={data.current_week}
          tab="rankings"
        />
      )}

      <div className="players-controls">
        <div className="players-filter" role="group" aria-label="Position">
          {RANK_POSITIONS.map((pos) => (
            <button
              key={pos}
              type="button"
              className="filter-chip"
              aria-pressed={pos === position}
              onClick={() => setPosition(pos)}
            >
              {pos}
            </button>
          ))}
        </div>
        <div className="players-filter" role="group" aria-label="Show">
          {AVAILABILITY.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className="filter-chip"
              aria-pressed={value === availability}
              onClick={() => setAvailability(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="card flush">
        <div className="players-scroll">
          <table className="players rankings-table">
            <caption className="visually-hidden">
              {position} rankings for week {data.week}, best first
            </caption>
            <thead>
              <tr>
                <th scope="col" className="num">
                  Rank
                </th>
                <th scope="col">Player</th>
                <th scope="col">Opponent</th>
                <th scope="col" className="num">
                  Proj
                </th>
                <th scope="col" className="num">
                  Last 3 avg
                </th>
                <th scope="col" className="num">
                  ESPN start %
                </th>
                <th scope="col">Sources</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p, i) => {
                const mine = myRosterId !== null && p.owner_roster_id === myRosterId;
                return (
                  <tr key={p.player_id} className={mine ? "mine" : undefined}>
                    <td className="num">{flex ? (p.flex_rank ?? i + 1) : p.rank}</td>
                    <th scope="row" className="player-cell">
                      <span className="player-line">
                        <PlayerAvatar
                          player_id={p.player_id}
                          name={p.name}
                          position={p.position}
                          team={p.team}
                        />
                        <span className="player-text">
                          <span className="player-name">
                            <PlayerLink playerId={p.player_id}>{p.name}</PlayerLink>
                          </span>
                          <span className="player-meta">
                            <PositionChip position={p.position} />
                            <span className="muted">
                              {p.team ? <TeamLink team={p.team}>{p.team}</TeamLink> : "FA"}
                            </span>
                            <InjuryBadge injury={p.injury} />
                            {p.owner_team ? (
                              <span className="muted">{mine ? "On your team" : p.owner_team}</span>
                            ) : (
                              <span className="status-available">Available</span>
                            )}
                          </span>
                          <span className="player-meta rank-why">{p.why}</span>
                        </span>
                      </span>
                    </th>
                    <td>
                      <GameBadge game={p.game} matchup={p.matchup} position={p.position} />
                    </td>
                    <td className="num">{number(p.projected)}</td>
                    <td className="num">{number(p.form)}</td>
                    <td className="num">
                      {p.started_pct === null || p.started_pct === undefined
                        ? "–"
                        : `${p.started_pct.toFixed(0)}%`}
                    </td>
                    <td>
                      <span
                        title={Object.entries(p.signal_ranks)
                          .map(([k, v]) => `${data.signals[k] ?? k}: ${ordinal(v)}`)
                          .join(", ")}
                      >
                        {agreementText(p)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {rows.length === 0 && <p className="note players-empty">No players match these filters.</p>}
      </div>
      <p className="note">
        Projections are Sleeper&apos;s, scored with this league&apos;s rules. Start % is ESPN-wide
        and only shown for the current week. A smaller gap between sources means they agree more.
      </p>
    </section>
  );
}
