/** Layout helpers for the team depth chart page. Pure, so they are easy to test. */

import type { DepthGroup, DepthPlayer, DepthSlot, TeamRecord } from "./api";

export const TEAM_NAMES: Record<string, string> = {
  ARI: "Arizona Cardinals",
  ATL: "Atlanta Falcons",
  BAL: "Baltimore Ravens",
  BUF: "Buffalo Bills",
  CAR: "Carolina Panthers",
  CHI: "Chicago Bears",
  CIN: "Cincinnati Bengals",
  CLE: "Cleveland Browns",
  DAL: "Dallas Cowboys",
  DEN: "Denver Broncos",
  DET: "Detroit Lions",
  GB: "Green Bay Packers",
  HOU: "Houston Texans",
  IND: "Indianapolis Colts",
  JAX: "Jacksonville Jaguars",
  KC: "Kansas City Chiefs",
  LAC: "Los Angeles Chargers",
  LAR: "Los Angeles Rams",
  LV: "Las Vegas Raiders",
  MIA: "Miami Dolphins",
  MIN: "Minnesota Vikings",
  NE: "New England Patriots",
  NO: "New Orleans Saints",
  NYG: "New York Giants",
  NYJ: "New York Jets",
  PHI: "Philadelphia Eagles",
  PIT: "Pittsburgh Steelers",
  SEA: "Seattle Seahawks",
  SF: "San Francisco 49ers",
  TB: "Tampa Bay Buccaneers",
  TEN: "Tennessee Titans",
  WAS: "Washington Commanders",
};

export const TEAM_CODES = Object.keys(TEAM_NAMES);

export function isTeamCode(value: string | undefined): value is string {
  return value !== undefined && value in TEAM_NAMES;
}

/** "Starter", "2nd string", "3rd string", ... however deep the chart goes. */
export function depthLabel(depth: number): string {
  if (depth <= 1) return "Starter";
  const lastTwo = depth % 100;
  const suffix =
    lastTwo >= 11 && lastTwo <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[depth % 10] ?? "th");
  return `${depth}${suffix} string`;
}

/** More columns than this are more than fit on a phone, so the chart says to slide sideways. */
export const SLIDE_FROM = 3;

export interface DepthRows {
  columns: { depth: number; label: string }[];
  rows: { slot: DepthSlot; cells: (DepthPlayer | null)[] }[];
}

/** A grid with one column per depth level the slots actually use, however deep it goes. */
export function depthRows(slots: DepthSlot[]): DepthRows {
  const levels = Math.max(1, ...slots.map((s) => s.players.length));
  return {
    columns: Array.from({ length: levels }, (_, i) => ({ depth: i + 1, label: depthLabel(i + 1) })),
    rows: slots.map((slot) => ({
      slot,
      cells: Array.from({ length: levels }, (_, i) => slot.players[i] ?? null),
    })),
  };
}

export interface DepthSections {
  /** The fantasy-relevant slots (QB, RB, WR, TE), always open. */
  skill: DepthSlot[];
  /** The rest of the chart: offensive line, defense, special teams, each a section that opens. */
  more: { key: string; title: string; slots: DepthSlot[] }[];
}

export type DepthUnit = "offense" | "defense" | "special";

export const DEPTH_UNITS: readonly { value: DepthUnit; label: string }[] = [
  { value: "offense", label: "Offense" },
  { value: "defense", label: "Defense" },
  { value: "special", label: "Special teams" },
];

export interface UnitView {
  /** The title of the main card ("Fantasy positions", "Defense", "Special teams"). */
  mainTitle: string;
  main: DepthSlot[];
  more: DepthSections["more"];
}

/** One unit's lineup: the offense keeps its fantasy positions up front and the line folded away. */
export function unitView(groups: DepthGroup[], unit: DepthUnit): UnitView {
  const own = groups.filter((g) => g.group === unit);
  if (unit === "offense") {
    const { skill, more } = groupSlots(own);
    return { mainTitle: "Fantasy positions", main: skill, more };
  }
  return {
    mainTitle: unit === "defense" ? "Defense" : "Special teams",
    main: own.flatMap((g) => g.slots),
    more: [],
  };
}

export function groupSlots(groups: DepthGroup[]): DepthSections {
  const skill: DepthSlot[] = [];
  const more: DepthSections["more"] = [];
  for (const group of groups) {
    if (group.group === "offense") {
      skill.push(...group.slots.filter((s) => s.skill));
      const line = group.slots.filter((s) => !s.skill);
      if (line.length) more.push({ key: "offense-line", title: "Offensive line", slots: line });
    } else if (group.slots.length) {
      more.push({ key: group.group, title: group.title, slots: group.slots });
    }
  }
  return { skill, more };
}

/** "3-2" or "3-2-1" (ties shown only when there are some), plus the sentence for screen readers. */
export function recordText(record: TeamRecord): { short: string; spoken: string } {
  const { wins, losses, ties } = record;
  const short = ties > 0 ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
  const parts = [
    `${wins} ${wins === 1 ? "win" : "wins"}`,
    `${losses} ${losses === 1 ? "loss" : "losses"}`,
  ];
  if (ties > 0) parts.push(`${ties} ${ties === 1 ? "tie" : "ties"}`);
  const last = parts.pop();
  return { short, spoken: `Record: ${parts.join(", ")} and ${last}` };
}
