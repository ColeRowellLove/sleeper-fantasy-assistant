export interface LeagueSummary {
  league_id: string;
  name: string;
  season: string;
  total_rosters: number;
}

export interface UserLeagues {
  user_id: string;
  display_name: string;
  leagues: LeagueSummary[];
}

export interface ConnectedLeague extends LeagueSummary {
  rules: {
    reception_scoring: string;
    uses_faab: boolean;
    trade_deadline_week: number | null;
    playoff_teams: number | null;
  };
}

export interface LeagueSettings {
  league_id: string;
  name: string;
  season: string;
  total_rosters: number;
  /** Sleeper's league settings exactly as sent (numbers, mostly 0/1 flags). */
  settings: Record<string, number | string | boolean | null>;
  scoring_settings: Record<string, number>;
  roster_positions: string[];
}

export interface PlayerListing {
  player_id: string;
  name: string;
  position: string;
  team: string | null;
  injury?: InjuryInfo | null;
  game?: GameInfo | null;
  /** Roster that has the player in this league; null means available. */
  owner_roster_id: number | null;
  owner_team: string | null;
  /** Sleeper's 24-hour adds and drops (top 100 only); null = not on that list. */
  adds: number | null;
  drops: number | null;
  /** This season's points under the league's scoring. */
  total_points: number;
  /** Rank within position by total points; null until the player has points. */
  rank: number | null;
  projected: number | null;
  /** ESPN-wide share of leagues that roster / start the player (not Sleeper's). */
  owned_pct?: number | null;
  started_pct?: number | null;
}

export interface PlayersData {
  league_id: string;
  week: number | null;
  trends_updated_at?: string | null;
  players: PlayerListing[];
}

export interface PlayerDetail {
  player_id: string;
  name: string;
  position: string | null;
  team: string | null;
  injury?: InjuryInfo | null;
  game?: GameInfo | null;
  /** This week's opponent against his position. */
  matchup?: MatchupRank | null;
  bio?: Record<string, unknown> | null;
  owner_roster_id?: number | null;
  owner_team?: string | null;
  /** The owning manager's Sleeper username, and the league, for linking to their roster. */
  owner_manager?: string | null;
  league_id?: string | null;
  /** ESPN-wide ownership and start shares in percent (not Sleeper leagues); null = no number. */
  owned_pct?: number | null;
  started_pct?: number | null;
  adds?: number | null;
  drops?: number | null;
  season: { points: number; games: number; average?: number | null; rank?: number | null };
  projected?: { week: number; points: number; stats: Record<string, number> } | null;
  weeks: {
    week: number;
    /** The NFL team he played for that week. */
    team?: string | null;
    opponent?: string | null;
    home?: boolean | null;
    points: number;
    stats: Record<string, number>;
    /** Projected before kickoff; null/absent when none was stored. */
    projected?: number | null;
    /** The game is over, so points can be compared with the projection. */
    final?: boolean;
  }[];
  past_seasons: {
    season: string;
    games: number;
    points: number;
    rank?: number | null;
    /** The teams he played for that season, in order. */
    teams?: string[];
    /** Game by game, with the team and opponent for each. */
    log?: PlayerDetail["weeks"];
  }[];
}

export interface DepthPlayer {
  name: string;
  player_id?: string | null;
  depth: number;
  label: string;
  injury?: InjuryInfo | null;
  owner_roster_id?: number | null;
  owner_team?: string | null;
  next_up?: boolean;
}

export interface DepthSlot {
  slot: string;
  label: string;
  skill?: boolean;
  note?: string | null;
  players: DepthPlayer[];
}

export interface DepthGroup {
  group: "offense" | "defense" | "special";
  title: string;
  slots: DepthSlot[];
}

export interface TeamDepth {
  team: string;
  source?: string | null;
  updated_at?: string | null;
  game?: GameInfo | null;
  groups: DepthGroup[];
}

export class ApiError extends Error {}

const USERNAME_RE = /^[A-Za-z0-9_.]{1,40}$/;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Could not reach the server. Please try again.");
  }
  if (!res.ok) {
    if (res.status === 404) throw new ApiError("We couldn't find that on Sleeper.");
    if (res.status === 422) throw new ApiError("That doesn't look right. Please check it.");
    throw new ApiError("Sleeper is unavailable right now. Please try again shortly.");
  }
  return (await res.json()) as T;
}

export function isValidUsername(username: string): boolean {
  return USERNAME_RE.test(username);
}

export async function listLeagues(username: string): Promise<UserLeagues> {
  const data = await request<UserLeagues | LeagueSummary[]>(
    `/api/users/${encodeURIComponent(username)}/leagues`,
  );
  // Web and API deploy as separate projects; tolerate the API's previous bare-array response
  // during a release so the form never breaks mid-deploy.
  if (Array.isArray(data)) return { user_id: "", display_name: "", leagues: data };
  return data;
}

export function connectLeague(leagueId: string): Promise<ConnectedLeague> {
  return request(`/api/leagues/${encodeURIComponent(leagueId)}/connect`, { method: "POST" });
}

export interface StandingsRow {
  rank: number;
  roster_id: number;
  team: string;
  /** The manager's Sleeper username; the team name is what they chose in Sleeper. */
  manager?: string | null;
  owner_id: string | null;
  wins: number;
  losses: number;
  ties: number;
  points_for: number;
  points_against: number;
  /** Current run as Sleeper reports it: "3W", "2L" or "1T". */
  streak?: string | null;
}

export interface GameInfo {
  state: "upcoming" | "live" | "final" | "bye";
  date: string | null;
  /** ISO UTC timestamp; absent until the schedule publishes a time. */
  kickoff?: string | null;
  /** The NFL team this game is for, and the score from that team's side once it has started. */
  team?: string | null;
  team_score?: number | null;
  opponent_score?: number | null;
  /** Where a live game is ("Q2 2:24", "Halftime"), or "Final". */
  period_text?: string | null;
  /** Share of the game played, 0 to 1; null/absent when the clock is unknown. */
  elapsed?: number | null;
  opponent: string | null;
  home: boolean | null;
}

/** How the opponent's defense ranks against a player's position: 1 = allows the most points. */
export interface MatchupRank {
  opponent: string;
  rank: number;
  teams: number;
  /** Fantasy points per game: allowed to the position, or scored by the offense a defense faces. */
  points: number;
  /** "offense" for a team defense: ranked by the points the opposing offense scores. */
  side?: "defense" | "offense";
  /** Completed games counted. */
  games: number;
}

export interface InjuryInfo {
  status: string;
  body_part: string | null;
}

export type RosterStatus = "starter" | "bench" | "ir" | "taxi";

export interface RosterPlayer {
  player_id: string;
  name: string;
  position: string | null;
  team: string | null;
  status: RosterStatus;
  slot: string | null;
  game?: GameInfo | null;
  injury?: InjuryInfo | null;
  /** Projected points this week under the league's scoring; null/absent = no projection. */
  projected?: number | null;
  /** Actual points this week once the game has started; null/absent before then. */
  points?: number | null;
  /** The projection frozen before kickoff (`projected` is live: the score once the game is over). */
  projected_pregame?: number | null;
  /** The opponent's defense rank against his position; null/absent on a bye or without data. */
  matchup?: MatchupRank | null;
}

export interface LineupPlayer {
  slot: string;
  player_id: string | null;
  name: string;
  position: string | null;
  team: string | null;
  points: number | null;
  game?: GameInfo | null;
  injury?: InjuryInfo | null;
  /** Projected points under the league's scoring; 0 when nothing is projected. */
  projected?: number | null;
  /** No projection was stored, so the 0 above is an assumption. */
  projection_missing?: boolean;
  /** The projection frozen before kickoff (`projected` is live: the score once the game is over). */
  projected_pregame?: number | null;
  /** The opponent's defense rank against his position; null/absent on a bye or without data. */
  matchup?: MatchupRank | null;
}

export interface TeamLineup {
  roster_id: number;
  team: string;
  owner_id: string | null;
  points: number;
  /** Sum of the starters' projections; null/absent when none has one. */
  projected?: number | null;
  /** The sum of the starters' projections frozen before kickoff. */
  projected_pregame?: number | null;
  /** Chance to win from projected points, 0 to 1; null/absent when there is nothing fair to say. */
  win_probability?: number | null;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
}

export interface Lineups {
  week: number | null;
  current_week?: number | null;
  weeks: number[];
  matchups: { matchup_id: number | null; teams: TeamLineup[] }[];
}

export interface Dashboard {
  league_id: string;
  name: string;
  season: string;
  week?: number | null;
  standings: StandingsRow[];
  rosters: {
    roster_id: number;
    team: string;
    owner_id: string | null;
    players: RosterPlayer[];
  }[];
  rules: ConnectedLeague["rules"];
}
