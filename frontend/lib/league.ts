import type { ConnectedLeague } from "./api";

export type Rules = ConnectedLeague["rules"];

/**
 * The sections of a league page, most important first, each with its pages. The nav shows the
 * sections; a section with more than one page shows them as a second row. `?tab=` keeps naming a
 * page, so every older link still works.
 */
export const SECTIONS = [
  {
    key: "team",
    label: "My team",
    pages: [
      { key: "rosters", label: "Roster" },
      { key: "startsit", label: "Start/Sit" },
    ],
  },
  {
    key: "scores",
    label: "Scores",
    pages: [
      { key: "lineups", label: "Matchups" },
      { key: "games", label: "NFL games" },
    ],
  },
  {
    key: "players",
    label: "Players",
    pages: [
      { key: "players", label: "Browse" },
      { key: "trending", label: "Trending" },
      { key: "waiver", label: "Waiver wire" },
      { key: "rankings", label: "Rankings" },
      { key: "teams", label: "NFL teams" },
    ],
  },
  {
    key: "league",
    label: "League",
    pages: [
      { key: "standings", label: "Standings" },
      { key: "settings", label: "Rules" },
    ],
  },
  { key: "alerts", label: "Alerts", pages: [{ key: "alerts", label: "Alerts" }] },
] as const;

export type TabKey = (typeof SECTIONS)[number]["pages"][number]["key"];
export type Section = (typeof SECTIONS)[number];

export const TABS: readonly { key: TabKey; label: string }[] = SECTIONS.flatMap(
  (s): readonly { key: TabKey; label: string }[] => s.pages,
);

/** The pages that show live scores or game states; only they refresh while a game is on. */
export const LIVE_TABS: readonly TabKey[] = ["rosters", "startsit", "lineups", "games", "teams"];

/** The section a page belongs to. */
export function sectionOf(tab: TabKey): Section {
  return SECTIONS.find((s) => s.pages.some((p) => p.key === tab)) ?? SECTIONS[0];
}

export function parseTab(value: string | undefined): TabKey {
  return TABS.find((t) => t.key === value)?.key ?? "standings";
}

const SCORING: Record<string, string> = {
  none: "Standard scoring",
  half: "Half PPR",
  full: "Full PPR",
  custom: "Custom reception scoring",
};

/** Short, plain-language rule chips shown under the league name. */
export function ruleChips(rules: Rules): string[] {
  return [
    SCORING[rules.reception_scoring] ?? rules.reception_scoring,
    rules.uses_faab ? "FAAB waivers" : "Priority waivers",
    rules.trade_deadline_week
      ? `Trade deadline: week ${rules.trade_deadline_week}`
      : "No trade deadline",
    rules.playoff_teams ? `${rules.playoff_teams} playoff teams` : "Playoffs not set",
  ];
}

/** Link to a league page; the id is encoded because it comes from outside. */
export function leaguePath(leagueId: string, query = ""): string {
  return `/league/${encodeURIComponent(leagueId)}${query}`;
}

/** Link to one team's roster in a league (the Rosters tab, starting on that team). */
export function rosterPath(leagueId: string, rosterId: number): string {
  return leaguePath(leagueId, `?tab=rosters&roster=${rosterId}`);
}

export function formatRecord(wins: number, losses: number, ties: number): string {
  return ties > 0 ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
}
