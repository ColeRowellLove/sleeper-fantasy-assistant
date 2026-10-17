import type { RankedPlayer } from "./api";

export const RANK_POSITIONS = ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF"] as const;
export type RankPosition = (typeof RANK_POSITIONS)[number];
export type RankAvailability = "all" | "available" | "mine";

/** The `sources` query value for a choice: empty when it is every available source. */
export function sourcesQuery(selected: string[], available: string[]): string {
  const chosen = available.filter((s) => selected.includes(s));
  return chosen.length === 0 || chosen.length === available.length ? "" : chosen.join(",");
}

/** Only well-formed source names go into a request. */
export function parseSources(value: string | string[] | undefined): string[] {
  const text = Array.isArray(value) ? value.join(",") : (value ?? "");
  return text
    .split(",")
    .filter((s) => /^[a-z]{1,20}$/.test(s))
    .slice(0, 8);
}

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

/** "projected 16.8 (5th RB); started in 17% of ESPN leagues" as separate short reasons. */
export function whyParts(why: string | null | undefined): string[] {
  return (why ?? "")
    .split(";")
    .map((part) => part.trim().replace(/\.$/, ""))
    .filter(Boolean);
}

// the table already has columns for these, so as chips they would only repeat a cell
const IN_A_COLUMN = [/^projected /, /a game over his last \d/, /^started in /];

/** The reasons that no column shows (the matchup, the betting line): the rest repeat the table. */
export function extraWhy(why: string | null | undefined): string[] {
  return whyParts(why).filter((part) => !IN_A_COLUMN.some((re) => re.test(part)));
}
