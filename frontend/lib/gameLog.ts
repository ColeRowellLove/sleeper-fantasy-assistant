import type { PlayerDetail } from "./api";
import { matchupDifficulty, type Difficulty } from "./game";

/** How a week's rank among his position reads: top 12 is a starter's week, 13 to 24 is fine. */
export type RankTone = "great" | "ok" | "poor";

const GREAT_RANK = 12;
const OK_RANK = 24;

export function rankTone(rank: number | null | undefined): RankTone | null {
  if (rank === null || rank === undefined) return null;
  if (rank <= GREAT_RANK) return "great";
  return rank <= OK_RANK ? "ok" : "poor";
}

export interface LogRow {
  week: number;
  /** played: he has a line; upcoming: a game is still to come; bye: his team is off. */
  kind: "played" | "upcoming" | "bye";
  /** The NFL team he played for that week (a played week only). */
  team: string | null;
  opponent: string | null;
  home: boolean | null;
  /** How hard the opponent is for his position, for the colour (with the word in the title). */
  difficulty: Difficulty | null;
  points: number | null;
  rank: number | null;
  projected: number | null;
  final: boolean;
  stats: Record<string, number>;
}

/**
 * The whole season as rows, like Sleeper's game log: every week of his team's schedule (played,
 * still to come or bye), with the weeks he played filled in. Without a schedule it is just the
 * weeks he played.
 */
export function gameLogRows(detail: PlayerDetail): LogRow[] {
  const played = new Map(detail.weeks.map((w) => [w.week, w]));
  const schedule = new Map((detail.schedule ?? []).map((s) => [s.week, s]));
  const weeks = [...new Set([...played.keys(), ...schedule.keys()])].sort((a, b) => a - b);
  return weeks.map((week): LogRow => {
    const line = played.get(week);
    const plan = schedule.get(week);
    // the schedule is his current team's: a week played for a former team has no matching colour
    const sameOpponent = !line?.opponent || line.opponent === plan?.opponent;
    const difficulty = plan?.matchup && sameOpponent ? matchupDifficulty(plan.matchup) : null;
    if (line) {
      return {
        week,
        kind: "played",
        team: line.team ?? null,
        opponent: line.opponent ?? plan?.opponent ?? null,
        home: line.home ?? plan?.home ?? null,
        difficulty,
        points: line.points,
        rank: line.rank ?? null,
        projected: line.projected ?? null,
        final: Boolean(line.final),
        stats: line.stats,
      };
    }
    return {
      week,
      kind: plan?.bye ? "bye" : "upcoming",
      team: null,
      opponent: plan?.opponent ?? null,
      home: plan?.home ?? null,
      difficulty,
      points: null,
      rank: null,
      projected: null,
      final: false,
      stats: {},
    };
  });
}

/** "@PHI" away, "PHI" at home (Sleeper's way), null without an opponent. */
export function opponentText(row: Pick<LogRow, "opponent" | "home">): string | null {
  if (!row.opponent) return null;
  return `${row.home === false ? "@" : ""}${row.opponent}`;
}
