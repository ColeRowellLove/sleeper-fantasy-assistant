import type { GameInfo } from "./api";

/** "Sun, Sep 20" from an ISO date. Always UTC so server and browser render the same text. */
export function formatGameDate(date: string | null): string | null {
  if (!date) return null;
  const parsed = new Date(`${date}T12:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export interface GameLabel {
  state: GameInfo["state"];
  /** Short label that is visible text (state is never conveyed by color alone). */
  text: string;
  /** Extra detail, e.g. the opponent and date. */
  detail: string | null;
}

export function gameLabel(game: GameInfo | null | undefined): GameLabel | null {
  if (!game) return null;
  if (game.state === "bye") return { state: "bye", text: "Bye week", detail: null };

  const versus = game.opponent ? `${game.home === false ? "at" : "vs"} ${game.opponent}` : null;
  const date = formatGameDate(game.date);
  if (game.state === "upcoming") {
    return { state: "upcoming", text: "Upcoming", detail: [date, versus].filter(Boolean).join(" ") };
  }
  if (game.state === "live") return { state: "live", text: "Live", detail: versus };
  return { state: "final", text: "Played", detail: versus };
}
