import type { LineupPlayer, Lineups, StandingsRow } from "../lib/api";
import { abbreviateName } from "../lib/game";
import { positionClass } from "../lib/positions";
import {
  formatPoints,
  notPlayedYet,
  pairRows,
  slotShort,
  winnerId,
  type WeekState,
} from "../lib/lineups";
import GameLine from "./GameLine";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PlayerLink from "./PlayerLink";
import PlayerStatLine from "./PlayerStatLine";
import TeamLink from "./TeamLink";
import MatchupHeader from "./MatchupHeader";
import Projection from "./Projection";
import WinBar from "./WinBar";

type Matchup = Lineups["matchups"][number];

interface Props {
  matchup: Matchup;
  state: WeekState;
  week: number | null;
  myRosterId: number | null;
  mine?: boolean;
  /** When given, each team's name links to that team's roster. */
  leagueId?: string;
  /** The standings, for each team's record, streak and seed under its name. */
  standings?: StandingsRow[];
  /** Eager-load avatars (use for the first card on the page). */
  priority?: boolean;
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
  // a dash for anyone whose game has not started, even in a week that is under way
  const notPlayed = notPlayedYet(state, player.game);
  const points = (
    <td className={`pts-cell pts-${side} num`}>
      {notPlayed ? "–" : formatPoints(player.points)}
      <Projection
        projected={player.projected}
        compareWith={player.projected_pregame}
        actual={player.points}
        state={state}
        label="Proj"
      />
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
          <span className="cell-name">
            {player.player_id ? (
              <PlayerLink playerId={player.player_id}>
                <span className="name-full">{player.name}</span>
                <span className="name-short" aria-hidden="true">
                  {abbreviateName(player.name)}
                </span>
              </PlayerLink>
            ) : (
              player.name
            )}
          </span>
          <span className="cell-meta">
            <span className={`pos-text ${positionClass(player.position)}`}>
              {player.position ?? "–"}
            </span>
            {player.team && (
              <>
                <span className="dot" aria-hidden="true">
                  •
                </span>
                <span className="cell-team">
                  <TeamLink team={player.team}>{player.team}</TeamLink>
                </span>
              </>
            )}
            {/* the designation is the current one, so it is not shown against weeks already played */}
            {state !== "played" && <InjuryBadge injury={player.injury} />}
          </span>
          <span className="cell-meta cell-game">
            <GameLine game={player.game} matchup={player.matchup} position={player.position} />
          </span>
          <PlayerStatLine line={player.stat_line} projected={player.stat_line_projected} />
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
  leagueId,
  standings,
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
        <MatchupHeader
          a={a}
          b={b}
          state={state}
          winner={winner}
          myRosterId={myRosterId}
          leagueId={leagueId}
          standings={standings}
        />
        <WinBar a={a} b={b} state={state} />
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
            <th scope="col" className="num-col">
              Pts
            </th>
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
                <span className={`slot-chip ${positionClass(row.slot)}`}>
                  <span className="visually-hidden">{row.slot}</span>
                  <span aria-hidden="true">{slotShort(row.slot)}</span>
                </span>
              </th>
              <Cell player={row.right} state={state} side="right" priority={priority} />
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}
