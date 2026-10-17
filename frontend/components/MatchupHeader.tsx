import Link from "next/link";

import type { StandingsRow, TeamLineup } from "../lib/api";
import { rosterPath } from "../lib/league";
import {
  formatProjection,
  projectionDelta,
  streakText,
  yetToPlay,
  type WeekState,
} from "../lib/lineups";
import TeamAvatar from "./TeamAvatar";

/** "@manager • 3-2 ▲2W (#4)": who runs the team and how it is doing, from the standings. */
function Blurb({ row }: { row: StandingsRow | undefined }) {
  if (!row) return null;
  const record = `${row.wins}-${row.losses}${row.ties > 0 ? `-${row.ties}` : ""}`;
  const streak = streakText(row.streak);
  return (
    <span className="mh-blurb">
      {row.manager && <span className="mh-manager">@{row.manager}</span>}
      <span>
        {record}
        {streak && <span className="mh-streak"> {streak}</span>} (#{row.rank})
      </span>
    </span>
  );
}

function Side({
  team,
  row,
  state,
  isWinner,
  isMe,
  leagueId,
  side,
}: {
  team: TeamLineup;
  row: StandingsRow | undefined;
  state: WeekState;
  isWinner: boolean;
  isMe: boolean;
  leagueId?: string;
  side: "a" | "b";
}) {
  const projected = formatProjection(team.projected);
  const delta = projectionDelta(team.points, team.projected_pregame ?? team.projected, state);
  const todo = yetToPlay(team);
  return (
    <div className={`mh-side mh-side-${side}${isWinner ? " winner" : ""}`}>
      <div className="mh-id">
        <TeamAvatar rosterId={team.roster_id} name={team.team} />
        <div className="mh-names">
          <span className="mh-team">
            {leagueId ? (
              <Link href={rosterPath(leagueId, team.roster_id)} className="member-link">
                {team.team}
              </Link>
            ) : (
              team.team
            )}
            {isMe && <span className="you">You</span>}
            {isWinner && <span className="win-tag">Winner</span>}
          </span>
          <Blurb row={row} />
        </div>
      </div>
      <div className="mh-score">
        <span className="score num">{state === "upcoming" ? "–" : team.points.toFixed(2)}</span>
        {projected !== null && (
          <span className="proj">
            Projected {projected}
            {delta && (
              <span className="proj-delta">
                {" "}
                ({delta}
                <span className="visually-hidden"> against projection</span>)
              </span>
            )}
          </span>
        )}
      </div>
      {todo && (
        <p className="mh-todo">
          <span className="mh-todo-count">Yet to play ({todo.count})</span> {todo.text}
        </p>
      )}
    </div>
  );
}

/**
 * The top of a matchup card, like Sleeper's: each team's avatar, name, manager, record, streak and
 * seed, its score and projection, and what it still has to play. The win bars go under it (WinBar)
 * and line up with the two sides.
 */
export default function MatchupHeader({
  a,
  b,
  state,
  winner,
  myRosterId,
  leagueId,
  standings,
}: {
  a: TeamLineup;
  b: TeamLineup;
  state: WeekState;
  winner: number | null;
  myRosterId: number | null;
  leagueId?: string;
  standings?: StandingsRow[];
}) {
  const row = (t: TeamLineup) => standings?.find((r) => r.roster_id === t.roster_id);
  return (
    <div className="mh">
      <Side
        team={a}
        row={row(a)}
        state={state}
        isWinner={winner === a.roster_id}
        isMe={a.roster_id === myRosterId}
        leagueId={leagueId}
        side="a"
      />
      <span className="vs" aria-hidden="true">
        vs
      </span>
      <Side
        team={b}
        row={row(b)}
        state={state}
        isWinner={winner === b.roster_id}
        isMe={b.roster_id === myRosterId}
        leagueId={leagueId}
        side="b"
      />
    </div>
  );
}
