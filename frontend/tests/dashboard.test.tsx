import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LeagueDashboard from "../components/LeagueDashboard";
import type { Dashboard } from "../lib/api";
import { expectNoA11yViolations } from "./a11y";

const data: Dashboard = {
  league_id: "1",
  name: "Family League",
  season: "2026",
  rules: { reception_scoring: "full", uses_faab: true, trade_deadline_week: 11, playoff_teams: 6 },
  standings: [
    { rank: 1, roster_id: 2, team: "Dad", owner_id: null, wins: 2, losses: 0, ties: 0, points_for: 250.5, points_against: 200 },
    { rank: 2, roster_id: 1, team: "Cole", owner_id: null, wins: 1, losses: 1, ties: 0, points_for: 220, points_against: 230.25 },
  ],
  rosters: [
    {
      roster_id: 1,
      team: "Cole",
      owner_id: null,
      players: [
        { player_id: "10", name: "Star RB", position: "RB", team: "SF", status: "starter", slot: "RB" },
        { player_id: "999", name: "999", position: null, team: null, status: "bench", slot: null },
        { player_id: "12", name: "Hurt TE", position: "TE", team: "KC", status: "ir", slot: null },
        { player_id: "13", name: "Rookie QB", position: "QB", team: "NYJ", status: "taxi", slot: null },
      ],
    },
  ],
};

describe("LeagueDashboard", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<LeagueDashboard data={data} />);
  });

  it("renders standings as a table with row and column headers", () => {
    render(<LeagueDashboard data={data} />);
    const table = screen.getByRole("table", { name: /standings/i });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3); // header + 2 teams
    expect(within(rows[1]).getByRole("rowheader", { name: "Dad" })).toBeInTheDocument();
    expect(within(rows[1]).getByText("2-0-0")).toBeInTheDocument();
    expect(within(rows[2]).getByText("230.25")).toBeInTheDocument();
  });

  it("shows the league rules card", () => {
    render(<LeagueDashboard data={data} />);
    expect(screen.getByText("Waivers").tagName).toBe("DT");
    expect(screen.getByText("Week 11")).toBeInTheDocument();
    expect(screen.getByText("FAAB")).toBeInTheDocument();
  });

  it("lists roster players with a text role (not color alone) and placeholders for unknowns", () => {
    render(<LeagueDashboard data={data} />);
    const roster = screen.getByRole("table", { name: /Cole roster/ });
    expect(within(roster).getByText("Starter (RB)")).toBeInTheDocument();
    expect(within(roster).getByText("Bench")).toBeInTheDocument();
    expect(within(roster).getByText("IR")).toBeInTheDocument();
    expect(within(roster).getByText("Taxi")).toBeInTheDocument();
    expect(within(roster).getAllByText("–")).toHaveLength(2);
  });

  it("has one h1 and ordered headings", () => {
    render(<LeagueDashboard data={data} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "League rules",
      "Standings",
      "Rosters",
    ]);
  });
});
