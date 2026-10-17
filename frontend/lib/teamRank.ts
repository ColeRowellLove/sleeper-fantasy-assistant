import type { TeamStat } from "./api";
import { ordinal } from "./game";

export type TeamRankTone = "great" | "ok" | "poor";

export interface RankChip {
  key: string;
  label: string;
  /** "17th", with the full phrase in `spoken`. */
  rank: string;
  /** Per game, as the table shows it. */
  value: string;
  spoken: string;
  tone: TeamRankTone;
}

/** Rank 1 is best. The best third of the teams is great, the worst third poor, the rest ok. */
export function teamRankTone(rank: number, teams: number): TeamRankTone {
  if (!(teams > 0)) return "ok";
  if (rank <= teams / 3) return "great";
  return rank > (teams * 2) / 3 ? "poor" : "ok";
}

/** One chip per team stat, like Sleeper's team rank row, coloured by where the team ranks. */
export function rankChips(stats: TeamStat[] | undefined): RankChip[] {
  return (stats ?? []).map((s) => ({
    key: s.key,
    label: s.label,
    rank: ordinal(s.rank),
    value: String(s.value),
    spoken: `${s.label}: ${ordinal(s.rank)} of ${s.teams} teams`,
    tone: teamRankTone(s.rank, s.teams),
  }));
}
