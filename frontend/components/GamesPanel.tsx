import { boxPath } from "../lib/boxScore";
import Link from "next/link";
import type { Games, TeamRecord } from "../lib/api";
import { recordText } from "../lib/depth";
import { groupGames, orderGames, teamNickname, yourPlayersText } from "../lib/games";
import { cardScores } from "../lib/game";
import { weekState } from "../lib/lineups";
import GameBadge from "./GameBadge";
import GamePlayers from "./GamePlayers";
import TeamLink from "./TeamLink";
import TeamLogo from "./TeamLogo";
import TopPerformers from "./TopPerformers";
import WeekChips from "./WeekChips";
import NoteList from "./NoteList";

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
function TeamRow({
  team,
  record,
  score,
}: {
  team: string;
  record?: TeamRecord | null;
  score: number | null;
}) {
  return (
    <span className="game-team">
      <TeamLogo team={team} size={28} />
      <span className="game-team-name">{teamNickname(team)}</span>
      {record && (
        <span className="game-team-record">
          <span aria-hidden="true">{recordText(record).short}</span>
          <span className="visually-hidden">{recordText(record).spoken}</span>
        </span>
      )}
      {score !== null && <strong className="game-score num">{score}</strong>}
    </span>
  );
}

export default function GamesPanel({
  favourite = null,
  data,
  leagueId,
  myRosterId,
}: {
  data: Games;
  leagueId: string;
  myRosterId: number | null;
  /** The viewer's favourite NFL team code: its game is listed first. */
  favourite?: string | null;
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

      {groupGames(ordered, favourite).map((section) => (
        <section key={section.key} aria-labelledby={`day-${section.key}`} className="game-day">
          <h3 id={`day-${section.key}`} className="game-day-title">
            {section.title}
          </h3>
          <ul className="game-list">
            {section.games.map(({ card, mine }) => {
              const scores = cardScores(card);
              return (
                <li key={card.game_id}>
                  <details className={`card game-card${mine.length > 0 ? " has-mine" : ""}`}>
                    <summary>
                      <span className="game-teams">
                        <TeamRow
                          team={card.away}
                          record={card.away_record}
                          score={scores?.away ?? null}
                        />
                        <TeamRow
                          team={card.home}
                          record={card.home_record}
                          score={scores?.home ?? null}
                        />
                      </span>
                      <span className="game-meta">
                        <GameBadge game={card.game} variant="card" />
                      </span>
                      {mine.length > 0 && (
                        <span className="game-mine">
                          <span className="you">You</span> {yourPlayersText(mine.length)}
                        </span>
                      )}
                    </summary>
                    <p className="game-conditions-line">
                      <GameBadge game={card.game} conditions="full" />
                    </p>
                    <p className="game-links">
                      Depth charts: <TeamLink team={card.away}>{card.away}</TeamLink>,{" "}
                      <TeamLink team={card.home}>{card.home}</TeamLink>
                      {" · "}
                      <Link href={boxPath(leagueId, card.week, card.away, card.home)}>
                        Full box score
                      </Link>
                    </p>
                    {card.players.length === 0 ? (
                      <p className="note">
                        No stats yet, and none of this league&apos;s teams have players in this
                        game.
                      </p>
                    ) : (
                      <GamePlayers card={card} myRosterId={myRosterId} />
                    )}
                  </details>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <TopPerformers data={data} />
      <NoteList
        items={[
          "Fantasy points use this league's scoring",
          "Games with your players are listed first",
        ]}
      />
    </section>
  );
}
