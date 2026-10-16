"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { PlayerDetail } from "../lib/api";
import {
  bioRows,
  describeStats,
  formatStat,
  rankText,
  statColumns,
  statTotals,
} from "../lib/playerDetail";
import { rosterPath } from "../lib/league";
import { projectionDelta } from "../lib/lineups";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PositionChip from "./PositionChip";
import TeamLink from "./TeamLink";
import TeamStatsTable from "./TeamStatsTable";

type PastSeason = NonNullable<PlayerDetail["past_seasons"]>[number];

/** One past season's summary row, and (when opened) a game-by-game table under it. */
function PastSeasonRows({
  season,
  position,
  open,
  onToggle,
}: {
  season: PastSeason;
  position: string | null;
  open: boolean;
  onToggle: () => void;
}) {
  const log = season.log ?? [];
  const columns = statColumns(
    log.map((g) => g.stats),
    position,
  );
  const totals = statTotals(log.map((g) => g.stats));
  const panelId = `season-${season.season}-games`;
  return (
    <>
      <tr>
        <th scope="row">
          {log.length > 0 ? (
            <button
              type="button"
              className="season-toggle"
              aria-expanded={open}
              aria-controls={panelId}
              onClick={onToggle}
            >
              <span aria-hidden="true">{open ? "▾" : "▸"}</span> {season.season}
              <span className="visually-hidden"> game by game</span>
            </button>
          ) : (
            season.season
          )}
        </th>
        <td>
          {(season.teams ?? []).length === 0
            ? "–"
            : (season.teams ?? []).map((team, i) => (
                <span key={team}>
                  {i > 0 && ", "}
                  <TeamLink team={team}>{team}</TeamLink>
                </span>
              ))}
        </td>
        <td className="num num-col">{season.games}</td>
        <td className="num num-col">{season.points.toFixed(1)}</td>
        <td className="num num-col">{rankText(position, season.rank)}</td>
      </tr>
      {open && (
        <tr id={panelId}>
          <td colSpan={5} className="season-log">
            <div className="players-scroll">
              <table className="players pd-table pd-stats-table">
                <caption className="visually-hidden">
                  {season.season} game by game, with season totals
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Week</th>
                    <th scope="col">Team</th>
                    <th scope="col">Opponent</th>
                    <th scope="col" className="num-col">
                      Points
                    </th>
                    {columns.map((c) => (
                      <th key={c.key} scope="col" className="num-col">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {log.map((g) => (
                    <tr key={g.week}>
                      <th scope="row">{g.week}</th>
                      <td>{g.team ?? "–"}</td>
                      <td>
                        {g.opponent ? `${g.home === false ? "at" : "vs"} ${g.opponent}` : "–"}
                      </td>
                      <td className="num num-col">{g.points.toFixed(1)}</td>
                      {columns.map((c) => (
                        <td key={c.key} className="num num-col">
                          {formatStat(g.stats[c.key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={3}>
                      Season total
                    </th>
                    <td className="num num-col">{season.points.toFixed(1)}</td>
                    {columns.map((c) => (
                      <td key={c.key} className="num num-col">
                        {formatStat(totals[c.key])}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

const percent = (n: number | null | undefined) =>
  n === null || n === undefined ? "–" : `${n.toFixed(1)}%`;

const count = (n: number | null | undefined) =>
  n === null || n === undefined ? "–" : n.toLocaleString("en-US");

/**
 * One player's pop-up: who they are, where they rank this season, what they scored each week and
 * what is projected. A native dialog, so focus stays inside, Escape closes it and focus returns to
 * the link that opened it. Closing goes back to the same page without ?player.
 */
export default function PlayerDialog({
  detail,
  closeHref,
}: {
  detail: PlayerDetail;
  closeHref: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [openSeason, setOpenSeason] = useState<string | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const router = useRouter();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    closeButton.current?.focus(); // start on Close so keyboard and screen-reader users land inside
  }, []);

  const close = () => router.replace(closeHref, { scroll: false });
  const bio = bioRows(detail.bio);
  const rank = rankText(detail.position, detail.season.rank);
  const weekStats = detail.weeks.map((w) => w.stats);
  const columns = statColumns(
    [...weekStats, ...(detail.projected ? [detail.projected.stats] : [])],
    detail.position,
  );
  const totals = statTotals(weekStats);
  // the projection columns only appear once at least one week has a stored projection
  const showProjections = detail.weeks.some(
    (w) => w.projected !== null && w.projected !== undefined,
  );
  const allProjected =
    detail.weeks.length > 0 &&
    detail.weeks.every((w) => w.projected !== null && w.projected !== undefined);
  const projectedTotal = detail.weeks.reduce((sum, w) => sum + (w.projected ?? 0), 0);

  return (
    <dialog
      ref={ref}
      className="player-dialog"
      aria-labelledby="player-dialog-title"
      onClose={close}
      onClick={(event) => {
        // a click on the backdrop (the dialog element itself) closes it
        if (event.target === event.currentTarget) ref.current?.close();
      }}
    >
      <div className="player-dialog-body">
        <header className="player-dialog-head">
          <PlayerAvatar
            player_id={detail.player_id}
            name={detail.name}
            position={detail.position}
            team={detail.team}
            priority
          />
          <div className="player-dialog-title">
            <h2 id="player-dialog-title">{detail.name}</h2>
            <p className="player-dialog-meta">
              <PositionChip position={detail.position} />
              {detail.team ? (
                <TeamLink team={detail.team}>{detail.team} depth chart</TeamLink>
              ) : (
                <span className="muted">Free agent</span>
              )}
              <InjuryBadge injury={detail.injury} />
              <GameBadge game={detail.game} matchup={detail.matchup} position={detail.position} />
            </p>
            <p className="player-dialog-owner">
              {detail.owner_team === null || detail.owner_team === undefined ? (
                <span className="status-available">Available in this league</span>
              ) : (
                <span className="status-owned">
                  On{" "}
                  {detail.league_id && detail.owner_roster_id != null ? (
                    <Link
                      href={rosterPath(detail.league_id, detail.owner_roster_id)}
                      className="member-link"
                    >
                      {detail.owner_team}
                    </Link>
                  ) : (
                    detail.owner_team
                  )}
                  {detail.owner_manager && detail.owner_manager !== detail.owner_team
                    ? ` (${detail.owner_manager})`
                    : ""}
                </span>
              )}
            </p>
          </div>
          <button
            type="button"
            className="btn btn-quiet player-dialog-close"
            onClick={() => ref.current?.close()}
            ref={closeButton}
          >
            Close
          </button>
        </header>

        {bio.length > 0 && (
          <section aria-labelledby="pd-bio">
            <h3 id="pd-bio">Bio</h3>
            <dl className="setting-rows">
              {bio.map((row) => (
                <div key={row.label} className="setting-row">
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        <section aria-labelledby="pd-season">
          <h3 id="pd-season">This season</h3>
          <dl className="setting-rows">
            <div className="setting-row">
              <dt>Position rank</dt>
              <dd>{rank}</dd>
            </div>
            <div className="setting-row">
              <dt>Points</dt>
              <dd>{detail.season.points.toFixed(1)}</dd>
            </div>
            <div className="setting-row">
              <dt>Games</dt>
              <dd>{detail.season.games}</dd>
            </div>
            <div className="setting-row">
              <dt>Points per game</dt>
              <dd>
                {detail.season.average === null || detail.season.average === undefined
                  ? "–"
                  : detail.season.average.toFixed(1)}
              </dd>
            </div>
            <div className="setting-row">
              <dt>Owned % (ESPN)</dt>
              <dd>{percent(detail.owned_pct)}</dd>
            </div>
            <div className="setting-row">
              <dt>Started % (ESPN)</dt>
              <dd>{percent(detail.started_pct)}</dd>
            </div>
            <div className="setting-row">
              <dt>Sleeper adds, last 24 hours</dt>
              <dd>{count(detail.adds)}</dd>
            </div>
            <div className="setting-row">
              <dt>Sleeper drops, last 24 hours</dt>
              <dd>{count(detail.drops)}</dd>
            </div>
          </dl>
          <p className="note">Points use this league&apos;s scoring, and every stat counts.</p>
        </section>

        {detail.projected && (
          <section aria-labelledby="pd-proj">
            <h3 id="pd-proj">Projected, week {detail.projected.week}</h3>
            <p className="pd-projected">
              <strong>{detail.projected.points.toFixed(1)}</strong> points
            </p>
            <p className="note">{describeStats(detail.projected.stats, detail.position)}</p>
          </section>
        )}

        {detail.team && detail.team_stats && (
          <TeamStatsTable
            stats={detail.team_stats}
            team={detail.team}
            headingId="pd-team-stats"
            title={`${detail.team} team stats`}
          />
        )}

        <section aria-labelledby="pd-weeks">
          <h3 id="pd-weeks">Week by week</h3>
          {detail.weeks.length === 0 ? (
            <p className="note">No games played yet this season.</p>
          ) : (
            <div className="players-scroll">
              <table className="players pd-table pd-stats-table">
                <caption className="visually-hidden">
                  Points and stats by week this season, with season totals
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Week</th>
                    <th scope="col">Team</th>
                    <th scope="col">Opponent</th>
                    <th scope="col" className="num-col">
                      Points
                    </th>
                    {showProjections && (
                      <>
                        <th scope="col" className="num-col">
                          Proj
                        </th>
                        <th scope="col" className="num-col">
                          +/-
                        </th>
                      </>
                    )}
                    {columns.map((c) => (
                      <th key={c.key} scope="col" className="num-col">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {detail.weeks.map((w) => (
                    <tr key={w.week}>
                      <th scope="row">{w.week}</th>
                      <td>{w.team ? <TeamLink team={w.team}>{w.team}</TeamLink> : "–"}</td>
                      <td>
                        {w.opponent ? `${w.home === false ? "at" : "vs"} ${w.opponent}` : "–"}
                      </td>
                      <td className="num num-col">{w.points.toFixed(1)}</td>
                      {showProjections && (
                        <>
                          <td className="num num-col">
                            {w.projected === null || w.projected === undefined
                              ? "–"
                              : w.projected.toFixed(1)}
                          </td>
                          <td className="num num-col">
                            {projectionDelta(
                              w.points,
                              w.projected,
                              w.final ? "played" : "current",
                            ) ?? "–"}
                          </td>
                        </>
                      )}
                      {columns.map((c) => (
                        <td key={c.key} className="num num-col">
                          {formatStat(w.stats[c.key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={3}>
                      Season total
                    </th>
                    <td className="num num-col">{detail.season.points.toFixed(1)}</td>
                    {showProjections && (
                      <>
                        <td className="num num-col">
                          {allProjected ? projectedTotal.toFixed(1) : "–"}
                        </td>
                        <td className="num num-col">
                          {allProjected && detail.weeks.every((w) => w.final)
                            ? projectionDelta(detail.season.points, projectedTotal, "played")
                            : "–"}
                        </td>
                      </>
                    )}
                    {columns.map((c) => (
                      <td key={c.key} className="num num-col">
                        {formatStat(totals[c.key])}
                      </td>
                    ))}
                  </tr>
                  {detail.projected && (
                    <tr className="pd-projected-row">
                      <th scope="row" colSpan={3}>
                        Projected, week {detail.projected.week}
                      </th>
                      <td className="num num-col">{detail.projected.points.toFixed(1)}</td>
                      {showProjections && (
                        <>
                          <td className="num num-col">–</td>
                          <td className="num num-col">–</td>
                        </>
                      )}
                      {columns.map((c) => (
                        <td key={c.key} className="num num-col">
                          {formatStat(detail.projected?.stats[c.key])}
                        </td>
                      ))}
                    </tr>
                  )}
                </tfoot>
              </table>
            </div>
          )}
        </section>

        {detail.past_seasons.length > 0 && (
          <section aria-labelledby="pd-past">
            <h3 id="pd-past">Past seasons</h3>
            <div className="players-scroll">
              <table className="players pd-table">
                <caption className="visually-hidden">
                  Season totals under this league&apos;s scoring. Open a season to see it game by
                  game.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Season</th>
                    <th scope="col">Team</th>
                    <th scope="col" className="num-col">
                      Games
                    </th>
                    <th scope="col" className="num-col">
                      Points
                    </th>
                    <th scope="col" className="num-col">
                      Rank
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {detail.past_seasons.map((s) => (
                    <PastSeasonRows
                      key={s.season}
                      season={s}
                      position={detail.position}
                      open={openSeason === s.season}
                      onToggle={() =>
                        setOpenSeason((current) => (current === s.season ? null : s.season))
                      }
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </dialog>
  );
}
