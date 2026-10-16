import type { RankedPlayer } from "./api";

export const RANK_POSITIONS = ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF"] as const;
export type RankPosition = (typeof RANK_POSITIONS)[number];
export type RankAvailability = "all" | "available" | "mine";

export function parseRankPosition(value: string | null | undefined): RankPosition {
  return RANK_POSITIONS.find((p) => p === value) ?? "RB";
}

/**
 * The players to show for a position (FLEX pools RB, WR and TE), best first. `available` keeps
 * players no one in the league has; `mine` keeps the players on the viewer's team.
 */
export function rankedFor(
  players: RankedPlayer[],
  position: RankPosition,
  availability: RankAvailability,
  myRosterId: number | null,
): RankedPlayer[] {
  const flex = position === "FLEX";
  return players
    .filter((p) => (flex ? p.flex_rank != null : p.position === position))
    .filter((p) => {
      if (availability === "available") return p.owner_roster_id == null;
      if (availability === "mine") return myRosterId !== null && p.owner_roster_id === myRosterId;
      return true;
    })
    .sort((a, b) =>
      flex
        ? (a.flex_rank ?? 0) - (b.flex_rank ?? 0) || a.name.localeCompare(b.name)
        : a.rank - b.rank || a.name.localeCompare(b.name),
    );
}

/** "3 of 3 signals agree within 2 places" style summary of how much the sources agree. */
export function agreementText(p: Pick<RankedPlayer, "sources" | "spread">): string {
  if (p.sources === 1) return "1 source";
  if (p.spread === 0) return `${p.sources} sources agree`;
  return `${p.sources} sources, ${p.spread} ${p.spread === 1 ? "place" : "places"} apart`;
}
