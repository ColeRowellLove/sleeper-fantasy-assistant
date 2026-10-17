import { leaguePath } from "./league";

const PARAM = /^([A-Z]{2,3})-([A-Z]{2,3})$/;

/** Link to a game's full box score on the games page: `?box=AWAY-HOME` for that week. */
export function boxPath(leagueId: string, week: number, away: string, home: string): string {
  return leaguePath(leagueId, `?tab=games&week=${week}&box=${away}-${home}`);
}

/** The away and home team codes in a `box` parameter, or null when it is not well formed. */
export function parseBox(value: string | undefined): { away: string; home: string } | null {
  const match = PARAM.exec(value ?? "");
  return match ? { away: match[1], home: match[2] } : null;
}
