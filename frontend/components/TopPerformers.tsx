import type { CSSProperties } from "react";

import type { Games } from "../lib/api";
import { fixed } from "../lib/format";
import { teamColor } from "../lib/teamColors";
import { topPerformers } from "../lib/topPerformers";
import PlayerLink from "./PlayerLink";

/**
 * The week's best fantasy games across every NFL game, as cards that scroll sideways: name,
 * position and team, the game's score, his three main stats and his points. Only players who have
 * played, never projections.
 */
export default function TopPerformers({ data }: { data: Games }) {
  const rows = topPerformers(data.games);
  if (rows.length === 0) return null;
  return (
    <section aria-labelledby="top-performers" className="top-performers">
      <h3 id="top-performers">Top performers</h3>
      <div
        className="tp-scroll"
        role="region"
        aria-label="Cards of the week's best games, scrolls sideways"
        tabIndex={0}
      >
        <ol className="tp-list">
          {rows.map(({ player, points, game, stats }) => {
            const color = teamColor(player.team);
            return (
              <li
                key={player.player_id}
                className="tp-card"
                style={color ? ({ "--team": color } as CSSProperties) : undefined}
              >
                <div className="tp-head">
                  <span className="tp-name">
                    <PlayerLink playerId={player.player_id}>{player.name}</PlayerLink>
                  </span>
                  <strong className="tp-points num">{fixed(points)}</strong>
                </div>
                <p className="tp-sub">
                  {player.position} · {player.team}
                  {game && <span className="muted"> · {game}</span>}
                </p>
                <dl className="tp-stats">
                  {stats.map((s) => (
                    <div key={s.label}>
                      <dt>{s.label}</dt>
                      <dd className="num">{s.value}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
