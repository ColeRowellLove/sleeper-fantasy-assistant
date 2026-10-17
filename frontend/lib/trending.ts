import type { PlayerListing } from "./api";
import { POSITION_FILTERS } from "./playersFilter";

export type TrendDirection = "adds" | "drops";

export const DIRECTIONS: readonly { value: TrendDirection; label: string }[] = [
  { value: "adds", label: "Adds" },
  { value: "drops", label: "Drops" },
];

export type TrendPosition = "ALL" | (typeof POSITION_FILTERS)[number];

/** The position chips: All, then the same positions the Browse filter uses. */
export const POSITION_OPTIONS: readonly { value: TrendPosition; label: string }[] = [
  { value: "ALL", label: "All" },
  ...POSITION_FILTERS.map((value) => ({ value, label: value })),
];

export interface TrendRow {
  player: PlayerListing;
  rank: number;
  count: number;
  /** The count as a share of the biggest one on the list, 0 to 100, for the little bar. */
  share: number;
}

/** 525400 becomes "+525.4K", 1200000 "+1.2M", 80 "+80"; drops get a minus sign. */
export function formatTrendCount(count: number, direction: TrendDirection): string {
  const sign = direction === "adds" ? "+" : "−";
  const thousands = Math.round(count / 100) / 10; // one decimal, rounded before the unit is chosen
  if (thousands >= 999.95 || count >= 1_000_000) {
    return `${sign}${(Math.round(count / 100_000) / 10).toFixed(1)}M`;
  }
  if (count >= 1_000) return `${sign}${thousands.toFixed(1)}K`;
  return `${sign}${count}`;
}

/**
 * Sleeper's 24-hour adds or drops, most first, for one position or all of them. Players that are
 * not on Sleeper's list for that direction are left out (a missing count is not a zero).
 */
export function trendRows(
  players: PlayerListing[],
  direction: TrendDirection,
  position: TrendPosition,
  limit = 25,
): TrendRow[] {
  const listed = players
    .filter((p) => (position === "ALL" || p.position === position) && (p[direction] ?? 0) > 0)
    .sort((a, b) => (b[direction] ?? 0) - (a[direction] ?? 0) || a.name.localeCompare(b.name))
    .slice(0, limit);
  const top = listed.length > 0 ? (listed[0][direction] ?? 1) : 1;
  return listed.map((player, i) => {
    const count = player[direction] ?? 0;
    return { player, rank: i + 1, count, share: Math.max(4, Math.round((count / top) * 100)) };
  });
}
