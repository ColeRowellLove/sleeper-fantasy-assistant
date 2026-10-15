export interface LeagueSummary {
  league_id: string;
  name: string;
  season: string;
  total_rosters: number;
}

export interface ConnectedLeague extends LeagueSummary {
  rules: {
    reception_scoring: string;
    uses_faab: boolean;
    trade_deadline_week: number | null;
    playoff_teams: number | null;
  };
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

export function listLeagues(username: string): Promise<LeagueSummary[]> {
  return request(`/api/users/${encodeURIComponent(username)}/leagues`);
}

export function connectLeague(leagueId: string): Promise<ConnectedLeague> {
  return request(`/api/leagues/${encodeURIComponent(leagueId)}/connect`, { method: "POST" });
}

export interface StandingsRow {
  rank: number;
  roster_id: number;
  team: string;
  wins: number;
  losses: number;
  ties: number;
  points_for: number;
  points_against: number;
}

export type RosterStatus = "starter" | "bench" | "ir" | "taxi";

export interface RosterPlayer {
  player_id: string;
  name: string;
  position: string | null;
  team: string | null;
  status: RosterStatus;
  slot: string | null;
}

export interface LineupPlayer {
  slot: string;
  player_id: string | null;
  name: string;
  position: string | null;
  team: string | null;
  points: number | null;
}

export interface TeamLineup {
  roster_id: number;
  team: string;
  points: number;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
}

export interface Lineups {
  week: number | null;
  weeks: number[];
  matchups: { matchup_id: number | null; teams: TeamLineup[] }[];
}

export interface Dashboard {
  league_id: string;
  name: string;
  season: string;
  standings: StandingsRow[];
  rosters: { roster_id: number; team: string; players: RosterPlayer[] }[];
  rules: ConnectedLeague["rules"];
}
