import type { LineupPlayer, Lineups, TeamLineup } from "./api";

type Matchup = Lineups["matchups"][number];

export type WeekState = "played" | "current" | "upcoming";

/** Played weeks are over, the current NFL week is in progress, later weeks have not started. */
export function weekState(week: number, currentWeek: number | null | undefined): WeekState {
  if (currentWeek == null) return "played";
  if (week < currentWeek) return "played";
  return week === currentWeek ? "current" : "upcoming";
}

/** Your matchup first (stable otherwise), so the page opens on what matters to you. */
export function orderMatchups(matchups: Matchup[], myRosterId: number | null): Matchup[] {
  if (myRosterId === null) return matchups;
  const mine = matchups.filter((m) => m.teams.some((t) => t.roster_id === myRosterId));
  return [...mine, ...matchups.filter((m) => !mine.includes(m))];
}

/** Puts your team on the left of your own matchup; other matchups keep their order. */
export function orientMatchup(matchup: Matchup, myRosterId: number | null): Matchup {
  if (myRosterId === null) return matchup;
  const mineIndex = matchup.teams.findIndex((t) => t.roster_id === myRosterId);
  if (mineIndex <= 0) return matchup;
  const teams = [matchup.teams[mineIndex], ...matchup.teams.filter((_, i) => i !== mineIndex)];
  return { ...matchup, teams };
}

export function isMine(matchup: Matchup, myRosterId: number | null): boolean {
  return myRosterId !== null && matchup.teams.some((t) => t.roster_id === myRosterId);
}

type RowKind = "starter" | "bench" | "ir" | "taxi";

export interface PairedRow {
  /** Lineup slot (QB, RB, FLEX, ...) or the group name: Bench, IR, Taxi. */
  slot: string;
  left: LineupPlayer | null;
  right: LineupPlayer | null;
  kind: RowKind;
}

// Non-starters, in display order. The API labels IR and taxi players separately from the bench.
const PARKED: { slot: string; label: string; kind: Exclude<RowKind, "starter"> }[] = [
  { slot: "BN", label: "Bench", kind: "bench" },
  { slot: "IR", label: "IR", kind: "ir" },
  { slot: "TAXI", label: "Taxi", kind: "taxi" },
];

/** Lines the two teams up row by row: starters by slot, then bench, then IR, then taxi. */
export function pairRows(left: TeamLineup, right: TeamLineup): PairedRow[] {
  const rows: PairedRow[] = [];
  const starters = Math.max(left.starters.length, right.starters.length);
  for (let i = 0; i < starters; i++) {
    const l = left.starters[i] ?? null;
    const r = right.starters[i] ?? null;
    rows.push({ slot: l?.slot ?? r?.slot ?? "", left: l, right: r, kind: "starter" });
  }
  const isParked = (p: LineupPlayer) => PARKED.some((g) => g.slot !== "BN" && g.slot === p.slot);
  for (const group of PARKED) {
    // anything that is not explicitly IR or taxi counts as bench, so no player can be dropped
    const inGroup = (p: LineupPlayer) => (group.slot === "BN" ? !isParked(p) : p.slot === group.slot);
    const l = left.bench.filter(inGroup);
    const r = right.bench.filter(inGroup);
    for (let i = 0; i < Math.max(l.length, r.length); i++) {
      rows.push({ slot: group.label, left: l[i] ?? null, right: r[i] ?? null, kind: group.kind });
    }
  }
  return rows;
}

/** The team with more points, or null for a tie or when nobody has scored. */
export function winnerId(a: TeamLineup, b: TeamLineup): number | null {
  if (a.points === b.points) return null;
  return a.points > b.points ? a.roster_id : b.roster_id;
}

export function formatPoints(value: number | null): string {
  return value === null ? "–" : value.toFixed(2);
}
