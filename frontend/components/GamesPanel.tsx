import type { Games } from "../lib/api";
import { orderGames, yourPlayersText } from "../lib/games";
import { weekState } from "../lib/lineups";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerLink from "./PlayerLink";
import PositionChip from "./PositionChip";
import TeamLink from "./TeamLink";
import WeekChips from "./WeekChips";

const points = (n: number | null | undefined) =>
  n === null || n === undefined ? "–" : n.toFixed(1);

const NOTES = {
  played: "Final scores for this week.",
  current: "This week's games. Scores and stats update as games are played.",
  upcoming: "Upcoming week: kickoff times, lines and conditions, with the players you could use.",
} as const;

/**
 * Every NFL game of a week: score or kickoff, the line and the conditions. Games with one of your
 * players come first, and each opens (by keyboard too) to the players in it with their stats and
 * fantasy points. Your players are marked in words as well as style.
 */
export default function GamesPanel({
  data,
  leagueId,
  myRosterId,
}: {
  data: Games;
  leagueId: string;
  myRosterId: number | null;
}) {
  const ordered = orderGames(data.games, myRosterId);
  const state = data.week === null ? "played" : weekState(data.week, data.current_week);
  return (
    <section aria-labelledby="games-heading" className="games">
      <h2 id="games-heading" className="week-heading">
        {data.week !== null ? `Week ${data.week} games` : "Games"}
      </h2>
      {data.weeks.length > 0 && (
        <WeekChips
          leagueId={leagueId}
          weeks={data.weeks}
          selected={data.week}
          currentWeek={data.current_week}
          tab="games"
        />
      )}
      {data.week !== null && <p className="note">{NOTES[state]}</p>}
      {ordered.length === 0 && <p className="note">No games have been synced for this week yet.</p>}

      <ul className="game-list">
        {ordered.map(({ card, mine }) => (
          <li key={card.game_id}>
            <details className={`card game-card${mine.length > 0 ? " has-mine" : ""}`}>
              <summary>
                <span className="game-teams">
                  {card.away}
                  <span className="muted"> at </span>
                  {card.home}
                </span>
                <GameBadge game={card.game} conditions="full" />
                {mine.length > 0 && (
                  <span className="game-mine">
                    <span className="you">You</span> {yourPlayersText(mine.length)}
                  </span>
                )}
              </summary>
              <p className="game-links">
                Depth charts: <TeamLink team={card.away}>{card.away}</TeamLink>,{" "}
                <TeamLink team={card.home}>{card.home}</TeamLink>
              </p>
              {card.players.length === 0 ? (
                <p className="note">
                  No stats yet, and none of this league&apos;s teams have players in this game.
                </p>
              ) : (
                <div className="players-scroll">
                  <table className="players pd-table game-players">
                    <caption className="visually-hidden">
                      Players in {card.away} at {card.home}
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Player</th>
                        <th scope="col">Team</th>
                        <th scope="col">Fantasy team</th>
                        <th scope="col">Stats</th>
                        <th scope="col" className="num">
                          Pts
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {card.players.map((p) => {
                        const yours = myRosterId !== null && p.owner_roster_id === myRosterId;
                        return (
                          <tr key={p.player_id} className={yours ? "mine" : undefined}>
                            <th scope="row" className="player-cell">
                              <span className="player-name">
                                <PlayerLink playerId={p.player_id}>{p.name}</PlayerLink>
                              </span>
                              <span className="player-meta">
                                <PositionChip position={p.position} />
                                <InjuryBadge injury={p.injury} />
                              </span>
                            </th>
                            <td>{p.team}</td>
                            <td>
                              {yours ? (
                                <span className="status-owned">
                                  <span className="you">You</span> {p.owner_team}
                                </span>
                              ) : p.owner_team ? (
                                <span className="muted">{p.owner_team}</span>
                              ) : (
                                <span className="status-available">Available</span>
                              )}
                            </td>
                            <td>{p.stat_line ?? <span className="muted">–</span>}</td>
                            <td className="num">{points(p.points)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </details>
          </li>
        ))}
      </ul>
      <p className="note">
        Fantasy points use this league&apos;s scoring. Games with your players are listed first.
      </p>
    </section>
  );
}
