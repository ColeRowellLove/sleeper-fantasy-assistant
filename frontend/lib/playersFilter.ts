/** Filtering and sorting for the Players tab. Pure, so it is easy to test. */

import type { PlayerListing } from "./api";

export const POSITION_FILTERS = ["QB", "RB", "WR", "TE", "K", "DEF"] as const;
export type PositionFilter = "ALL" | (typeof POSITION_FILTERS)[number] | "FLEX";

export type Availability = "all" | "available" | "rostered";

export type SortKey = "name" | "status" | "adds" | "drops" | "rank" | "total" | "projected";
export type SortDirection = "asc" | "desc";

export interface PlayerSort {
  key: SortKey;
  direction: SortDirection;
}

export const DEFAULT_SORT: PlayerSort = { key: "total", direction: "desc" };

export interface PlayerFilters {
  position: PositionFilter;
  availability: Availability;
  search: string;
}

export const DEFAULT_FILTERS: PlayerFilters = { position: "ALL", availability: "all", search: "" };

const FLEX_POSITIONS = new Set(["RB", "WR", "TE"]);

/** Lowercase and strip accents and punctuation so "D'Andre" matches "dandre" and "Jose" matches "José". */
function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "");
}

export function filterPlayers(players: PlayerListing[], filters: PlayerFilters): PlayerListing[] {
  const query = normalize(filters.search).trim();
  return players.filter((p) => {
    if (filters.position === "FLEX") {
      if (!FLEX_POSITIONS.has(p.position)) return false;
    } else if (filters.position !== "ALL" && p.position !== filters.position) {
      return false;
    }
    if (filters.availability === "available" && p.owner_roster_id !== null) return false;
    if (filters.availability === "rostered" && p.owner_roster_id === null) return false;
    if (query && !normalize(`${p.name} ${p.team ?? ""}`).includes(query)) return false;
    return true;
  });
}

/** What a first click on a column does: names and rank run best first, numbers run high first. */
export function firstDirection(key: SortKey): SortDirection {
  return key === "name" || key === "rank" || key === "status" ? "asc" : "desc";
}

export function nextSort(current: PlayerSort, key: SortKey): PlayerSort {
  if (current.key === key) {
    return { key, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  return { key, direction: firstDirection(key) };
}

function value(p: PlayerListing, key: SortKey): number | string | null {
  switch (key) {
    case "name":
      return p.name.toLowerCase();
    case "status":
      return p.owner_roster_id === null ? 0 : 1; // available players sort first when ascending
    case "adds":
      return p.adds ?? null;
    case "drops":
      return p.drops ?? null;
    case "rank":
      return p.rank ?? null;
    case "total":
      return p.total_points;
    case "projected":
      return p.projected ?? null;
  }
}

/**
 * Sorted copy. A player with no value for the column (no projection, not in Sleeper's top 100, no
 * rank yet) always goes last, in either direction, so the top of the list is always real data.
 * Ties keep the season-points order the server sent, so the order is stable.
 */
export function sortPlayers(players: PlayerListing[], sort: PlayerSort): PlayerListing[] {
  const sign = sort.direction === "asc" ? 1 : -1;
  const indexed = players.map((p, index) => ({ p, index }));
  indexed.sort((a, b) => {
    const x = value(a.p, sort.key);
    const y = value(b.p, sort.key);
    if (x === null && y === null) return a.index - b.index;
    if (x === null) return 1;
    if (y === null) return -1;
    const order = typeof x === "string" ? x.localeCompare(y as string) : x - (y as number);
    return order * sign || a.index - b.index;
  });
  return indexed.map(({ p }) => p);
}

export function describeSort(sort: PlayerSort): string {
  const labels: Record<SortKey, string> = {
    name: "Player",
    status: "Status",
    adds: "Adds",
    drops: "Drops",
    rank: "Position rank",
    total: "Total points",
    projected: "Projected points",
  };
  const how =
    sort.key === "name"
      ? sort.direction === "asc"
        ? "A to Z"
        : "Z to A"
      : sort.key === "rank"
        ? sort.direction === "asc"
          ? "best first"
          : "worst first"
        : sort.key === "status"
          ? sort.direction === "asc"
            ? "available first"
            : "rostered first"
          : sort.direction === "asc"
            ? "low to high"
            : "high to low";
  return `Sorted by ${labels[sort.key]}, ${how}`;
}
