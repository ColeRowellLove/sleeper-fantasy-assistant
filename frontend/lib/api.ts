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
  /** Last week's points; null when he did not play. */
  last_points?: number | null;
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
  /** His team's numbers that matter for his position, ranked. */
  team_stats?: TeamStat[];
  /** His team's depth chart, for the Team tab. */
  depth?: TeamDepth | null;
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
    /** His rank among players at his position that week (1 = best). */
    rank?: number | null;
  }[];
  /** Every week of the season for his team: the opponent and how hard it is, or a bye. */
  schedule?: {
    week: number;
    opponent?: string | null;
    home?: boolean | null;
    bye?: boolean;
    matchup?: MatchupRank | null;
  }[];
  /** Recent headlines that name him. */
  news?: NewsItem[];
  /** His adds and drops in this league, newest first. */
  history?: {
    kind: "added" | "dropped";
    source: "waivers" | "free_agency" | "trade" | "commissioner";
    manager?: string | null;
    date?: string | null;
    week: number;
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

/** A team's season record from its finished games. */
export interface TeamRecord {
  wins: number;
  losses: number;
  ties: number;
}

export interface TeamDepth {
  team: string;
  source?: string | null;
  updated_at?: string | null;
  game?: GameInfo | null;
  /** Wins, losses and ties; absent unless every finished game has a score. */
  record?: TeamRecord | null;
  /** The team's per-game numbers with league ranks. */
  stats?: TeamStat[];
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
  /** Sit vs start accuracy (points over Sleeper's potential points, 0 to 1); added from /accuracy. */
  accuracy?: number | null;
  /** Points left on the bench, from Sleeper's potential points. */
  left_on_bench?: number | null;
}

/** Who has the ball and where, for a game in progress (ESPN's live scoreboard). */
interface GameSituation {
  /** The team code with the ball. */
  possession?: string | null;
  /** "1st & 10" */
  down_distance?: string | null;
  /** "DEN 35": the yard line and the side of the field. */
  ball_on?: string | null;
  /** The offense is inside the opponent's 20. */
  red_zone?: boolean;
}

/** The setting of a game, from the player's team's side. Any part can be missing. */
export interface GameConditions {
  roof?: string | null;
  surface?: string | null;
  stadium?: string | null;
  /** Degrees Fahrenheit (outdoor games). */
  temp?: number | null;
  /** Miles per hour (outdoor games). */
  wind?: number | null;
  /** This team's spread: -3.5 favoured by 3.5, +3.5 an underdog. */
  spread?: number | null;
  /** The over/under. */
  total?: number | null;
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
  conditions?: GameConditions | null;
  /** Only while the game is live and ESPN reports it. */
  situation?: GameSituation | null;
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

/** One team stat per game and where it ranks of the teams; rank 1 is best. */
export interface TeamStat {
  key: string;
  label: string;
  side: "offense" | "defense";
  value: number;
  rank: number;
  teams: number;
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
  /** How he did once his game has started, e.g. "18 car, 92 yds, 1 TD"; absent before kickoff. */
  stat_line?: string | null;
  /** True when `stat_line` is what he is projected to do (his game has not started). */
  stat_line_projected?: boolean;
  /** ESPN-wide shares of leagues that roster and start him; absent without a number. */
  owned_pct?: number | null;
  started_pct?: number | null;
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
  /** How he did once his game has started, e.g. "18 car, 92 yds, 1 TD"; absent before kickoff. */
  stat_line?: string | null;
  /** True when `stat_line` is what he is projected to do (his game has not started). */
  stat_line_projected?: boolean;
}

export interface TeamLineup {
  roster_id: number;
  team: string;
  /** The team's picture (a Sleeper image URL), when it has one. */
  avatar?: string | null;
  owner_id: string | null;
  points: number;
  /** Sum of the starters' projections; null/absent when none has one. */
  projected?: number | null;
  /** The sum of the starters' projections frozen before kickoff. */
  projected_pregame?: number | null;
  /** Chance to win from projected points, 0 to 1; null/absent when there is nothing fair to say. */
  win_probability?: number | null;
  win_probability_rough?: boolean;
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

/** Sit vs start accuracy for one team, from the totals Sleeper reports on its roster. */
interface TeamAccuracy {
  roster_id: number;
  team: string;
  /** Sleeper's season points for the team. */
  points: number;
  /** Sleeper's potential points: what the best lineups would have scored. Null if not reported. */
  potential: number | null;
  /** Points over potential, 0 to 1; null when Sleeper reports no potential points. */
  accuracy: number | null;
  left_on_bench: number | null;
}

export interface LineupAccuracy {
  league_id: string;
  /** Most accurate first; teams without a figure last. */
  teams: TeamAccuracy[];
}

export interface RankedPlayer {
  player_id: string;
  name: string;
  position: string;
  team: string | null;
  injury?: InjuryInfo | null;
  game?: GameInfo | null;
  matchup?: MatchupRank | null;
  owner_roster_id?: number | null;
  owner_team?: string | null;
  projected?: number | null;
  /** Points per game over his last three games. */
  form?: number | null;
  /** ESPN-wide share of leagues that start him, in percent. */
  started_pct?: number | null;
  /** The points the betting line implies for his team this week. */
  implied_points?: number | null;
  /** Rank within the position from each signal that has him. */
  signal_ranks: Record<string, number>;
  /** Consensus rank within the position, and among RB, WR and TE together. */
  rank: number;
  flex_rank?: number | null;
  /** Average of the signal ranks (lower is better) and the gap between the best and worst. */
  score: number;
  spread: number;
  sources: number;
  why: string;
}

export interface Rankings {
  league_id: string;
  week: number | null;
  current_week: number | null;
  weeks: number[];
  /** The signals available this week: key -> label. */
  signals: Record<string, string>;
  /** The signals the ranks were computed from. */
  selected?: string[];
  /** Sources asked for that are not connected yet, with the reason. */
  unavailable?: Record<string, string>;
  players: RankedPlayer[];
}

/** A player in the Start/Sit tool, with the numbers the recommendation used. */
export interface StartSitCandidate {
  player_id: string;
  name: string;
  position: string | null;
  team: string | null;
  injury?: InjuryInfo | null;
  game?: GameInfo | null;
  matchup?: MatchupRank | null;
  projected?: number | null;
  form?: number | null;
  started_pct?: number | null;
  rank?: number | null;
  score?: number | null;
  sources: number;
  /** Why he cannot be recommended (an injury, a bye, no projection); null when he can. */
  out?: string | null;
}

export interface StartSitComparison {
  league_id: string;
  week: number | null;
  /** Best first. */
  candidates: StartSitCandidate[];
  /** The recommended player's id; null when nobody can be started. */
  start: string | null;
  close_call: boolean;
  why: string;
}

export interface BestLineup {
  league_id: string;
  roster_id: number;
  week: number | null;
  lineup: { slot: string; player: StartSitCandidate | null }[];
  projected: number;
  current_projected: number;
  changes: { start: StartSitCandidate; sit: StartSitCandidate; gain: number }[];
  why: string;
  /** Everyone on the roster who can be compared, with projection, matchup and game. */
  roster?: StartSitCandidate[];
}

/** A player in a game on the Games tab. */
export interface GamePlayer {
  player_id: string;
  name: string;
  position: string;
  /** The NFL team he plays for in this game. */
  team: string;
  injury?: InjuryInfo | null;
  /** The league roster that has him; null/absent means available. */
  owner_roster_id?: number | null;
  owner_team?: string | null;
  /** Fantasy points in this game under the league's scoring, once he has stats. */
  points?: number | null;
  stat_line?: string | null;
  /** His stat line by Sleeper's stat names (pass_yd, rush_att, rec, ...); projected before he plays. */
  stats?: Record<string, number>;
  /** True when `stats` and `points` are projections rather than what he did. */
  projected?: boolean;
}

export interface GameCard {
  game_id: string;
  week: number;
  home: string;
  away: string;
  /** From the home team's side: score, state, clock, line and conditions. */
  game: GameInfo;
  /** Wins, losses and ties; absent unless every finished game has a score. */
  home_record?: TeamRecord | null;
  away_record?: TeamRecord | null;
  players: GamePlayer[];
}

export interface BoxRow {
  name: string;
  position?: string | null;
  /** The Sleeper player, when the name and team match exactly one. */
  player_id?: string | null;
  stats: string[];
}

export interface BoxTable {
  key: string;
  title: string;
  columns: string[];
  rows: BoxRow[];
  totals?: string[] | null;
}

export interface BoxScoreData {
  home: string;
  away: string;
  final: boolean;
  /** Away first, then home. */
  teams: { team: string; tables: BoxTable[] }[];
}

export interface Games {
  league_id: string;
  week: number | null;
  current_week: number | null;
  weeks: number[];
  /** In kickoff order. */
  games: GameCard[];
}

export interface AlertItem {
  id: number;
  kind: string;
  title: string;
  /** One line with the numbers behind it. */
  why: string;
  player_id?: string | null;
  created_at: string;
  data?: Record<string, unknown>;
}

/** One reason for or against adding a player; "info" is a plain fact. */
interface WireReason {
  stance: "for" | "against" | "info";
  label: string;
  detail: string;
}

export interface WireEntry {
  player_id: string;
  name: string;
  position: string | null;
  team: string | null;
  projected: number;
  gain: number;
  slot: string;
  over: string;
  /** One line with the numbers behind it. */
  reason: string;
  /** ESPN-wide percent of leagues that roster them. */
  owned: number | null;
  for_count: number;
  against_count: number;
  reasons: WireReason[];
}

export interface WaiverWireData {
  league_id: string;
  roster_id: number;
  waiver_date: string;
  waiver_day: string;
  week: number | null;
  /** Best first; every position, capped per position. */
  entries: WireEntry[];
  /** Ids of the mixed best-of view. */
  top?: string[];
  /** Why the list is empty, when it is. */
  note: string | null;
}

export interface AlertsData {
  league_id: string;
  roster_id: number;
  /** Newest first, the last 14 days. */
  alerts: AlertItem[];
}

export interface MovedPlayer {
  player_id: string;
  name: string;
  position?: string | null;
  team?: string | null;
}

/** What one team did in a transaction: who came in and who went out. */
export interface TeamMove {
  roster_id: number;
  team: string;
  manager?: string | null;
  added: MovedPlayer[];
  dropped: MovedPlayer[];
}

export interface TransactionItem {
  transaction_id: string;
  kind: "waiver" | "free_agent" | "trade" | "commissioner";
  week: number;
  created_at?: string | null;
  moves: TeamMove[];
}

export interface NewsItem {
  id: string;
  source: string;
  title: string;
  link: string;
  published_at?: string | null;
  players: { player_id: string; name: string; position?: string | null; team?: string | null }[];
  teams: string[];
  topics: string[];
  roster_ids: number[];
}

export interface NewsData {
  league_id?: string | null;
  items: NewsItem[];
  sources: string[];
}

export interface TransactionsData {
  league_id: string;
  transactions: TransactionItem[];
}
