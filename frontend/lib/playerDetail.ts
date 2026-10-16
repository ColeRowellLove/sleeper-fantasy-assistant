/** Small formatting helpers for the player pop-up. Pure, so they are easy to test. */

import { scoringLabel } from "./leagueSettings";

type Bio = Record<string, unknown> | null | undefined;

export interface BioRow {
  label: string;
  value: string;
}

function text(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

/** 74 inches becomes 6'2". Anything that is not a plausible number is shown as written. */
export function formatHeight(value: unknown): string | null {
  const raw = text(value);
  if (raw === null) return null;
  const inches = Number(raw);
  if (!Number.isFinite(inches) || inches < 48 || inches > 96) return raw;
  return `${Math.floor(inches / 12)}'${Math.round(inches % 12)}"`;
}

function formatExperience(value: unknown): string | null {
  const raw = text(value);
  if (raw === null) return null;
  const years = Number(raw);
  if (!Number.isFinite(years)) return raw;
  if (years === 0) return "Rookie";
  return `${years} ${years === 1 ? "season" : "seasons"}`;
}

/** The bio facts Sleeper has for the player, in reading order. Missing facts are left out. */
export function bioRows(bio: Bio): BioRow[] {
  if (!bio) return [];
  const rows: [string, string | null][] = [
    ["Age", text(bio.age)],
    ["Height", formatHeight(bio.height)],
    ["Weight", text(bio.weight) ? `${text(bio.weight)} lb` : null],
    ["College", text(bio.college)],
    ["Experience", formatExperience(bio.years_exp)],
    ["Jersey", text(bio.number) ? `#${text(bio.number)}` : null],
    [
      "Depth chart",
      text(bio.depth_chart_position)
        ? `${text(bio.depth_chart_position)}${text(bio.depth_chart_order) ? ` ${text(bio.depth_chart_order)}` : ""}`
        : null,
    ],
  ];
  return rows.filter((r): r is [string, string] => r[1] !== null).map(([label, value]) => ({ label, value }));
}

const SHORT: Record<string, string> = {
  rec: "Catches",
  rec_yd: "Rec yds",
  rec_td: "Rec TD",
  rec_tgt: "Targets",
  rush_att: "Carries",
  rush_yd: "Rush yds",
  rush_td: "Rush TD",
  pass_att: "Pass att",
  pass_cmp: "Pass cmp",
  pass_yd: "Pass yds",
  pass_td: "Pass TD",
  pass_int: "INT thrown",
  fum_lost: "Fumbles lost",
  fga: "FG att",
  fgm: "FG made",
  xpm: "XP made",
  sack: "Sacks",
  int: "INT",
};

const PASS = ["pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int"];
const RUSH = ["rush_att", "rush_yd", "rush_td"];
const REC = ["rec_tgt", "rec", "rec_yd", "rec_td"];
const KICK = ["fga", "fgm", "xpm"];
const DEFENSE = ["sack", "int", "ff", "fum_rec", "def_td", "safe", "blk_kick"];

/** Stats come in reading order for the position: a quarterback's passing first, a receiver's catches first. */
const ORDER: Record<string, string[]> = {
  QB: [...PASS, ...RUSH, ...REC],
  RB: [...RUSH, ...REC, ...PASS],
  WR: [...REC, ...RUSH, ...PASS],
  TE: [...REC, ...RUSH, ...PASS],
  K: KICK,
  DEF: DEFENSE,
};

/** Smaller than this would print as 0.0, which says nothing (a 0.03 projected fumble). */
const TINY = 0.05;

/**
 * "Catches 7, Rec yds 90, Rush yds 25": every stat that counted, in plain words and reading order.
 * The position puts its main stats first; anything else follows alphabetically.
 */
export function describeStats(stats: Record<string, number>, position?: string | null): string {
  const order = ORDER[position ?? ""] ?? [...REC, ...RUSH, ...PASS];
  const rank = (key: string) => {
    const at = order.indexOf(key);
    return at === -1 ? order.length : at;
  };
  const parts = Object.entries(stats)
    .filter(([, value]) => Math.abs(value) >= TINY)
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .map(([key, value]) => {
      const label = SHORT[key] ?? scoringLabel(key);
      return `${label} ${Number.isInteger(value) ? value : value.toFixed(1)}`;
    });
  return parts.length ? parts.join(", ") : "No scoring stats";
}

/** "WR1" style rank text, or a dash when the player has no rank yet. */
export function rankText(position: string | null, rank: number | null | undefined): string {
  return rank === null || rank === undefined || !position ? "–" : `${position}${rank}`;
}
