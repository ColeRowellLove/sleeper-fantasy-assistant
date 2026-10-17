import type { TeamLineup } from "../lib/api";
import { winPercent, type WeekState } from "../lib/lineups";

/** The team behind gets the softer shade; the team ahead (or both, when even) the full one. */
function tone(mine: number, theirs: number): string {
  return mine < theirs ? "win-trail" : "";
}

/**
 * One slim bar per team, like Sleeper's header: each fills to its own win chance (the first team
 * from the left, the second from the right) under a bold "46% WIN". The teams have their own
 * colours (blue and orange, not red and green, so it reads for colour-blind viewers) and the team
 * behind is the softer shade. Colour is never the only signal: each bar sits on its team's side, under that team's
 * name and score, and the bar is decorative because the sentence for screen readers (with both
 * names) carries the same information.
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
      <div className="win-halves" aria-hidden="true">
        <div className="win-half win-half-a">
          <span className="win-label">
            <strong>{left}%</strong> WIN
          </span>
          <div className="win-track">
            <span
              className={`win-bar-a ${tone(left, right)}`.trim()}
              style={{ width: `${left}%` }}
            />
          </div>
        </div>
        <div className="win-half win-half-b">
          <span className="win-label">
            <strong>{right}%</strong> WIN
          </span>
          <div className="win-track">
            <span
              className={`win-bar-b ${tone(right, left)}`.trim()}
              style={{ width: `${right}%` }}
            />
          </div>
        </div>
      </div>
      {rough && <p className="muted win-bar-rough">{roughNote}</p>}
    </div>
  );
}
