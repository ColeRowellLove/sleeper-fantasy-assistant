import type { Lineups, StandingsRow } from "../lib/api";
import { isMine, orderMatchups, orientMatchup, weekState } from "../lib/lineups";
import MatchupCard from "./MatchupCard";
import WeekChips from "./WeekChips";

const NOTES = {
  played: "Final scores for this week.",
  current: "This week's matchups. Scores update as games are played.",
  upcoming:
    "Upcoming week: lineups show each team's current starters and can change before kickoff.",
} as const;

export default function WeeklyLineups({
  data,
  leagueId,
  myRosterId = null,
  standings,
}: {
  data: Lineups;
  leagueId: string;
  myRosterId?: number | null;
  /** The standings, for each team's record, streak and seed in its matchup header. */
  standings?: StandingsRow[];
}) {
  const week = data.week;
  const state = week === null ? "played" : weekState(week, data.current_week);

  return (
    <section aria-labelledby="lineups-heading" className="lineups">
      <h2 id="lineups-heading" className="week-heading">
        {week !== null ? `Week ${week}` : "Weekly lineups"}
      </h2>

      {data.weeks.length > 0 && (
        <WeekChips
          leagueId={leagueId}
          weeks={data.weeks}
          selected={week}
          currentWeek={data.current_week}
        />
      )}

      {week !== null && <p className="note">{NOTES[state]}</p>}
      {data.matchups.length === 0 && <p className="note">No matchups have been synced yet.</p>}

      <div className="matchups">
        {orderMatchups(data.matchups, myRosterId).map((m, i) => (
          <MatchupCard
            leagueId={leagueId}
            key={m.matchup_id ?? `solo-${i}`}
            matchup={orientMatchup(m, myRosterId)}
            state={state}
            week={week}
            myRosterId={myRosterId}
            mine={isMine(m, myRosterId)}
            standings={standings}
            priority={i === 0}
          />
        ))}
      </div>
    </section>
  );
}
