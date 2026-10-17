import type { PlayerDetail } from "./api";
import type { Difficulty } from "./game";
import { gameLogRows, opponentText } from "./gameLog";
import { rankText } from "./playerDetail";

/** "88.0%", or a dash when there is no number (never 0, which would be a claim). */
export function percentText(n: number | null | undefined): string {
  return n === null || n === undefined ? "–" : `${n.toFixed(1)}%`;
}

/** "1,204", or a dash when there is no number. */
export function countText(n: number | null | undefined): string {
  return n === null || n === undefined ? "–" : n.toLocaleString("en-US");
}

export interface SummaryStat {
  label: string;
  value: string;
  /** What the number is, for a tooltip and screen readers when the label is short. */
  title?: string;
}

/** The numbers at the top of the Summary tab, in reading order. */
export function summaryStats(detail: PlayerDetail): SummaryStat[] {
  const average = detail.season.average;
  return [
    { label: "Rank", value: rankText(detail.position, detail.season.rank), title: "Position rank" },
    {
      label: "Pts/game",
      value: average === null || average === undefined ? "–" : average.toFixed(1),
      title: "Points per game",
    },
    { label: "Points", value: detail.season.points.toFixed(1), title: "Season points" },
    { label: "Games", value: String(detail.season.games), title: "Games played" },
    { label: "Owned", value: percentText(detail.owned_pct), title: "Owned % (ESPN)" },
    { label: "Started", value: percentText(detail.started_pct), title: "Started % (ESPN)" },
  ];
}

export interface ProjectionCard {
  week: number;
  /** "SEA" at home, "@SF" away; null on a bye. */
  opponent: string | null;
  difficulty: Difficulty | null;
  bye: boolean;
  /** Projected points, or null when none is stored for that week. */
  projected: number | null;
  /** Points actually scored, only once the game is over. */
  final: number | null;
}

/**
 * One card per week of the season, like Sleeper's projections strip: the opponent, what was
 * projected and what he scored. The coming week's projection is the live one, the rest come from
 * the projections stored before kickoff.
 */
export function projectionCards(detail: PlayerDetail): ProjectionCard[] {
  return gameLogRows(detail).map((row) => {
    const live = detail.projected && detail.projected.week === row.week ? detail.projected : null;
    return {
      week: row.week,
      opponent: opponentText(row),
      difficulty: row.difficulty,
      bye: row.kind === "bye",
      projected: row.projected ?? live?.points ?? null,
      final: row.kind === "played" && row.final ? row.points : null,
    };
  });
}
