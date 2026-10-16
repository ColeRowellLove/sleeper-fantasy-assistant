"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import type { PlayerDetail } from "../lib/api";
import { bioRows, describeStats, rankText } from "../lib/playerDetail";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PositionChip from "./PositionChip";

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
              <span className="muted">{detail.team ?? "Free agent"}</span>
              <InjuryBadge injury={detail.injury} />
              <GameBadge game={detail.game} />
            </p>
            <p className="player-dialog-owner">
              {detail.owner_team === null || detail.owner_team === undefined ? (
                <span className="status-available">Available in this league</span>
              ) : (
                <span className="status-owned">On {detail.owner_team}</span>
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
              <dd>{detail.season.average === null || detail.season.average === undefined ? "–" : detail.season.average.toFixed(1)}</dd>
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

        <section aria-labelledby="pd-weeks">
          <h3 id="pd-weeks">Week by week</h3>
          {detail.weeks.length === 0 ? (
            <p className="note">No games played yet this season.</p>
          ) : (
            <div className="players-scroll">
              <table className="players pd-table">
                <caption className="visually-hidden">Points and stats by week this season</caption>
                <thead>
                  <tr>
                    <th scope="col">Week</th>
                    <th scope="col">Opponent</th>
                    <th scope="col" className="num-col">
                      Points
                    </th>
                    <th scope="col">What counted</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.weeks.map((w) => (
                    <tr key={w.week}>
                      <th scope="row">{w.week}</th>
                      <td>
                        {w.opponent ? `${w.home === false ? "at" : "vs"} ${w.opponent}` : "–"}
                      </td>
                      <td className="num num-col">{w.points.toFixed(1)}</td>
                      <td className="pd-stats">{describeStats(w.stats, detail.position)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {detail.past_seasons.length > 0 && (
          <section aria-labelledby="pd-past">
            <h3 id="pd-past">Past seasons</h3>
            <div className="players-scroll">
              <table className="players pd-table">
                <caption className="visually-hidden">Season totals under this league&apos;s scoring</caption>
                <thead>
                  <tr>
                    <th scope="col">Season</th>
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
                    <tr key={s.season}>
                      <th scope="row">{s.season}</th>
                      <td className="num num-col">{s.games}</td>
                      <td className="num num-col">{s.points.toFixed(1)}</td>
                      <td className="num num-col">{rankText(detail.position, s.rank)}</td>
                    </tr>
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
