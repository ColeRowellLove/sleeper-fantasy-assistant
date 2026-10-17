"use client";

import { fixed } from "../lib/format";
import { abbreviateName } from "../lib/game";
import { teamInitials } from "../lib/lineups";
import type { GameCard, GamePlayer } from "../lib/api";
import { GROUPS, playersFor, totalCells, type StatGroup } from "../lib/gameStats";
import PanelTabs from "./PanelTabs";
import InjuryBadge from "./InjuryBadge";
import PlayerLink from "./PlayerLink";
import StatTable from "./StatTable";
import TeamLogo from "./TeamLogo";

const points = fixed;

/** A short mark after the name: "You", the fantasy team's initials, or "FA"; spoken in words. */
function OwnerTag({ player, mine }: { player: GamePlayer; mine: boolean }) {
  if (mine) return <span className="you">You</span>;
  if (player.owner_team) {
    return (
      <span className="owner-other" title={player.owner_team}>
        <span aria-hidden="true">{teamInitials(player.owner_team)}</span>
        <span className="visually-hidden">{player.owner_team}</span>
      </span>
    );
  }
  return (
    <span className="status-available" title="Available in this league">
      FA<span className="visually-hidden"> (available in this league)</span>
    </span>
  );
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
  const totals = totalCells(group, players);
  const hasTotals = players.length > 1 && totals.some((t) => t !== null);
  return (
    <StatTable
      bare
      caption={`${team} ${group.title.toLowerCase()}${projected ? " (projected)" : ""}`}
      className="pd-table game-players"
    >
      <thead>
        <tr>
          <th scope="col" className="player-cell">
            {group.title}
          </th>
          {group.columns.map((c) => (
            <th key={c.label} scope="col" className="num">
              {c.label}
            </th>
          ))}
          <th scope="col" className="num">
            {projected ? "Proj" : "Pts"}
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
                <span className="gp-name">
                  <PlayerLink playerId={p.player_id}>
                    <span aria-hidden="true">{abbreviateName(p.name)}</span>
                    <span className="visually-hidden">{p.name}</span>
                  </PlayerLink>
                  <InjuryBadge injury={p.injury} />
                  <OwnerTag player={p} mine={mine} />
                </span>
              </th>
              {group.columns.map((c) => (
                <td key={c.label} className="num">
                  {c.get(stats, p.projected === true) ?? <span className="muted">–</span>}
                </td>
              ))}
              <td className="num">{points(p.points)}</td>
            </tr>
          );
        })}
      </tbody>
      {hasTotals && (
        <tfoot>
          <tr>
            <th scope="row" className="player-cell">
              Total
            </th>
            {totals.map((t, i) => (
              <td key={group.columns[i].label} className="num">
                {t ?? ""}
              </td>
            ))}
            <td />
          </tr>
        </tfoot>
      )}
    </StatTable>
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
  // one team at a time, like theScore's box score: far less scrolling than both teams stacked
  const tabs = [card.away, card.home].map((team) => ({
    key: team,
    label: team,
    content: (
      <section aria-label={`${team} players`} className="game-team-block">
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
    ),
  }));
  return (
    <div className="game-teams-detail">
      <PanelTabs label="Team" tabs={tabs} />
    </div>
  );
}
