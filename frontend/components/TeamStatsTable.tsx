import type { TeamStat } from "../lib/api";
import { ordinal } from "../lib/game";

/**
 * A team's per-game numbers with where they rank among the 32 teams. Rank 1 is always the best:
 * the most yards or touchdowns and, for what a defense gives up, the fewest.
 */
export default function TeamStatsTable({
  stats,
  team,
  headingId,
  title = "Team stats",
}: {
  stats: TeamStat[];
  team: string;
  headingId: string;
  title?: string;
}) {
  if (stats.length === 0) return null;
  const games = stats[0].games;
  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>{title}</h3>
      <div className="players-scroll">
        <table className="players pd-table team-stats">
          <caption className="visually-hidden">
            {team} per-game stats and league rank, over {games} {games === 1 ? "game" : "games"}
          </caption>
          <thead>
            <tr>
              <th scope="col">Stat</th>
              <th scope="col" className="num">
                Per game
              </th>
              <th scope="col" className="num">
                League rank
              </th>
            </tr>
          </thead>
          <tbody>
            {stats.map((s) => (
              <tr key={s.key}>
                <th scope="row">{s.label}</th>
                <td className="num">{s.value}</td>
                <td className="num">
                  {ordinal(s.rank)} of {s.teams}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        Rank 1 is best: the most yards and touchdowns, the fewest points and yards allowed.
      </p>
    </section>
  );
}
