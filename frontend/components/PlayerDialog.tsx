"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { PlayerDetail } from "../lib/api";
import {
  bioDetails,
  bioStrip,
  formatStat,
  rankText,
  statColumns,
  statTotals,
} from "../lib/playerDetail";
import { rosterPath } from "../lib/league";
import GameBadge from "./GameBadge";
import GameLog from "./GameLog";
import InjuryBadge from "./InjuryBadge";
import PanelTabs from "./PanelTabs";
import PlayerAvatar from "./PlayerAvatar";
import PlayerSummary from "./PlayerSummary";
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
  const strip = bioStrip(detail.bio);
  const details = bioDetails(detail.bio);
  const weekStats = detail.weeks.map((w) => w.stats);
  const columns = statColumns(
    [...weekStats, ...(detail.projected ? [detail.projected.stats] : [])],
    detail.position,
  );
  const totals = statTotals(weekStats);
  const summary = (
    <>
      <PlayerSummary detail={detail} />
      {details.length > 0 && (
        <section aria-labelledby="pd-bio">
          <h3 id="pd-bio">Bio</h3>
          <dl className="setting-rows">
            {details.map((row) => (
              <div key={row.label} className="setting-row">
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </>
  );
  const team = (
    <>
      {detail.team && detail.team_stats && (
        <TeamStatsTable
          stats={detail.team_stats}
          team={detail.team}
          headingId="pd-team-stats"
          title={`${detail.team} team stats`}
        />
      )}
    </>
  );
  const gameLog = (
    <>
      <section aria-labelledby="pd-weeks">
        <h3 id="pd-weeks">Game log</h3>
        <GameLog detail={detail} columns={columns} totals={totals} />
      </section>
    </>
  );
  const history = (
    <>
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
    </>
  );
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
              <GameBadge
                game={detail.game}
                matchup={detail.matchup}
                position={detail.position}
                conditions="full"
              />
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

        {strip.length > 0 && (
          <dl className="pd-strip" aria-label="Age, height, weight and experience">
            {strip.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        )}

        <PanelTabs
          label="Player sections"
          tabs={[
            { key: "summary", label: "Summary", content: summary },
            { key: "log", label: "Game log", content: gameLog },
            ...(detail.team && detail.team_stats
              ? [{ key: "team", label: "Team", content: team }]
              : []),
            ...(detail.past_seasons.length > 0
              ? [{ key: "history", label: "History", content: history }]
              : []),
          ]}
        />
      </div>
    </dialog>
  );
}
