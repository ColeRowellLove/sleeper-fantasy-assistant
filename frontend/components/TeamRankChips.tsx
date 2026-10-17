import type { TeamStat } from "../lib/api";
import { rankChips } from "../lib/teamRank";

/** Where a team ranks in the numbers that matter for a position, as coloured chips. */
export default function TeamRankChips({
  stats,
  team,
  headingId,
}: {
  stats?: TeamStat[];
  team: string;
  headingId: string;
}) {
  const chips = rankChips(stats);
  if (chips.length === 0) return null;
  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>{team} team rank</h3>
      <ul className="rank-chips">
        {chips.map((c) => (
          <li key={c.key} className={`rank-chip tone-${c.tone}`}>
            <span className="rank-chip-label">{c.label}</span>
            <span className="rank-chip-rank" aria-label={c.spoken}>
              {c.rank}
              <span className="rank-chip-value" aria-hidden="true">
                {" "}
                {c.value}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
