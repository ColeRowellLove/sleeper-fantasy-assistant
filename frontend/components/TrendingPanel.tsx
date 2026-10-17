"use client";

import { useState } from "react";

import type { PlayersData } from "../lib/api";
import {
  DIRECTIONS,
  POSITION_OPTIONS,
  formatTrendCount,
  trendRows,
  type TrendPosition,
  type TrendDirection,
} from "../lib/trending";
import { fixed, percentWhole } from "../lib/format";
import FilterChips from "./FilterChips";
import GameLine from "./GameLine";
import NoteList from "./NoteList";
import PlayerIdentity from "./PlayerIdentity";

/**
 * Sleeper's 24-hour trending adds or drops as a ranked list, like theirs: rank, the player, his
 * game, and how many leagues added or dropped him with a small bar, then ESPN's rostered share,
 * last week's points and this week's projection on one line.
 */
export default function TrendingPanel({ data }: { data: PlayersData }) {
  const [direction, setDirection] = useState<TrendDirection>("adds");
  const [position, setPosition] = useState<TrendPosition>("ALL");
  const rows = trendRows(data.players, direction, position);
  const week = data.week;
  const hasTrends = data.players.some((p) => p.adds || p.drops);
  return (
    <section aria-labelledby="trending-heading" className="trending">
      <div className="trend-head">
        <h2 id="trending-heading">Trending</h2>
        <FilterChips label="Trend" options={DIRECTIONS} value={direction} onChange={setDirection} />
      </div>
      <div className="trend-positions">
        <FilterChips
          label="Position"
          options={POSITION_OPTIONS}
          value={position}
          onChange={setPosition}
        />
      </div>
      {!hasTrends ? (
        <p className="note">Sleeper&apos;s trending numbers have not loaded yet. Try again soon.</p>
      ) : rows.length === 0 ? (
        <p className="note">Nobody is trending at that position right now.</p>
      ) : (
        <ol className="trend-list">
          {rows.map(({ player, rank, count, share }) => (
            <li key={player.player_id} className="trend-row">
              <span className="trend-rank num">{rank}</span>
              <div className="trend-main">
                <PlayerIdentity
                  player_id={player.player_id}
                  name={player.name}
                  position={player.position}
                  team={player.team}
                  injury={player.injury}
                >
                  <GameLine game={player.game} position={player.position} />
                </PlayerIdentity>
                <dl className="trend-stats">
                  <div>
                    <dt>Rostered</dt>
                    <dd>{percentWhole(player.owned_pct)}</dd>
                  </div>
                  <div>
                    <dt>{week && week > 1 ? `Wk ${week - 1} pts` : "Last wk"}</dt>
                    <dd>{fixed(player.last_points)}</dd>
                  </div>
                  <div>
                    <dt>{week ? `Wk ${week} proj` : "Proj"}</dt>
                    <dd>{fixed(player.projected)}</dd>
                  </div>
                </dl>
              </div>
              <div className={`trend-count trend-${direction}`}>
                <strong className="num" aria-hidden="true">
                  {formatTrendCount(count, direction)}
                </strong>
                <span className="trend-bar" aria-hidden="true">
                  <span style={{ width: `${share}%` }} />
                </span>
                <span className="visually-hidden">
                  {count.toLocaleString("en-US")} {direction} in 24 hours
                </span>
                <span className="trend-owner muted">
                  {player.owner_team ? `On ${player.owner_team}` : "Available"}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
      <details className="trend-about">
        <summary>About these numbers</summary>
        <NoteList
          items={[
            "Sleeper's adds and drops across all leagues in the last 24 hours",
            "Rostered is ESPN's share of leagues; points and projection use this league's scoring",
          ]}
        />
      </details>
    </section>
  );
}
