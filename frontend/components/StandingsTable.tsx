"use client";

import { useState } from "react";

import type { StandingsRow } from "../lib/api";
import { formatRecord } from "../lib/league";
import {
  DEFAULT_SORT,
  nextSort,
  sortStandings,
  type SortKey,
  type SortState,
} from "../lib/standingsSort";

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "rank", label: "Rank" },
  { key: "team", label: "Team" },
  { key: "record", label: "Record" },
  { key: "points_for", label: "PF", numeric: true },
  { key: "points_against", label: "PA", numeric: true },
];

function describe(sort: SortState): string {
  const column = COLUMNS.find((c) => c.key === sort.key)?.label ?? "";
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
}: {
  standings: StandingsRow[];
  playoffTeams: number | null;
  myRosterId: number | null;
}) {
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);
  const rows = sortStandings(standings, sort);

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
              {COLUMNS.map(({ key, label, numeric }) => {
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
              const inPlayoffs = playoffTeams !== null && row.rank <= playoffTeams;
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
                    {row.team}
                    {mine && <span className="you">You</span>}
                  </th>
                  <td className="num">{formatRecord(row.wins, row.losses, row.ties)}</td>
                  <td className="num num-col">{row.points_for.toFixed(2)}</td>
                  <td className="num num-col">{row.points_against.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="visually-hidden" role="status">
        {describe(sort)}
      </p>
      {playoffTeams !== null && (
        <p className="note">
          The top {playoffTeams} teams make the playoffs (marked with a bar and a line below
          {` #${playoffTeams}`}).
        </p>
      )}
    </section>
  );
}
