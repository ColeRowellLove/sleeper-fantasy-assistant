import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TrendingPanel from "../components/TrendingPanel";
import type { PlayerListing, PlayersData } from "../lib/api";
import { parseTab } from "../lib/league";
import { fixed, percentWhole } from "../lib/format";
import { formatTrendCount, trendRows } from "../lib/trending";
import { expectNoA11yViolations } from "./a11y";

const p = (id: string, name: string, position: string, extra: Partial<PlayerListing> = {}) =>
  ({
    player_id: id,
    name,
    position,
    team: "ARI",
    owner_roster_id: null,
    owner_team: null,
    adds: null,
    drops: null,
    total_points: 0,
    rank: null,
    projected: null,
    ...extra,
  }) as PlayerListing;

const players = [
  p("1", "Tyler Allgeier", "RB", {
    adds: 525400,
    owned_pct: 64.1,
    last_points: 3.6,
    projected: 13.5,
  }),
  p("2", "Dameon Pierce", "RB", { adds: 449900, drops: 10, owner_team: "Dad Bods" }),
  p("3", "Tanner McKee", "QB", { adds: 309800 }),
  p("4", "Josh Jacobs", "RB", { drops: 396600 }),
  p("5", "Nobody", "WR"),
];
const data: PlayersData = { league_id: "L", week: 6, players };

describe("trending helpers", () => {
  it("writes counts the way Sleeper does", () => {
    expect(formatTrendCount(525400, "adds")).toBe("+525.4K");
    expect(formatTrendCount(1200000, "adds")).toBe("+1.2M");
    expect(formatTrendCount(80, "adds")).toBe("+80");
    expect(formatTrendCount(396600, "drops")).toBe("−396.6K");
    expect(formatTrendCount(999960, "adds")).toBe("+1.0M"); // never "+1000.0K"
  });

  it("ranks the most added first, leaves out unlisted players and filters by position", () => {
    expect(trendRows(players, "adds", "ALL").map((r) => [r.rank, r.player.name])).toEqual([
      [1, "Tyler Allgeier"],
      [2, "Dameon Pierce"],
      [3, "Tanner McKee"],
    ]);
    expect(trendRows(players, "adds", "QB").map((r) => r.player.name)).toEqual(["Tanner McKee"]);
    expect(trendRows(players, "drops", "ALL").map((r) => r.player.name)).toEqual([
      "Josh Jacobs",
      "Dameon Pierce",
    ]);
  });

  it("sizes each bar against the top of the list, with a visible minimum", () => {
    const rows = trendRows(players, "adds", "ALL");
    expect(rows[0].share).toBe(100);
    expect(rows[1].share).toBe(86);
    expect(trendRows([p("9", "Tiny", "RB", { adds: 1 }), players[0]], "adds", "ALL")[1].share).toBe(
      4,
    );
    expect(trendRows(players, "adds", "ALL", 2)).toHaveLength(2);
  });

  it("shows a dash, never zero, for a missing number", () => {
    expect(percentWhole(null)).toBe("–");
    expect(percentWhole(64.1)).toBe("64%");
    expect(fixed(undefined)).toBe("–");
    expect(fixed(13.54)).toBe("13.5");
  });

  it("is a page of the league", () => {
    expect(parseTab("trending")).toBe("trending");
  });
});

describe("TrendingPanel", () => {
  it("lists the top adds with rostered share, last week's points and the projection", () => {
    render(<TrendingPanel data={data} />);
    const rows = screen.getAllByRole("listitem").filter((li) => li.classList.contains("trend-row"));
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("Tyler Allgeier")).toBeInTheDocument();
    expect(within(rows[0]).getByText(/525,400 adds/)).toBeInTheDocument();
    expect(within(rows[0]).getByText("64%")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Wk 5 pts").nextSibling).toHaveTextContent("3.6");
    expect(within(rows[0]).getByText("Wk 6 proj").nextSibling).toHaveTextContent("13.5");
    expect(within(rows[1]).getByText("On Dad Bods")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Available")).toBeInTheDocument();
  });

  it("switches to drops and filters by position", () => {
    render(<TrendingPanel data={data} />);
    fireEvent.click(screen.getByRole("button", { name: "Drops" }));
    expect(screen.getByText(/396,600 drops/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "QB" }));
    expect(screen.getByText(/nobody is trending at that position/i)).toBeInTheDocument();
  });

  it("says the numbers are not loaded when Sleeper's trends are missing", () => {
    render(<TrendingPanel data={{ ...data, players: [p("5", "Nobody", "WR")] }} />);
    expect(screen.getByText(/trending numbers have not loaded/i)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<TrendingPanel data={data} />);
  });
});
