import Link from "next/link";
import { useId } from "react";

import type { Lineups } from "../lib/api";
import { rosterPath } from "../lib/league";
import {
  formatPoints,
  formatProjection,
  matchupFor,
  winPercent,
  winnerId,
  type WeekState,
} from "../lib/lineups";
import WinBar from "./WinBar";

function resultText(
  state: WeekState,
  winner: number | null,
  mine: string,
  theirs: string,
  mineId?: number,
): string {
  if (state !== "played") return "No win chance to show yet.";
  if (winner === null) return "Finished level.";
  return `${winner === mineId ? mine : theirs} won this week.`;
}

/**
 * The selected team's matchup this week above its roster: the opponent and the win chance as the
 * same bar the lineups use (the numbers come from the same lineups data, so the two never
 * disagree). When there is no chance to show (a finished week, or too few projections) it names
 * the opponent and gives the score or result instead.
 */
export default function RosterMatchup({
  lineups,
  rosterId,
  leagueId,
}: {
  lineups: Lineups | null | undefined;
  rosterId: number;
  leagueId: string;
}) {
  const headingId = useId();
  const found = matchupFor(lineups, rosterId);
  if (!found) return null;
  const { team, opponent, state, week } = found;
  const heading = week !== null ? `Week ${week} matchup` : "Matchup";
  if (!opponent) {
    return (
      <section aria-labelledby={headingId} className="card roster-matchup">
        <h3 id={headingId}>{heading}</h3>
        <p className="note">No opponent this week.</p>
      </section>
    );
  }
  const hasChance =
    winPercent(team.win_probability) !== null && winPercent(opponent.win_probability) !== null;
  const winner = state === "played" ? winnerId(team, opponent) : null;
  return (
    <section aria-labelledby={headingId} className="card roster-matchup">
      <h3 id={headingId}>{heading}</h3>
      <p className="roster-matchup-line">
        {team.team} vs{" "}
        <Link href={rosterPath(leagueId, opponent.roster_id)} className="member-link">
          {opponent.team}
        </Link>
      </p>
      <dl className="roster-matchup-scores">
        {[team, opponent].map((t) => (
          <div key={t.roster_id}>
            <dt>{t.team}</dt>
            <dd className="num">
              {state === "upcoming" ? "–" : formatPoints(t.points)}
              {formatProjection(t.projected) !== null && (
                <span className="muted"> · proj {formatProjection(t.projected)}</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {hasChance && state !== "played" ? (
        <WinBar a={team} b={opponent} state={state} />
      ) : (
        <p className="note">
          {resultText(state, winner, team.team, opponent.team, team.roster_id)}
        </p>
      )}
    </section>
  );
}
