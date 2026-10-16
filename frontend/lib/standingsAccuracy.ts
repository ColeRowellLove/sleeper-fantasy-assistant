import type { LineupAccuracy, StandingsRow } from "./api";

/** The standings with each team's sit vs start accuracy beside its record (unchanged when none). */
export function withAccuracy(
  standings: StandingsRow[],
  accuracy: LineupAccuracy | null | undefined,
): StandingsRow[] {
  if (!accuracy) return standings;
  const byTeam = new Map(accuracy.teams.map((t) => [t.roster_id, t]));
  return standings.map((row) => {
    const found = byTeam.get(row.roster_id);
    return found ? { ...row, accuracy: found.accuracy, left_on_bench: found.left_on_bench } : row;
  });
}
