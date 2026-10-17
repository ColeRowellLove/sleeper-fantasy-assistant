import type { TeamLineup } from "../lib/api";
import { winPercent, type WeekState } from "../lib/lineups";

/** The team ahead is the strong side, the team behind the soft one, an even matchup neutral. */
function tone(mine: number, theirs: number): string {
  if (mine === theirs) return "win-even";
  return mine > theirs ? "win-lead" : "win-trail";
}

/**
 * A bar split in proportion to the two teams' chances: a bold number on each side (the team
 * names are right above it in the score header), a rounded track with a marker at 50%, and a "Win chance" caption. The two teams have their
 * own colours (blue and orange, not red and green, so it reads for colour-blind viewers), and the
 * team ahead is the stronger shade. Colour is never the only signal: the numbers and names say it,
 * and the bar is decorative because the sentence for screen readers carries the same information.
 */
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
  const rough = Boolean(a.win_probability_rough || b.win_probability_rough);
  const roughNote = "Rough estimate: some starters have no projection yet.";
  return (
    <div className={`win-bar${rough ? " win-rough" : ""}`}>
      <span className="visually-hidden">
        {`${a.team} has a ${left} percent chance to win and ${b.team} has ${right} percent, from projected points.`}
      </span>
      <div className="win-bar-labels" aria-hidden="true">
        <span className="win-side win-side-a">
          <strong>{left}%</strong>
        </span>
        <span className="win-caption">Win chance</span>
        <span className="win-side win-side-b">
          <strong>{right}%</strong>
        </span>
      </div>
      <div className="win-bar-track" aria-hidden="true">
        <span className={`win-bar-a ${tone(left, right)}`} style={{ width: `${left}%` }} />
        <span className={`win-bar-b ${tone(right, left)}`} style={{ width: `${100 - left}%` }} />
        <span className="win-bar-mid" />
      </div>
      {rough && <p className="muted win-bar-rough">{roughNote}</p>}
    </div>
  );
}
