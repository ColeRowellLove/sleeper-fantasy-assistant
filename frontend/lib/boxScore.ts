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

/** The Sleeper player ids on a team in this game that the viewer owns (to mark them "You"). */
export function boxMineIds(
  games: {
    away: string;
    home: string;
    players: { player_id: string; owner_roster_id?: number | null }[];
  }[],
  game: { away: string; home: string },
  myRosterId: number | null,
): string[] {
  if (myRosterId === null) return [];
  return games
    .filter((g) => g.away === game.away && g.home === game.home)
    .flatMap((g) => g.players)
    .filter((p) => p.owner_roster_id === myRosterId)
    .map((p) => p.player_id);
}

/** A box score only exists once a game has started. */
export function hasBoxScore(state: string | undefined): boolean {
  return state === "live" || state === "final";
}
