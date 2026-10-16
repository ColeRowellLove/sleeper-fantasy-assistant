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

// The easiest quarter of teams are "easy" matchups and the hardest quarter "tough".
const QUARTILE = 0.25;

export type Difficulty = "easy" | "average" | "tough";

/** How hard a matchup is: rank 1 is the best matchup for the player (see matchupText). */
export function matchupDifficulty(matchup: MatchupRank): Difficulty {
  if (!(matchup.teams > 0)) return "average"; // no sensible team count: say nothing strong
  if (matchup.rank <= matchup.teams * QUARTILE) return "easy";
  if (matchup.rank > matchup.teams * (1 - QUARTILE)) return "tough";
  return "average";
}

const DIFFICULTY_WORD: Record<Difficulty, string> = {
  easy: "Easy",
  average: "Average",
  tough: "Tough",
};

export interface MatchupText {
  /** How hard it is, for the colour: green easy, amber average, red tough. */
  difficulty: Difficulty;
  /** The same in a word, so colour is never the only cue: "Easy". */
  word: string;
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
  const difficulty = matchupDifficulty(matchup);
  const word = DIFFICULTY_WORD[difficulty];
  const rank = ordinal(matchup.rank);
  const games = matchup.games === 1 ? "1 game" : `${matchup.games} games`;
  const numbers = `of ${matchup.teams} teams (${matchup.points} per game over ${games})`;
  if (matchup.side === "offense") {
    return {
      difficulty,
      word,
      text: rank,
      spoken: `${matchup.opponent} offense ranks ${rank} easiest for a defense (${word.toLowerCase()} matchup)`,
      description: `${matchup.opponent} scores the ${rank} fewest fantasy points ${numbers}`,
    };
  }
  const spot = position ? ` to ${position}s` : "";
  return {
    difficulty,
    word,
    text: rank,
    spoken: `${matchup.opponent} ranks ${rank} against ${position ? `${position}s` : "the position"} (${word.toLowerCase()} matchup)`,
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

export type Unit = "offense" | "defense";

const OFFENSE_POSITIONS = new Set(["QB", "RB", "WR", "TE"]);
// the team defense and, in leagues that use them, individual defenders
const DEFENSE_POSITIONS = new Set(["DEF", "DL", "DE", "DT", "LB", "DB", "CB", "S"]);

/** The situation of a live game with someone known to have the ball; null otherwise. */
function liveSituation(game: GameInfo | null | undefined) {
  if (!game || game.state !== "live" || !game.situation) return null;
  // halftime and the end of a quarter: nobody is on the field, whatever was last reported
  if (/half|end/i.test(game.period_text ?? "")) return null;
  const s = game.situation;
  return s.possession || s.ball_on || s.down_distance || s.red_zone ? s : null;
}

/**
 * Which unit of a team is on the field right now: the offense when the team has the ball, the
 * defense when the other team does. Null when the game is not live or the ball is unknown.
 */
export function unitOnField(
  game: GameInfo | null | undefined,
  team: string | null | undefined,
): Unit | null {
  const s = liveSituation(game);
  if (!s?.possession || !team) return null;
  return s.possession === team ? "offense" : "defense";
}

/** "Offense on field" / "Defense on field" for a player whose unit is on the field now. */
export function playerUnitLabel(
  game: GameInfo | null | undefined,
  position: string | null | undefined,
): string | null {
  const unit = unitOnField(game, game?.team);
  if (unit === "offense" && position && OFFENSE_POSITIONS.has(position)) return "Offense on field";
  if (unit === "defense" && position && DEFENSE_POSITIONS.has(position)) {
    return "Defense on field";
  }
  return null;
}

export interface SituationLabel {
  /** Just the spot, "Ball on DEN 18"; for a row where the full line would repeat. */
  spot: string | null;
  /** "SEA have the ball · 3rd & 4 · at DEN 18", or "Ball on DEN 18" when only the spot is known. */
  text: string | null;
  redZone: boolean;
}

/** Plain words for where a live game's ball is. Null unless the game is live and ESPN said something. */
export function situationLabel(game: GameInfo | null | undefined): SituationLabel | null {
  const s = liveSituation(game);
  if (!s) return null;
  const parts: string[] = [];
  if (s.possession) parts.push(`${s.possession} have the ball`);
  if (s.down_distance) parts.push(s.down_distance);
  if (s.ball_on) parts.push(s.possession ? `at ${s.ball_on}` : `Ball on ${s.ball_on}`);
  return {
    text: parts.length > 0 ? parts.join(" · ") : null,
    spot: s.ball_on ? `Ball on ${s.ball_on}` : null,
    redZone: s.red_zone === true,
  };
}

/** An upcoming game this close to (or past) its kickoff is about to be live. */
const SOON_MS = 60 * 60 * 1000;

/**
 * Whether a page should start refreshing itself: any of the given games (any number of lists, with
 * gaps) is live, or is upcoming but within an hour of kickoff or already past it, so a page opened
 * before the games starts updating by itself when they begin.
 */
export function needsLiveRefresh(
  lists: (GameInfo | null | undefined)[][],
  now: number = Date.now(),
): boolean {
  return lists.some((games) =>
    games.some((game) => {
      if (!game) return false;
      if (game.state === "live") return true;
      if (game.state !== "upcoming" || !game.kickoff) return false;
      const kickoff = Date.parse(game.kickoff);
      return Number.isFinite(kickoff) && kickoff - now <= SOON_MS && now - kickoff < 8 * SOON_MS;
    }),
  );
}
