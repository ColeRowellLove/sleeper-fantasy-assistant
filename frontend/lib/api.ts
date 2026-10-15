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
  opponent: string | null;
  home: boolean | null;
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
}

export interface TeamLineup {
  roster_id: number;
  team: string;
  owner_id: string | null;
  points: number;
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
