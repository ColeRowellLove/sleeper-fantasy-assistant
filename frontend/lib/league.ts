import type { ConnectedLeague } from "./api";

export type Rules = ConnectedLeague["rules"];

export const TABS = [
  { key: "standings", label: "Standings" },
  { key: "rosters", label: "Rosters" },
  { key: "lineups", label: "Lineups" },
  { key: "rankings", label: "Rankings" },
  { key: "startsit", label: "Start/Sit" },
  { key: "accuracy", label: "Accuracy" },
  { key: "players", label: "Players" },
  { key: "teams", label: "Teams" },
  { key: "settings", label: "Settings" },
] as const;

export type TabKey = (typeof TABS)[number]["key"];

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
