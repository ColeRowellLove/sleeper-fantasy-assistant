import Link from "next/link";

import type { LineupAccuracy } from "../lib/api";
import { rosterPath } from "../lib/league";

const percent = (n: number | null) => (n === null ? "–" : `${(n * 100).toFixed(1)}%`);
const points = (n: number | null) => (n === null ? "–" : n.toFixed(1));

/**
 * Sit vs start accuracy: how close each team's lineups came to the best ones its roster allowed.
 * Both numbers are Sleeper's own season totals (points and potential points), not recomputed here.
 */
export default function AccuracyTable({
  data,
  leagueId,
  myRosterId,
}: {
  data: LineupAccuracy;
  leagueId: string;
  myRosterId: number | null;
}) {
  const reported = data.teams.some((t) => t.accuracy !== null);
  return (
    <section aria-labelledby="accuracy-heading">
      <h2 id="accuracy-heading">Sit vs start accuracy</h2>
      <p className="note">
        Points scored divided by Sleeper&apos;s potential points: what the best possible lineups
        would have scored. 100% means you started the best lineup every week. Both numbers come from
        Sleeper for the season so far.
      </p>
      {!reported && (
        <p className="note" role="status">
          Sleeper has not reported potential points for this league yet, so there is nothing to
          score.
        </p>
      )}
      <div className="card flush">
        <div className="players-scroll">
          <table className="players accuracy-table">
            <caption className="visually-hidden">Lineup accuracy by team, best first</caption>
            <thead>
              <tr>
                <th scope="col">Team</th>
                <th scope="col" className="num">
                  Accuracy
                </th>
                <th scope="col" className="num">
                  Points
                </th>
                <th scope="col" className="num">
                  Potential points
                </th>
                <th scope="col" className="num">
                  Left on bench
                </th>
              </tr>
            </thead>
            <tbody>
              {data.teams.map((t) => (
                <tr key={t.roster_id} className={t.roster_id === myRosterId ? "mine" : undefined}>
                  <th scope="row">
                    <Link href={rosterPath(leagueId, t.roster_id)} className="member-link">
                      {t.team}
                    </Link>
                    {t.roster_id === myRosterId && <span className="muted"> (you)</span>}
                  </th>
                  <td className="num">{percent(t.accuracy)}</td>
                  <td className="num">{points(t.points)}</td>
                  <td className="num">{points(t.potential)}</td>
                  <td className="num">{points(t.left_on_bench)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
