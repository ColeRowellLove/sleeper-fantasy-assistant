import type { StandingsRow } from "./api";

export type SortKey = "rank" | "team" | "record" | "points_for" | "points_against";
export type SortDirection = "asc" | "desc";

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

const VALUE: Record<SortKey, (row: StandingsRow) => number | string> = {
  rank: (row) => row.rank,
  team: (row) => row.team.toLowerCase(),
  record: winPct,
  points_for: (row) => row.points_for,
  points_against: (row) => row.points_against,
};

/** What a first click on a column does: names run A to Z, rank best first, numbers high first. */
export function firstDirection(key: SortKey): SortDirection {
  return key === "rank" || key === "team" ? "asc" : "desc";
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
    const order = typeof x === "string" ? x.localeCompare(y as string) : (x as number) - (y as number);
    return order * sign || a.rank - b.rank;
  });
}
