"use client";

import { useState } from "react";

import type { PlayersData } from "../lib/api";
import {
  DEFAULT_FILTERS,
  DEFAULT_SORT,
  POSITION_FILTERS,
  describeSort,
  filterPlayers,
  nextSort,
  sortPlayers,
  type Availability,
  type PlayerFilters,
  type PlayerSort,
  type PositionFilter,
  type SortKey,
} from "../lib/playersFilter";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PlayerLink from "./PlayerLink";
import PositionChip from "./PositionChip";

const PAGE = 50;

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "name", label: "Player" },
  { key: "status", label: "Status" },
  { key: "adds", label: "Adds", numeric: true },
  { key: "drops", label: "Drops", numeric: true },
  { key: "rank", label: "Rank", numeric: true },
  { key: "total", label: "Points", numeric: true },
  { key: "projected", label: "Proj", numeric: true },
];

const AVAILABILITY: { value: Availability; label: string }[] = [
  { value: "all", label: "All players" },
  { value: "available", label: "Available" },
  { value: "rostered", label: "Rostered" },
];

const count = (n: number | null) => (n === null ? "–" : n.toLocaleString("en-US"));

/** Every relevant NFL player through this league: filter, search and sort by the numbers that matter. */
export default function PlayersTable({
  data,
  myRosterId,
}: {
  data: PlayersData;
  myRosterId: number | null;
}) {
  const [filters, setFilters] = useState<PlayerFilters>(DEFAULT_FILTERS);
  const [sort, setSort] = useState<PlayerSort>(DEFAULT_SORT);
  const [shown, setShown] = useState(PAGE);

  const rows = sortPlayers(filterPlayers(data.players, filters), sort);
  const visible = rows.slice(0, shown);
  const update = (change: Partial<PlayerFilters>) => {
    setFilters((current) => ({ ...current, ...change }));
    setShown(PAGE); // a new filter starts again from the top of the list
  };

  return (
    <section aria-labelledby="players-heading">
      <h2 id="players-heading" className="visually-hidden">
        Players
      </h2>

      <div className="players-controls">
        <label className="players-search">
          <span className="visually-hidden">Search players by name or team</span>
          <input
            type="search"
            value={filters.search}
            placeholder="Search players"
            onChange={(event) => update({ search: event.target.value })}
          />
        </label>

        <div className="players-filter" role="group" aria-label="Position">
          {(["ALL", ...POSITION_FILTERS, "FLEX"] as PositionFilter[]).map((position) => (
            <button
              key={position}
              type="button"
              className="filter-chip"
              aria-pressed={filters.position === position}
              onClick={() => update({ position })}
            >
              {position === "ALL" ? "All" : position}
            </button>
          ))}
        </div>

        <div className="players-filter" role="group" aria-label="Availability">
          {AVAILABILITY.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className="filter-chip"
              aria-pressed={filters.availability === value}
              onClick={() => update({ availability: value })}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="card flush">
        <div className="players-scroll">
          <table className="players">
            <caption className="visually-hidden">
              Players in this league. Use the column buttons to sort.
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
              {visible.map((p) => {
                const mine = myRosterId !== null && p.owner_roster_id === myRosterId;
                return (
                  <tr key={p.player_id} className={mine ? "mine" : undefined}>
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
                            <span className="muted">{p.team ?? "FA"}</span>
                            <InjuryBadge injury={p.injury} />
                            <GameBadge game={p.game} />
                          </span>
                        </span>
                      </span>
                    </th>
                    <td className="status-cell">
                      {p.owner_team === null ? (
                        <span className="status-available">Available</span>
                      ) : (
                        <span className="status-owned">
                          {p.owner_team}
                          {mine && <span className="you">You</span>}
                        </span>
                      )}
                    </td>
                    <td className="num num-col">{count(p.adds)}</td>
                    <td className="num num-col">{count(p.drops)}</td>
                    <td className="num num-col">{p.rank === null ? "–" : `${p.position}${p.rank}`}</td>
                    <td className="num num-col">{p.total_points.toFixed(1)}</td>
                    <td className="num num-col">
                      {p.projected === null ? "–" : p.projected.toFixed(1)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {rows.length === 0 && <p className="note players-empty">No players match these filters.</p>}
      </div>

      <p className="visually-hidden" role="status">
        {describeSort(sort)}. Showing {visible.length} of {rows.length} players.
      </p>
      <p className="note">
        Showing {visible.length} of {rows.length} players. Adds and drops are Sleeper&apos;s top 100
        over the last 24 hours; a dash means not on that list. Points are this season under this
        league&apos;s scoring.
      </p>
      {visible.length < rows.length && (
        <button type="button" className="btn btn-quiet" onClick={() => setShown((n) => n + PAGE)}>
          Show more players
        </button>
      )}
    </section>
  );
}
