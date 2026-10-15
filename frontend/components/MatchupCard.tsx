import type { LineupPlayer, Lineups, TeamLineup } from "../lib/api";
import { formatPoints, pairRows, winnerId, type WeekState } from "../lib/lineups";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PositionChip from "./PositionChip";

type Matchup = Lineups["matchups"][number];

interface Props {
  matchup: Matchup;
  state: WeekState;
  week: number | null;
  myRosterId: number | null;
  mine?: boolean;
  /** Eager-load avatars (use for the first card on the page). */
  priority?: boolean;
}

function TeamScore({
  team,
  state,
  isWinner,
  isMe,
}: {
  team: TeamLineup;
  state: WeekState;
  isWinner: boolean;
  isMe: boolean;
}) {
  return (
    <div className={`team-score${isWinner ? " winner" : ""}`}>
      <span className="team-name">
        {team.team}
        {isMe && <span className="you">You</span>}
      </span>
      <span className="score num">{state === "upcoming" ? "–" : team.points.toFixed(2)}</span>
      {isWinner && <span className="win-tag">Winner</span>}
    </div>
  );
}

function Cell({
  player,
  state,
  side,
  priority,
}: {
  player: LineupPlayer | null;
  state: WeekState;
  side: "left" | "right";
  priority: boolean;
}) {
  if (!player) {
    return (
      <>
        <td className={`pts-cell pts-${side}`} />
        <td className={`player-cell cell-${side}`} />
      </>
    );
  }
  const points = (
    <td className={`pts-cell pts-${side} num`}>
      {state === "upcoming" ? "–" : formatPoints(player.points)}
    </td>
  );
  const info = (
    <td className={`player-cell cell-${side}`}>
      <div className="cell-inner">
        {player.player_id ? (
          <PlayerAvatar
            player_id={player.player_id}
            name={player.name}
            position={player.position}
            team={player.team}
            priority={priority}
          />
        ) : null}
        <span className="cell-text">
          <span className="cell-name">{player.name}</span>
          <span className="cell-meta">
            <PositionChip position={player.position} />
            {/* the designation is the current one, so it is not shown against weeks already played */}
            {state !== "played" && <InjuryBadge injury={player.injury} />}
            <GameBadge game={player.game} />
          </span>
        </span>
      </div>
    </td>
  );
  return side === "left" ? (
    <>
      {info}
      {points}
    </>
  ) : (
    <>
      {points}
      {info}
    </>
  );
}

/** One fantasy matchup: a scoreboard, then both lineups aligned row by row. */
export default function MatchupCard({
  matchup,
  state,
  week,
  myRosterId,
  mine = false,
  priority = false,
}: Props) {
  const [a, b] = matchup.teams;
  const id = `matchup-${week ?? "w"}-${a.roster_id}`;

  if (!b) {
    return (
      <article className="matchup-card" aria-labelledby={id}>
        <h3 id={id}>{a.team}</h3>
        <p className="note">No opponent this week.</p>
      </article>
    );
  }

  const winner = state === "played" ? winnerId(a, b) : null;
  const rows = pairRows(a, b);

  return (
    <article className={`matchup-card${mine ? " mine" : ""}`} aria-labelledby={id}>
      <header className="scoreboard">
        {mine && <p className="mine-label">Your matchup</p>}
        <h3 id={id} className="visually-hidden">
          {a.team} versus {b.team}
        </h3>
        <div className="score-row">
          <TeamScore team={a} state={state} isWinner={winner === a.roster_id} isMe={a.roster_id === myRosterId} />
          <span className="vs" aria-hidden="true">
            vs
          </span>
          <TeamScore team={b} state={state} isWinner={winner === b.roster_id} isMe={b.roster_id === myRosterId} />
        </div>
      </header>
      <table className="h2h">
        <caption className="visually-hidden">
          {a.team} versus {b.team}: lineups by slot, then bench
        </caption>
        <thead>
          <tr>
            <th scope="col">{a.team}</th>
            <th scope="col" className="num-col">
              Pts
            </th>
            <th scope="col" className="slot-col">
              Slot
            </th>
            <th scope="col">Pts</th>
            <th scope="col" className="right-col">
              {b.team}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={`${row.slot}-${i}`} className={row.kind === "starter" ? undefined : row.kind}>
              <Cell player={row.left} state={state} side="left" priority={priority} />
              <th scope="row" className="slot-cell">
                {row.slot}
              </th>
              <Cell player={row.right} state={state} side="right" priority={priority} />
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}
