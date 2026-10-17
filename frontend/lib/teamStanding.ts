import type { StandingsRow } from "./api";
import { ordinal } from "./game";
import { streakText } from "./lineups";

export interface TeamStanding {
  /** "3-2" or "3-2-1". */
  record: string;
  /** "4th" place in the standings. */
  place: string;
  /** Where the team ranks in points scored (1st = most) and points allowed (1st = fewest). */
  pointsFor: string;
  pointsAgainst: string;
  /** "▲2W" or "▼1L", null without a streak. */
  streak: string | null;
}

/** One team's standing line: record, place, and how it ranks in points for and against. */
export function teamStanding(
  standings: StandingsRow[] | undefined,
  rosterId: number,
): TeamStanding | null {
  const row = standings?.find((r) => r.roster_id === rosterId);
  if (!row || !standings) return null;
  const rankBy = (better: (other: StandingsRow) => boolean) =>
    ordinal(1 + standings.filter(better).length);
  return {
    record: `${row.wins}-${row.losses}${row.ties > 0 ? `-${row.ties}` : ""}`,
    place: ordinal(row.rank),
    pointsFor: rankBy((o) => o.points_for > row.points_for),
    pointsAgainst: rankBy((o) => o.points_against < row.points_against),
    streak: streakText(row.streak),
  };
}
