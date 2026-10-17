import type { PlayerDetail } from "../lib/api";
import { describeStats } from "../lib/playerDetail";
import { count } from "../lib/format";
import { projectionCards, summaryStats } from "../lib/playerSummary";
import GameLine from "./GameLine";

/**
 * The Summary tab: the numbers that matter at a glance, this week's game with its projection, and
 * a strip with every week's projection and result.
 */
export default function PlayerSummary({ detail }: { detail: PlayerDetail }) {
  const stats = summaryStats(detail);
  const cards = projectionCards(detail);
  const dash = "–";
  return (
    <>
      <dl className="ps-stats" aria-label="Season summary">
        {stats.map((s) => (
          <div key={s.label} title={s.title}>
            <dt>{s.label}</dt>
            <dd>{s.value}</dd>
          </div>
        ))}
      </dl>
      <p className="note ps-note">
        Owned and started are ESPN&apos;s numbers. Points use this league&apos;s scoring, and every
        stat counts.
      </p>

      {detail.projected && (
        <section aria-labelledby="pd-upcoming">
          <h3 id="pd-upcoming">This week&apos;s game</h3>
          <div className="ps-game">
            <span className="ps-week">Week {detail.projected.week}</span>
            <GameLine game={detail.game} matchup={detail.matchup} position={detail.position} />
            <p className="ps-proj">
              <strong>{detail.projected.points.toFixed(1)}</strong> projected
            </p>
            <p className="note">{describeStats(detail.projected.stats, detail.position)}</p>
          </div>
        </section>
      )}

      {cards.length > 0 && (
        <section aria-labelledby="pd-projections">
          <h3 id="pd-projections">Projections</h3>
          <div
            className="ps-strip"
            role="region"
            aria-label="Projections by week, scrolls sideways"
            tabIndex={0}
          >
            <ul className="ps-cards">
              {cards.map((c) => (
                <li key={c.week} className={`ps-card${c.bye ? " ps-bye" : ""}`}>
                  <span className="ps-card-head">
                    Wk {c.week}
                    {c.opponent && (
                      <span className={`ps-opp${c.difficulty ? ` diff-${c.difficulty}` : ""}`}>
                        {c.opponent}
                        {c.difficulty && (
                          <span className="visually-hidden"> ({c.difficulty} matchup)</span>
                        )}
                      </span>
                    )}
                  </span>
                  {c.bye ? (
                    <span className="ps-card-bye">BYE</span>
                  ) : (
                    <>
                      <span className="ps-line">
                        <span className="ps-key">Proj</span>
                        {c.projected === null ? dash : c.projected.toFixed(1)}
                      </span>
                      <span className="ps-line">
                        <span className="ps-key">Final</span>
                        {c.final === null ? dash : c.final.toFixed(1)}
                      </span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <section aria-labelledby="pd-activity">
        <h3 id="pd-activity">Sleeper activity, last 24 hours</h3>
        <ul className="ps-activity">
          <li>
            Adds <strong>{count(detail.adds)}</strong>
          </li>
          <li>
            Drops <strong>{count(detail.drops)}</strong>
          </li>
        </ul>
      </section>
    </>
  );
}
