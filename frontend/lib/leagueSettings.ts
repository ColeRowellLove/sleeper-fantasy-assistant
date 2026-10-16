/** Turns Sleeper's raw league settings into labelled, grouped rows. Pure so it is easy to test. */

import type { LeagueSettings } from "./api";

export interface SettingRow {
  label: string;
  value: string;
}

export interface SettingGroup {
  title: string;
  rows: SettingRow[];
}

type Raw = LeagueSettings["settings"];

type Format = "flag" | "week" | "weekday" | { [value: number]: string };

interface Spec {
  key: string;
  label: string;
  format?: Format;
}

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** Settings that only mean something under a certain waiver system (Sleeper keeps them regardless). */
const FAAB_ONLY = new Set(["waiver_budget", "waiver_bid_min", "faab_suggestions"]);

const GROUPS: { title: string; specs: Spec[] }[] = [
  {
    title: "League",
    specs: [
      { key: "num_teams", label: "Teams" },
      { key: "type", label: "League type", format: { 0: "Redraft", 1: "Keeper", 2: "Dynasty" } },
      { key: "best_ball", label: "Best ball", format: "flag" },
      { key: "start_week", label: "First week of the season", format: "week" },
      { key: "leg", label: "Current week", format: "week" },
      { key: "last_scored_leg", label: "Last scored week", format: "week" },
      {
        key: "league_average_match",
        label: "Also play the league average each week",
        format: "flag",
      },
    ],
  },
  {
    title: "Rosters",
    specs: [
      { key: "reserve_slots", label: "Injured reserve spots" },
      { key: "reserve_allow_out", label: "IR: Out players allowed", format: "flag" },
      { key: "reserve_allow_doubtful", label: "IR: Doubtful players allowed", format: "flag" },
      { key: "reserve_allow_sus", label: "IR: Suspended players allowed", format: "flag" },
      { key: "reserve_allow_dnr", label: "IR: Did-not-report players allowed", format: "flag" },
      { key: "reserve_allow_cov", label: "IR: COVID-list players allowed", format: "flag" },
      { key: "reserve_allow_na", label: "IR: Inactive (NA) players allowed", format: "flag" },
      { key: "taxi_slots", label: "Taxi squad spots" },
      { key: "taxi_years", label: "Taxi eligibility (years in the league)" },
      { key: "taxi_allow_vets", label: "Veterans allowed on taxi", format: "flag" },
      { key: "taxi_deadline", label: "Taxi deadline", format: "week" },
      { key: "max_keepers", label: "Keepers" },
      { key: "bench_lock", label: "Bench locked after kickoff", format: "flag" },
      { key: "capacity_override", label: "Roster size override", format: "flag" },
      { key: "max_subs", label: "Substitutions per week" },
      { key: "sub_start_time_eligibility", label: "Substitution start-time eligibility" },
      {
        key: "sub_lock_if_starter_active",
        label: "Lock substitutions once the starter plays",
        format: "flag",
      },
    ],
  },
  {
    title: "Waivers and free agents",
    specs: [
      {
        key: "waiver_type",
        label: "Waiver system",
        format: { 0: "Rolling priority", 1: "Reverse standings priority", 2: "FAAB budget" },
      },
      { key: "waiver_budget", label: "FAAB budget" },
      { key: "waiver_bid_min", label: "Minimum FAAB bid" },
      { key: "faab_suggestions", label: "FAAB bid suggestions", format: "flag" },
      { key: "waiver_day_of_week", label: "Waivers first run on", format: "weekday" },
      { key: "waiver_clear_days", label: "Days a dropped player stays on waivers" },
      { key: "daily_waivers", label: "Daily waivers", format: "flag" },
      { key: "daily_waivers_hour", label: "Daily waivers run at (hour of day)" },
      { key: "daily_waivers_days", label: "Daily waiver days (Sleeper's bitmask)" },
      { key: "daily_waivers_last_ran", label: "Daily waivers last ran", format: "week" },
      { key: "disable_adds", label: "Adds disabled", format: "flag" },
      { key: "offseason_adds", label: "Adds allowed in the offseason", format: "flag" },
    ],
  },
  {
    title: "Trades",
    specs: [
      { key: "trade_deadline", label: "Trade deadline", format: "week" },
      { key: "disable_trades", label: "Trades disabled", format: "flag" },
      { key: "pick_trading", label: "Draft pick trading", format: "flag" },
      { key: "trade_review_days", label: "Days a trade is under review" },
      { key: "veto_votes_needed", label: "Votes needed to veto" },
      { key: "veto_auto_poll", label: "Automatic veto poll", format: "flag" },
      { key: "veto_show_votes", label: "Veto votes are public", format: "flag" },
    ],
  },
  {
    title: "Playoffs",
    specs: [
      { key: "playoff_teams", label: "Playoff teams" },
      { key: "playoff_week_start", label: "Playoffs start", format: "week" },
      {
        key: "playoff_type",
        label: "Bracket",
        format: { 0: "Single elimination", 1: "Two-week rounds" },
      },
      {
        key: "playoff_round_type",
        label: "Round length",
        format: {
          0: "One week per round",
          1: "Two weeks per round",
          2: "Two-week championship only",
        },
      },
      { key: "playoff_seed_type", label: "Seeding", format: { 0: "By record", 1: "By points" } },
    ],
  },
  {
    title: "Draft",
    specs: [{ key: "draft_rounds", label: "Draft rounds" }],
  },
];

/** A value for a key we have no special format for: shown as written, never hidden. */
function plain(value: unknown): string {
  if (value === null || value === undefined) return "Not set";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function format(value: unknown, how: Format | undefined): string {
  if (value === null || value === undefined) return "Not set";
  const n = typeof value === "number" ? value : Number(value);
  if (how === "flag") return n ? "On" : "Off";
  if (how === "week") return n ? `Week ${n}` : "Not set";
  if (how === "weekday") return WEEKDAYS[n] ?? plain(value);
  if (how && typeof how === "object") return how[n] ?? plain(value);
  return plain(value);
}

function titleCase(key: string): string {
  const words = key.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Rule groups with a plain-language label for every setting Sleeper sent; unlabelled ones go last. */
export function settingGroups(settings: Raw): SettingGroup[] {
  const known = new Set<string>();
  const groups: SettingGroup[] = [];
  const usesFaab = Number(settings.waiver_type) === 2;
  for (const { title, specs } of GROUPS) {
    const rows: SettingRow[] = [];
    for (const spec of specs) {
      if (!(spec.key in settings)) continue;
      known.add(spec.key);
      if (FAAB_ONLY.has(spec.key) && !usesFaab) continue;
      rows.push({ label: spec.label, value: format(settings[spec.key], spec.format) });
    }
    if (rows.length) groups.push({ title, rows });
  }
  const other = Object.keys(settings)
    .filter((key) => !known.has(key))
    .sort()
    .map((key) => ({ label: titleCase(key), value: plain(settings[key]) }));
  if (other.length) groups.push({ title: "Other settings", rows: other });
  return groups;
}

/** One row per lineup slot with how many there are, in lineup order. */
export function rosterSummary(positions: string[]): SettingRow[] {
  const counts = new Map<string, number>();
  for (const slot of positions) counts.set(slot, (counts.get(slot) ?? 0) + 1);
  return [...counts].map(([slot, count]) => ({
    label: slot === "BN" ? "Bench" : slot === "IR" ? "Injured reserve" : slot,
    value: String(count),
  }));
}

const TOKENS: Record<string, string> = {
  pass: "passing",
  rush: "rushing",
  rec: "receiving",
  td: "touchdown",
  yd: "yards",
  yds: "yards",
  int: "interception",
  att: "attempt",
  cmp: "completion",
  inc: "incompletion",
  fd: "first down",
  fgm: "field goal made",
  fgmiss: "field goal missed",
  xpm: "extra point made",
  xpmiss: "extra point missed",
  fum: "fumble",
  ff: "forced fumble",
  tkl: "tackle",
  ast: "assist",
  def: "defense",
  st: "special teams",
  idp: "IDP",
  pts: "points",
  allow: "allowed",
  ret: "return",
  kr: "kick return",
  pr: "punt return",
  blk: "blocked",
  safe: "safety",
  "2pt": "2-point conversion",
  qb: "QB",
  te: "TE",
  wr: "WR",
  rb: "RB",
};

const SCORING_OVERRIDES: Record<string, string> = {
  rec: "Reception",
  pass_yd: "Passing yard",
  rush_yd: "Rushing yard",
  rec_yd: "Receiving yard",
  pass_td: "Passing touchdown",
  rush_td: "Rushing touchdown",
  rec_td: "Receiving touchdown",
  pass_int: "Interception thrown",
  fum_lost: "Fumble lost",
  fum_rec: "Fumble recovery",
  fum_rec_td: "Fumble recovery touchdown",
  int: "Interception (defense)",
  sack: "Sack",
  safe: "Safety",
  ff: "Forced fumble",
  blk_kick: "Blocked kick",
  def_td: "Defensive touchdown",
  st_td: "Special teams touchdown",
  def_st_td: "Special teams (defense) touchdown",
  xpm: "Extra point made",
  fgm: "Field goal made",
  pass_int_td: "Interception returned for a touchdown (thrown)",
  def_st_ff: "Special teams forced fumble (defense)",
  def_st_fum_rec: "Special teams fumble recovery (defense)",
  st_ff: "Special teams forced fumble",
  st_fum_rec: "Special teams fumble recovery",
  pts_allow: "Points allowed",
  yds_allow: "Yards allowed",
};

/** "fgm_40_49" becomes "Field goal made 40-49"; "pass_td_50p" becomes "Passing touchdown 50+". */
export function scoringLabel(key: string): string {
  if (SCORING_OVERRIDES[key]) return SCORING_OVERRIDES[key];
  const words: string[] = [];
  const range: string[] = [];
  for (const part of key.split("_")) {
    if (/^\d+p?$/.test(part)) range.push(part);
    else words.push(TOKENS[part] ?? part);
  }
  let label = words.join(" ");
  if (range.length === 2) label += ` ${range[0]}-${range[1]}`;
  else if (range.length === 1) {
    label += range[0].endsWith("p") ? ` ${range[0].slice(0, -1)}+` : ` ${range[0]}`;
  }
  return label.charAt(0).toUpperCase() + label.slice(1);
}

const TEAM_DEFENSE_KEYS = new Set([
  "sack",
  "int",
  "ff",
  "safe",
  "blk_kick",
  "fum_rec",
  "int_ret_yd",
  "sack_yd",
  "fum_ret_yd",
  "fum_rec_td",
]);
const IDP_KEYS = new Set(["tkl", "tkl_solo", "tkl_ast", "tkl_loss", "qb_hit"]);
const SPECIAL_TEAMS_KEYS = new Set(["kr_yd", "pr_yd", "fg_ret_yd", "blk_kick_ret_yd"]);

// First match wins, so more specific groups come first.
const CATEGORIES: { title: string; test: (key: string) => boolean }[] = [
  { title: "Bonuses", test: (k) => k.startsWith("bonus_") },
  { title: "Individual defensive players", test: (k) => k.startsWith("idp_") || IDP_KEYS.has(k) },
  {
    title: "Team defense",
    test: (k) =>
      k.startsWith("def_") ||
      k.startsWith("pts_allow") ||
      k.startsWith("yds_allow") ||
      TEAM_DEFENSE_KEYS.has(k),
  },
  { title: "Kicking", test: (k) => k.startsWith("fg") || k.startsWith("xp") },
  { title: "Special teams", test: (k) => k.startsWith("st_") || SPECIAL_TEAMS_KEYS.has(k) },
  { title: "Passing", test: (k) => k.startsWith("pass_") },
  { title: "Rushing", test: (k) => k.startsWith("rush_") },
  { title: "Receiving", test: (k) => k === "rec" || k.startsWith("rec_") },
  { title: "Fumbles and other", test: () => true },
];

export interface ScoringSummary {
  /** Rules worth points, by category. */
  active: SettingGroup[];
  /** Rules Sleeper lists that this league scores at zero. */
  unused: SettingRow[];
}

function points(value: number): string {
  const text = String(Number(value.toFixed(4)));
  return `${value > 0 ? "+" : ""}${text}`;
}

export function scoringSummary(scoring: Record<string, number>): ScoringSummary {
  const byCategory = new Map<string, SettingRow[]>(CATEGORIES.map((c) => [c.title, []]));
  const unused: SettingRow[] = [];
  for (const key of Object.keys(scoring).sort()) {
    const value = scoring[key];
    if (value === 0) {
      unused.push({ label: scoringLabel(key), value: "0" });
      continue;
    }
    const category = CATEGORIES.find((c) => c.test(key))!;
    byCategory.get(category.title)!.push({ label: scoringLabel(key), value: points(value) });
  }
  return {
    active: [...byCategory]
      .filter(([, rows]) => rows.length > 0)
      .map(([title, rows]) => ({ title, rows })),
    unused,
  };
}
