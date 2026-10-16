import type { GameCard, GamePlayer } from "../lib/api";
import { GROUPS, playersFor, type StatGroup } from "../lib/gameStats";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PlayerLink from "./PlayerLink";
import PositionChip from "./PositionChip";
import TeamLogo from "./TeamLogo";

const points = (n: number | null | undefined) =>
  n === null || n === undefined ? "–" : n.toFixed(1);

function Owner({ player, mine }: { player: GamePlayer; mine: boolean }) {
  if (mine) {
    return (
      <span className="status-owned">
        <span className="you">You</span> {player.owner_team}
      </span>
    );
  }
  if (player.owner_team) return <span className="owner-other">{player.owner_team}</span>;
  return <span className="status-available">Available</span>;
}

function GroupTable({
  group,
  team,
  players,
  myRosterId,
}: {
  group: StatGroup;
  team: string;
  players: GamePlayer[];
  myRosterId: number | null;
}) {
  const projected = players.length > 0 && players.every((p) => p.projected);
  return (
    <div className="players-scroll">
      <table className="players pd-table game-players">
        <caption className="visually-hidden">
          {team} {group.title.toLowerCase()}
          {projected ? " (projected)" : ""}
        </caption>
        <thead>
          <tr>
            <th scope="col">{group.title}</th>
            <th scope="col">Fantasy team</th>
            {group.columns.map((c) => (
              <th key={c.label} scope="col" className="num">
                {c.label}
              </th>
            ))}
            <th scope="col" className="num">
              {projected ? "Proj pts" : "Pts"}
            </th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => {
            const mine = myRosterId !== null && p.owner_roster_id === myRosterId;
            const cls = mine ? "mine" : p.owner_team ? "owned-other" : undefined;
            const stats = p.stats ?? {};
            return (
              <tr key={p.player_id} className={cls}>
                <th scope="row" className="player-cell">
                  <span className="game-player">
                    <PlayerAvatar
                      player_id={p.player_id}
                      name={p.name}
                      position={p.position}
                      team={p.team}
                    />
                    <span>
                      <span className="player-name">
                        <PlayerLink playerId={p.player_id}>{p.name}</PlayerLink>
                      </span>
                      <span className="player-meta">
                        <PositionChip position={p.position} />
                        <InjuryBadge injury={p.injury} />
                      </span>
                    </span>
                  </span>
                </th>
                <td>
                  <Owner player={p} mine={mine} />
                </td>
                {group.columns.map((c) => (
                  <td key={c.label} className="num">
                    {c.get(stats) ?? <span className="muted">–</span>}
                  </td>
                ))}
                <td className="num">
                  {points(p.points)}
                  {p.projected && p.points !== null && p.points !== undefined && (
                    <span className="muted"> proj</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The players of a game laid out like a box score, one team after the other: a table each for
 * passing, rushing and receiving, kicking and defense, with every stat Sleeper has (the projected
 * line before kickoff). Your players are marked "You" and tinted strongly; other fantasy teams'
 * players carry that team's name and a lighter tint; free agents say "Available".
 */
export default function GamePlayers({
  card,
  myRosterId,
}: {
  card: GameCard;
  myRosterId: number | null;
}) {
  return (
    <div className="game-teams-detail">
      {[card.away, card.home].map((team) => (
        <section key={team} aria-label={`${team} players`} className="game-team-block">
          <h3 className="game-team-title">
            <TeamLogo team={team} size={28} /> {team}
          </h3>
          {GROUPS.map((group) => {
            const rows = playersFor(group, card.players, team);
            if (rows.length === 0) return null;
            return (
              <GroupTable
                key={group.key}
                group={group}
                team={team}
                players={rows}
                myRosterId={myRosterId}
              />
            );
          })}
        </section>
      ))}
    </div>
  );
}
