"use client";

import Link from "next/link";
import { useState } from "react";

import { fixed, fractionPercent } from "../lib/format";
import type { StandingsRow } from "../lib/api";
import { formatRecord, rosterPath } from "../lib/league";
import NoteList from "./NoteList";
import {
  DEFAULT_SORT,
  nextSort,
  parseStreak,
  sortStandings,
  type SortKey,
  type SortState,
} from "../lib/standingsSort";

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "rank", label: "Rank" },
  { key: "team", label: "Team" },
  { key: "record", label: "Record" },
  { key: "streak", label: "Streak" },
  { key: "points_for", label: "PF", numeric: true },
  { key: "points_against", label: "PA", numeric: true },
];

// Sleeper's own season totals, shown only when it reports potential points for the league
const ACCURACY_COLUMNS: typeof COLUMNS = [
  { key: "accuracy", label: "Accuracy", numeric: true },
  { key: "left_on_bench", label: "Bench pts", numeric: true },
];
const ALL_COLUMNS = [...COLUMNS, ...ACCURACY_COLUMNS];

const percent = fractionPercent;
const points = fixed;

function StreakBadge({ streak }: { streak: string | null | undefined }) {
  const parsed = parseStreak(streak);
  if (!parsed) return <span className="streak streak-none">&ndash;</span>;
  const [one, many] = {
    W: ["win", "wins"],
    L: ["loss", "losses"],
    T: ["tie", "ties"],
  }[parsed.kind];
  return (
    <span className={`streak streak-${parsed.kind}`}>
      <span aria-hidden="true">
        {parsed.kind}
        {parsed.length}
      </span>
      <span className="visually-hidden">
        {parsed.length} {parsed.length === 1 ? one : many} in a row
      </span>
    </span>
  );
}

function describe(sort: SortState): string {
  const column = ALL_COLUMNS.find((c) => c.key === sort.key)?.label ?? "";
  const how =
    sort.key === "team"
      ? sort.direction === "asc"
        ? "A to Z"
        : "Z to A"
      : sort.direction === "asc"
        ? "low to high"
        : "high to low";
  return `Sorted by ${column}, ${how}`;
}

export default function StandingsTable({
  standings,
  playoffTeams,
  myRosterId,
  leagueId,
}: {
  standings: StandingsRow[];
  playoffTeams: number | null;
  myRosterId: number | null;
  /** When given, each team name links to that team's roster. */
  leagueId?: string;
}) {
  const [chosen, setSort] = useState<SortState>(DEFAULT_SORT);
  const showAccuracy = standings.some((r) => r.accuracy !== null && r.accuracy !== undefined);
  const columns = showAccuracy ? ALL_COLUMNS : COLUMNS;
  // a sort on a column that is no longer shown (the accuracy data went away) falls back to rank
  const sort = columns.some((c) => c.key === chosen.key) ? chosen : DEFAULT_SORT;
  const rows = sortStandings(standings, sort);
  // the playoff bar only means something while the table runs from first place down
  const showPlayoffs = playoffTeams !== null && sort.key === "rank" && sort.direction === "asc";

  return (
    <section aria-labelledby="standings-heading">
      <h2 id="standings-heading" className="visually-hidden">
        Standings
      </h2>
      <div className="card flush">
        <table className="standings">
          <caption className="visually-hidden">
            League standings. Use the column buttons to sort.
          </caption>
          <thead>
            <tr>
              {columns.map(({ key, label, numeric }) => {
                const active = sort.key === key;
                return (
                  <th
                    key={key}
                    scope="col"
                    className={numeric ? "num-col" : undefined}
                    aria-sort={
                      active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"
                    }
                  >
                    <button
                      type="button"
                      className="sort-button"
                      onClick={() => setSort((current) => nextSort(current, key))}
                    >
                      {label}
                      <span className="sort-arrow" aria-hidden="true">
                        {active ? (sort.direction === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const mine = row.roster_id === myRosterId;
              const inPlayoffs = showPlayoffs && row.rank <= playoffTeams;
              const classes = [
                mine ? "mine" : "",
                inPlayoffs ? "playoff" : "",
                inPlayoffs && row.rank === playoffTeams ? "cutoff" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <tr
                  key={row.roster_id}
                  className={classes || undefined}
                  aria-current={mine ? "true" : undefined}
                >
                  <td className="rank num">
                    {row.rank}
                    {inPlayoffs && <span className="visually-hidden"> (playoff position)</span>}
                  </td>
                  <th scope="row">
                    {leagueId ? (
                      <Link href={rosterPath(leagueId, row.roster_id)} className="member-link">
                        {row.team}
                      </Link>
                    ) : (
                      row.team
                    )}
                    {mine && <span className="you">You</span>}
                    {row.manager && row.manager !== row.team && (
                      <span className="manager">
                        <span className="visually-hidden">Manager: </span>
                        {row.manager}
                      </span>
                    )}
                  </th>
                  <td className="num">{formatRecord(row.wins, row.losses, row.ties)}</td>
                  <td className="num">
                    <StreakBadge streak={row.streak} />
                  </td>
                  <td className="num num-col">{row.points_for.toFixed(2)}</td>
                  <td className="num num-col">{row.points_against.toFixed(2)}</td>
                  {showAccuracy && (
                    <>
                      <td className="num num-col">{percent(row.accuracy)}</td>
                      <td className="num num-col">{points(row.left_on_bench)}</td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="visually-hidden" role="status">
        {describe(sort)}
      </p>
      {showAccuracy && (
        <NoteList
          items={[
            "Accuracy is the points a team scored divided by its potential points (what its best lineups would have scored)",
            "100% means the best lineup every week",
            "Bench pts is what was left on the bench",
          ]}
        />
      )}
      {showPlayoffs && (
        <p className="note">
          The top {playoffTeams} teams make the playoffs (marked with a bar and a line below
          {` #${playoffTeams}`}).
        </p>
      )}
    </section>
  );
}
