import type { GameConditions, GameInfo, MatchupRank } from "./api";

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

/**
 * "Sun, Oct 18, 1:00 PM EDT" in the viewer's own time zone. Only call this in the browser: the
 * server does not know the viewer's zone, so server output would differ from the first client render.
 */
export function formatKickoff(kickoff: string | null | undefined): string | null {
  if (!kickoff) return null;
  const parsed = new Date(kickoff);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export interface GameLabel {
  state: GameInfo["state"];
  /** Short label that is visible text (state is never conveyed by color alone). */
  text: string;
  /** Extra detail, e.g. the opponent and date. */
  detail: string | null;
}

/** `kickoffText` is the localized kickoff when known; the date alone is the fallback. */
/** "SEA 3 - DEN 14": the player's team first, so it reads from his side. Null without both numbers. */
export function scoreText(game: GameInfo): string | null {
  const { team, opponent, team_score: mine, opponent_score: theirs } = game;
  if (!team || !opponent || mine === null || mine === undefined) return null;
  if (theirs === null || theirs === undefined) return null;
  return `${team} ${mine} - ${opponent} ${theirs}`;
}

export function gameLabel(
  game: GameInfo | null | undefined,
  kickoffText: string | null = null,
): GameLabel | null {
  if (!game) return null;
  if (game.state === "bye") return { state: "bye", text: "Bye week", detail: null };

  const versus = game.opponent ? `${game.home === false ? "at" : "vs"} ${game.opponent}` : null;
  const date = kickoffText ?? formatGameDate(game.date);
  if (game.state === "upcoming") {
    return {
      state: "upcoming",
      text: "Upcoming",
      detail: [date, versus].filter(Boolean).join(" "),
    };
  }
  const score = scoreText(game);
  if (game.state === "live") {
    // the clock and the score when we have them, otherwise just the opponent
    const where = [game.period_text, score].filter(Boolean).join(", ");
    return { state: "live", text: "Live", detail: where || versus };
  }
  return { state: "final", text: "Played", detail: score ? `Final, ${score}` : versus };
}

/** 1 -> "1st", 2 -> "2nd", 3 -> "3rd", 11 -> "11th", 22 -> "22nd". */
export function ordinal(n: number): string {
  const lastTwo = n % 100;
  if (lastTwo >= 11 && lastTwo <= 13) return `${n}th`;
  const suffix = { 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th";
  return `${n}${suffix}`;
}

export interface MatchupText {
  /** Short visible text: "3rd". */
  text: string;
  /** The full sentence for a tooltip. */
  description: string;
  /** A short phrase for screen readers: "JAX ranks 3rd against RBs". */
  spoken: string;
}

/**
 * How hard the opponent is for a position, e.g. "3rd" for JAX against RBs. Rank 1 is the best
 * matchup: the defense that allows the most fantasy points to the position, or, for a team
 * defense (DEF), the offense that scores the fewest.
 */
export function matchupText(
  matchup: MatchupRank | null | undefined,
  position: string | null | undefined,
): MatchupText | null {
  if (!matchup) return null;
  const rank = ordinal(matchup.rank);
  const games = matchup.games === 1 ? "1 game" : `${matchup.games} games`;
  const numbers = `of ${matchup.teams} teams (${matchup.points} per game over ${games})`;
  if (matchup.side === "offense") {
    return {
      text: rank,
      spoken: `${matchup.opponent} offense ranks ${rank} easiest for a defense`,
      description: `${matchup.opponent} scores the ${rank} fewest fantasy points ${numbers}`,
    };
  }
  const spot = position ? ` to ${position}s` : "";
  return {
    text: rank,
    spoken: `${matchup.opponent} ranks ${rank} against ${position ? `${position}s` : "the position"}`,
    description: `${matchup.opponent} allows the ${rank} most fantasy points${spot} ${numbers}`,
  };
}

const WINDY_MPH = 15;
const FREEZING_F = 32;

/** "SF -3.5", "DAL +3.5" or "SF pick'em" for a team's spread. */
export function spreadText(team: string | null | undefined, spread: number): string {
  const who = team ? `${team} ` : "";
  if (spread === 0) return `${who}pick'em`;
  return `${who}${spread > 0 ? "+" : ""}${spread}`;
}

export interface ConditionsLabel {
  /** Roof and weather: "Dome" or "53°F, wind 15 mph (windy)". Null when unknown. */
  setting: string | null;
  /** The surface, "Grass"; null when unknown or compact. */
  surface: string | null;
  /** The betting line: "SF -3.5, O/U 44.5". Null when unknown. */
  line: string | null;
}

/**
 * Plain words for a game's conditions. Weather only applies outdoors; a dome or closed roof says
 * so instead. Every state is text, so nothing relies on color.
 */
export function conditionsLabel(
  game: GameInfo | null | undefined,
  compact = false,
): ConditionsLabel | null {
  const c: GameConditions | null | undefined = game?.conditions;
  if (!game || !c || game.state === "bye") return null;
  const indoors = c.roof === "dome" || c.roof === "closed";
  let setting: string | null = null;
  if (indoors) {
    setting = c.roof === "closed" ? "Closed roof" : "Dome";
  } else {
    const parts: string[] = [];
    if (c.temp !== null && c.temp !== undefined) {
      parts.push(`${c.temp}°F${c.temp <= FREEZING_F ? " (freezing)" : ""}`);
    }
    if (c.wind !== null && c.wind !== undefined) {
      parts.push(`wind ${c.wind} mph${c.wind >= WINDY_MPH ? " (windy)" : ""}`);
    }
    setting = parts.length > 0 ? parts.join(", ") : c.roof === "outdoors" ? "Outdoors" : null;
  }
  const surface = !compact && c.surface ? c.surface[0].toUpperCase() + c.surface.slice(1) : null;
  const bits: string[] = [];
  if (c.spread !== null && c.spread !== undefined) bits.push(spreadText(game.team, c.spread));
  if (c.total !== null && c.total !== undefined) bits.push(`O/U ${c.total}`);
  const line = compact ? null : bits.length > 0 ? bits.join(", ") : null;
  if (!setting && !surface && !line) return null;
  return { setting, surface, line };
}
