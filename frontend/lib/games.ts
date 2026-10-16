import type { GameCard, GamePlayer } from "./api";

export interface OrderedGame {
  card: GameCard;
  /** Players from the viewer's fantasy team in this game, your own first. */
  mine: GamePlayer[];
}

/**
 * Games with one of your players come first, most of your players first, then everything else
 * in kickoff order (the order the API gives). Within a game your players lead, then the other
 * rostered players, then the rest, each by points.
 */
export function orderGames(games: GameCard[], myRosterId: number | null): OrderedGame[] {
  const withMine = games.map((card) => {
    const mine =
      myRosterId === null ? [] : card.players.filter((p) => p.owner_roster_id === myRosterId);
    const rank = (p: GamePlayer) =>
      p.owner_roster_id === myRosterId && myRosterId !== null
        ? 0
        : p.owner_roster_id != null
          ? 1
          : 2;
    const players = [...card.players].sort(
      (a, b) =>
        rank(a) - rank(b) || (b.points ?? -1) - (a.points ?? -1) || a.name.localeCompare(b.name),
    );
    return { card: { ...card, players }, mine };
  });
  const yours = withMine
    .filter((g) => g.mine.length > 0)
    .sort((a, b) => b.mine.length - a.mine.length);
  const rest = withMine.filter((g) => g.mine.length === 0);
  return [...yours, ...rest];
}

/** "1 of your players" / "3 of your players", for the card summary. */
export function yourPlayersText(count: number): string {
  return `${count} of your ${count === 1 ? "player" : "players"}`;
}
