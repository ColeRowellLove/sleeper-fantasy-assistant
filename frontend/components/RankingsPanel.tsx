"use client";

import { useState } from "react";

import type { Rankings } from "../lib/api";
import { fixed } from "../lib/format";
import {
  RANK_POSITIONS,
  agreementText,
  sourcesQuery,
  rankedFor,
  extraWhy,
  type RankAvailability,
  type RankPosition,
} from "../lib/rankings";
import { ordinal } from "../lib/game";
import GameBadge from "./GameBadge";
import FilterChips from "./FilterChips";
import PlayerIdentity from "./PlayerIdentity";
import StatTable from "./StatTable";
import { leaguePath } from "../lib/league";
import WeekChips from "./WeekChips";
import NoteList from "./NoteList";
import ReasonChips from "./ReasonChips";

const AVAILABILITY: { value: RankAvailability; label: string }[] = [
  { value: "all", label: "All players" },
  { value: "available", label: "Available" },
  { value: "mine", label: "My team" },
];

const number = fixed;

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
  const available = Object.keys(data.signals);
  const selected = data.selected ?? available;
  const labels = selected.map((s) => data.signals[s]);
  const sources = sourcesQuery(selected, available);
  const sourcesParam = sources ? `&sources=${sources}` : "";

  return (
    <section aria-labelledby="rankings-heading">
      <h2 id="rankings-heading">Weekly rankings</h2>
      <p className="note rank-line">
        {data.week ? `Week ${data.week}: ` : ""}ranked by {labels.length}{" "}
        {labels.length === 1 ? "signal" : "signals"}, using this league&apos;s scoring
      </p>
      {data.weeks.length > 0 && (
        <WeekChips
          leagueId={leagueId}
          weeks={data.weeks}
          selected={data.week}
          currentWeek={data.current_week}
          tab="rankings"
          extraQuery={`${sourcesParam}&pos=${position}`}
        />
      )}

      {available.length > 0 && (
        <details className="card rank-fold">
          <summary>Change what the ranks use ({labels.join(", ")})</summary>
          <form method="get" action={leaguePath(leagueId)} className="rank-sources">
            <input type="hidden" name="tab" value="rankings" />
            {data.week !== null && <input type="hidden" name="week" value={data.week} />}
            <input type="hidden" name="pos" value={position} />
            <fieldset>
              <legend>Ranked by</legend>
              <ul className="startsit-picks">
                {available.map((key) => (
                  <li key={key}>
                    <label>
                      <input
                        type="checkbox"
                        name="sources"
                        value={key}
                        defaultChecked={selected.includes(key)}
                      />{" "}
                      {data.signals[key]}
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
            <button type="submit" className="btn" aria-label="Update rankings">
              Update
            </button>
            {data.unavailable && Object.keys(data.unavailable).length > 0 && (
              <details className="rank-missing">
                <summary>Not included yet</summary>
                <p className="note">{Object.values(data.unavailable).join(", ")}.</p>
              </details>
            )}
          </form>
        </details>
      )}

      <div className="players-controls">
        <FilterChips
          label="Position"
          options={RANK_POSITIONS.map((pos) => ({ value: pos, label: pos }))}
          value={position}
          onChange={setPosition}
        />
        <FilterChips
          label="Show"
          options={AVAILABILITY}
          value={availability}
          onChange={setAvailability}
        />
      </div>

      <StatTable
        caption={`${position} rankings for week ${data.week}, best first`}
        className="rankings-table"
        empty={
          rows.length === 0
            ? data.players.length > 0
              ? "No players match these filters."
              : data.week === null
                ? "There is no week to rank yet."
                : `Player projections for week ${data.week} are not in yet. Check back after the next sync.`
            : undefined
        }
      >
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
          </tr>
        </thead>
        <tbody>
          {rows.map((p, i) => {
            const mine = myRosterId !== null && p.owner_roster_id === myRosterId;
            return (
              <tr key={p.player_id} className={mine ? "mine" : undefined}>
                <td className="num">
                  {flex ? (p.flex_rank ?? i + 1) : p.rank}
                  <span
                    className="rank-agree"
                    title={Object.entries(p.signal_ranks)
                      .map(([k, v]) => `${data.signals[k] ?? k}: ${ordinal(v)}`)
                      .join(", ")}
                  >
                    {agreementText(p)}
                  </span>
                </td>
                <th scope="row" className="player-cell">
                  <PlayerIdentity
                    player_id={p.player_id}
                    name={p.name}
                    position={p.position}
                    team={p.team}
                    injury={p.injury}
                    meta={
                      p.owner_team ? (
                        <span className="muted">{mine ? "On your team" : p.owner_team}</span>
                      ) : (
                        <span className="status-available">Available</span>
                      )
                    }
                  >
                    <span className="rank-why">
                      <ReasonChips
                        label={`Why ${p.name} is ranked here`}
                        reasons={extraWhy(p.why).map((label) => ({ label }))}
                      />
                    </span>
                  </PlayerIdentity>
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
              </tr>
            );
          })}
        </tbody>
      </StatTable>
      <details className="rank-about">
        <summary>About these rankings</summary>
        <NoteList
          items={[
            "The consensus is the average of the signals' ranks; rank 1 is best",
            "Projections are Sleeper's, scored with this league's rules",
            "Start % is ESPN-wide and only shown for the current week",
            "A smaller gap between sources means they agree more",
          ]}
        />
      </details>
    </section>
  );
}
