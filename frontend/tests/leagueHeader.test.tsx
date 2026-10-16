import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LeagueHeader from "../components/LeagueHeader";
import LeagueTabs from "../components/LeagueTabs";
import type { Dashboard } from "../lib/api";
import { formatRecord, parseTab, ruleChips } from "../lib/league";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const rules = {
  reception_scoring: "full",
  uses_faab: false,
  trade_deadline_week: 11,
  playoff_teams: 6,
};

const data: Dashboard = {
  league_id: "9",
  name: "Love League ",
  season: "2026",
  rules,
  standings: [
    {
      rank: 1,
      roster_id: 1,
      team: "Cole",
      owner_id: "u1",
      wins: 1,
      losses: 0,
      ties: 0,
      points_for: 1,
      points_against: 1,
    },
  ],
  rosters: [],
};

describe("LeagueHeader", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<LeagueHeader data={data} myRosterId={1} />);
  });

  it("shows the trimmed league name as the single h1, the season and rule chips", () => {
    render(<LeagueHeader data={data} myRosterId={1} />);
    expect(screen.getByRole("heading", { level: 1, name: "Love League" })).toBeInTheDocument();
    expect(screen.getByText("2026 season")).toBeInTheDocument();
    const chips = within(screen.getByRole("list", { name: "League rules" })).getAllByRole(
      "listitem",
    );
    expect(chips.map((c) => c.textContent)).toEqual([
      "Full PPR",
      "Priority waivers",
      "Trade deadline: week 11",
      "6 playoff teams",
    ]);
  });
});

describe("LeagueTabs", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<LeagueTabs leagueId="9" active="rosters" />);
  });

  it("is a labelled nav of links with the current section marked", () => {
    render(<LeagueTabs leagueId="9" active="rosters" />);
    const nav = screen.getByRole("navigation", { name: "League sections" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual([
      "Standings",
      "Rosters",
      "Lineups",
      "Rankings",
      "Start/Sit",
      "Players",
      "Teams",
      "Settings",
    ]);
    expect(links[1]).toHaveAttribute("aria-current", "page");
    expect(links[0]).not.toHaveAttribute("aria-current");
    expect(links[2]).toHaveAttribute("href", "/league/9?tab=lineups");
  });
});

describe("league helpers", () => {
  it("parses tabs defensively", () => {
    expect(parseTab("lineups")).toBe("lineups");
    expect(parseTab("nope")).toBe("standings");
    expect(parseTab(undefined)).toBe("standings");
  });

  it("words the rules in plain language for every scoring and waiver type", () => {
    expect(ruleChips({ ...rules, reception_scoring: "half", uses_faab: true })).toContain(
      "Half PPR",
    );
    expect(ruleChips({ ...rules, reception_scoring: "none" })[0]).toBe("Standard scoring");
    expect(ruleChips({ ...rules, uses_faab: true })[1]).toBe("FAAB waivers");
    const bare = ruleChips({ ...rules, trade_deadline_week: null, playoff_teams: null });
    expect(bare.slice(2)).toEqual(["No trade deadline", "Playoffs not set"]);
  });

  it("formats records, showing ties only when there are any", () => {
    expect(formatRecord(4, 1, 0)).toBe("4-1");
    expect(formatRecord(3, 1, 1)).toBe("3-1-1");
  });
});
