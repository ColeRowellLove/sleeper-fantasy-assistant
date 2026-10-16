import type { TeamLineup } from "../lib/api";
import { winPercent, type WeekState } from "../lib/lineups";

/**
 * A bar split in proportion to the two teams' chances, with each team's name and number at its
 * end (the only place the percentage is shown). Green is the team ahead and red the team behind, but
 * colour is never the only signal: the ends name the team and number, and the bar is decorative
 * because the sentence for screen readers carries the same information.
 */
/** Green for the team ahead, red for the team behind, neutral for an even matchup. */
export function tone(mine: number, theirs: number): string {
  if (mine === theirs) return "win-even";
  return mine > theirs ? "win-lead" : "win-trail";
}

export default function WinBar({
  a,
  b,
  state,
}: {
  a: TeamLineup;
  b: TeamLineup;
  state: WeekState;
}) {
  const left = winPercent(a.win_probability);
  const right = winPercent(b.win_probability);
  if (left === null || right === null || state === "played") return null;
  return (
    <div className="win-bar">
      <span className="visually-hidden">
        {a.team} has a {left} percent chance to win and {b.team} has {right} percent, from projected
        points.
      </span>
      <div className="win-bar-track" aria-hidden="true">
        <span className={`win-bar-a ${tone(left, right)}`} style={{ width: `${left}%` }} />
        <span className={`win-bar-b ${tone(right, left)}`} style={{ width: `${100 - left}%` }} />
      </div>
      <div className="win-bar-labels" aria-hidden="true">
        <span>
          {a.team} {left}%
        </span>
        <span>
          {right}% {b.team}
        </span>
      </div>
    </div>
  );
}
