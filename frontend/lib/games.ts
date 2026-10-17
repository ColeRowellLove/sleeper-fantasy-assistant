import type { GameCard, GamePlayer } from "./api";
import { TEAM_NAMES } from "./depth";

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

/** "Texans" from "HOU": the team's nickname, which is what fits on a phone row; the code if unknown. */
export function teamNickname(code: string): string {
  const full = TEAM_NAMES[code];
  return full ? (full.split(" ").pop() ?? code) : code;
}

export interface GameSection {
  key: string;
  /** "Your games" or a day like "Sunday, Oct 18". */
  title: string;
  games: OrderedGame[];
}

/**
 * Your games first (they are what the owner opens this page for), then one section per day in
 * kickoff order, like Sleeper's schedule. A game with no date goes last under its own heading.
 */
export function groupGames(ordered: OrderedGame[]): GameSection[] {
  const yours = ordered.filter((g) => g.mine.length > 0);
  const rest = ordered.filter((g) => g.mine.length === 0);
  const sections: GameSection[] = [];
  if (yours.length > 0) sections.push({ key: "mine", title: "Your games", games: yours });
  const days = new Map<string, OrderedGame[]>();
  for (const game of rest) {
    const day = game.card.game.date ?? "";
    days.set(day, [...(days.get(day) ?? []), game]);
  }
  const keys = [...days.keys()].sort((a, b) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b)));
  for (const day of keys) {
    sections.push({
      key: day || "tbd",
      title: day ? (longDay(day) ?? day) : "Date to be set",
      games: days.get(day) ?? [],
    });
  }
  return sections;
}

/** "Sunday, Oct 18" from an ISO date (UTC, so the server and the browser agree). */
export function longDay(date: string): string | null {
  const parsed = new Date(`${date}T12:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
