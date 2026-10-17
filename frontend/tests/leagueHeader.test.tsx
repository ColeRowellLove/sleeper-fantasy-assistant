import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import LeagueHeader from "../components/LeagueHeader";
import LeagueTabs from "../components/LeagueTabs";
import type { Dashboard } from "../lib/api";
import { LIVE_TABS, TABS, formatRecord, parseTab, ruleChips, sectionOf } from "../lib/league";
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

  it("lists five sections, most important first, with the open one marked", () => {
    render(<LeagueTabs leagueId="9" active="rosters" />);
    const nav = screen.getByRole("navigation", { name: "League sections" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual([
      "My team",
      "Scores",
      "Players",
      "League",
      "Alerts",
    ]);
    expect(links[0]).toHaveAttribute("aria-current", "page");
    expect(links[1]).not.toHaveAttribute("aria-current");
    expect(links[1]).toHaveAttribute("href", "/league/9?tab=lineups"); // a section opens its first page
  });

  it("shows the pages of the open section as chips, the open page marked", () => {
    render(<LeagueTabs leagueId="9" active="waiver" />);
    expect(
      within(screen.getByRole("navigation", { name: "League sections" })).getByRole("link", {
        name: "Players",
      }),
    ).toHaveAttribute("aria-current", "page");
    const pages = screen.getByRole("navigation", { name: "Players pages" });
    expect(
      within(pages)
        .getAllByRole("link")
        .map((l) => l.textContent),
    ).toEqual(["Browse", "Trending", "Waiver wire", "Rankings", "NFL teams"]);
    expect(within(pages).getByRole("link", { name: "Waiver wire" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("a link to the open section stays on the open page", () => {
    render(<LeagueTabs leagueId="9" active="waiver" />);
    const nav = screen.getByRole("navigation", { name: "League sections" });
    expect(within(nav).getByRole("link", { name: "Players" })).toHaveAttribute(
      "href",
      "/league/9?tab=waiver",
    );
    expect(within(nav).getByRole("link", { name: "My team" })).toHaveAttribute(
      "href",
      "/league/9?tab=rosters",
    );
  });

  it("has no accessibility violations with the page chips showing", async () => {
    await expectNoA11yViolations(<LeagueTabs leagueId="9" active="waiver" />);
  });

  it("has no second row for a section with one page", () => {
    render(<LeagueTabs leagueId="9" active="alerts" />);
    expect(screen.queryByRole("navigation", { name: "Alerts pages" })).not.toBeInTheDocument();
  });

  it("only the pages that show live data refresh during a game", () => {
    expect([...LIVE_TABS]).toEqual(["rosters", "startsit", "lineups", "games", "teams"]);
    for (const tab of LIVE_TABS) expect(TABS.map((t) => t.key)).toContain(tab);
  });

  it("every page belongs to exactly one section and old links still resolve", () => {
    const keys = TABS.map((t) => t.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys).toHaveLength(12);
    expect(sectionOf("startsit").label).toBe("My team");
    expect(sectionOf("teams").label).toBe("Players");
  });

  it("is reachable by keyboard in order and shows unread alerts in words", async () => {
    const user = userEvent.setup();
    render(<LeagueTabs leagueId="9" active="rosters" unreadAlerts={2} />);
    expect(screen.getByRole("link", { name: "Alerts 2 new" })).toBeInTheDocument();
    await user.tab();
    expect(screen.getByRole("link", { name: "My team" })).toHaveFocus();
    for (let i = 0; i < 4; i += 1) await user.tab();
    expect(screen.getByRole("link", { name: "Alerts 2 new" })).toHaveFocus();
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
