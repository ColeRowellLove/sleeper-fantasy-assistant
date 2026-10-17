import type { GameCard, GamePlayer } from "./api";
import { formatStat, statColumns } from "./playerDetail";

export interface Performer {
  player: GamePlayer;
  points: number;
  /** "SEA 14 - DEN 17" from the game he played in, null when there is no score. */
  game: string | null;
  /** His three main stats for his position: label and value. */
  stats: { label: string; value: string }[];
}

/**
 * The best fantasy games of the week across all NFL games: players who have played (never a
 * projection), most points first, each with his game's score and his three main stats.
 */
export function topPerformers(cards: GameCard[], limit = 8): Performer[] {
  const all: Performer[] = [];
  for (const card of cards) {
    const { team_score: home, opponent_score: away } = card.game;
    const hasScore = home !== null && home !== undefined && away !== null && away !== undefined;
    const game = hasScore ? `${card.away} ${away} - ${card.home} ${home}` : null;
    for (const player of card.players) {
      if (player.projected || player.points === null || player.points === undefined) continue;
      if (player.points <= 0) continue;
      const stats = statColumns([player.stats ?? {}], player.position)
        .slice(0, 3)
        .map((c) => ({ label: c.label, value: formatStat(player.stats?.[c.key]) }));
      all.push({ player, points: player.points, game, stats });
    }
  }
  return all
    .sort((a, b) => b.points - a.points || a.player.name.localeCompare(b.player.name))
    .slice(0, limit);
}
