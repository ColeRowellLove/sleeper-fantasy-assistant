import type { StandingsRow } from "./api";

export type SortKey = "rank" | "team" | "record" | "streak" | "points_for" | "points_against";
type SortDirection = "asc" | "desc";

export interface SortState {
  key: SortKey;
  direction: SortDirection;
}

export const DEFAULT_SORT: SortState = { key: "rank", direction: "asc" };

/** Win percentage with a tie as half a win; teams with no games yet count as 0. */
function winPct(row: StandingsRow): number {
  const games = row.wins + row.losses + row.ties;
  return games === 0 ? 0 : (row.wins + row.ties / 2) / games;
}

export interface Streak {
  kind: "W" | "L" | "T";
  length: number;
}

/** Parses Sleeper's "3W" / "2L" / "1T". Anything else (or no streak yet) is null. */
export function parseStreak(value: string | null | undefined): Streak | null {
  const match = /^(\d{1,2})([WLT])$/.exec(value ?? "");
  if (!match) return null;
  return { kind: match[2] as Streak["kind"], length: Number(match[1]) };
}

/** Wins count up, losses count down, so sorting runs from the longest win streak to the longest loss streak. */
function streakValue(row: StandingsRow): number {
  const streak = parseStreak(row.streak);
  if (!streak || streak.kind === "T") return 0;
  return streak.kind === "W" ? streak.length : -streak.length;
}

const VALUE: Record<SortKey, (row: StandingsRow) => number | string> = {
  rank: (row) => row.rank,
  team: (row) => row.team.toLowerCase(),
  record: winPct,
  streak: streakValue,
  points_for: (row) => row.points_for,
  points_against: (row) => row.points_against,
};

/** What a first click on a column does: names run A to Z, rank best first, numbers high first. */
function firstDirection(key: SortKey): SortDirection {
  return key === "rank" || key === "team" ? "asc" : "desc"; // streak: hottest first
}

/** Clicking the active column flips it; clicking another starts at that column's natural order. */
export function nextSort(current: SortState, key: SortKey): SortState {
  if (current.key === key) {
    return { key, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  return { key, direction: firstDirection(key) };
}

/** Sorted copy. Ties keep league rank order whichever way the column runs, so the order is stable. */
export function sortStandings(rows: StandingsRow[], sort: SortState): StandingsRow[] {
  const value = VALUE[sort.key];
  const sign = sort.direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = value(a);
    const y = value(b);
    const order =
      typeof x === "string" ? x.localeCompare(y as string) : (x as number) - (y as number);
    return order * sign || a.rank - b.rank;
  });
}
