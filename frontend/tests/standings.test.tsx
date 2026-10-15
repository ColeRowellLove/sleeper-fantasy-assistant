import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import StandingsTable from "../components/StandingsTable";
import type { StandingsRow } from "../lib/api";
import { expectNoA11yViolations } from "./a11y";

const row = (rank: number, id: number, team: string, w: number, l: number, t = 0): StandingsRow => ({
  rank,
  roster_id: id,
  team,
  owner_id: `u${id}`,
  wins: w,
  losses: l,
  ties: t,
  points_for: 700 + id,
  points_against: 650.5,
});

const standings = [row(1, 3, "Dad", 4, 1), row(2, 1, "Cole", 3, 1, 1), row(3, 2, "Sis", 2, 3)];

describe("StandingsTable", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <StandingsTable standings={standings} playoffTeams={2} myRosterId={1} />,
    );
  });

  it("is a table with column and row headers and formatted records", () => {
    render(<StandingsTable standings={standings} playoffTeams={2} myRosterId={null} />);
    const table = screen.getByRole("table", { name: /standings/i });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(4);
    expect(within(rows[1]).getByRole("rowheader", { name: "Dad" })).toBeInTheDocument();
    expect(within(rows[1]).getByText("4-1")).toBeInTheDocument();
    expect(within(rows[2]).getByText("3-1-1")).toBeInTheDocument(); // ties only shown when present
    expect(within(rows[3]).getByText("702.00")).toBeInTheDocument();
  });

  it("marks the user's team with text and aria-current, not color alone", () => {
    render(<StandingsTable standings={standings} playoffTeams={2} myRosterId={1} />);
    const mine = screen.getByRole("row", { name: /Cole/ });
    expect(mine).toHaveAttribute("aria-current", "true");
    expect(within(mine).getByText("You")).toBeInTheDocument();
    expect(screen.getAllByText("You")).toHaveLength(1);
  });

  it("marks the playoff line and explains it in text", () => {
    render(<StandingsTable standings={standings} playoffTeams={2} myRosterId={null} />);
    const rows = screen.getAllByRole("row");
    expect(rows[1].className).toContain("playoff");
    expect(rows[2].className).toContain("cutoff");
    expect(rows[3].className).not.toContain("playoff");
    expect(screen.getByText(/top 2 teams make the playoffs/i)).toBeInTheDocument();
    // not only visual: screen readers are told which rows are in playoff position
    expect(screen.getAllByText("(playoff position)")).toHaveLength(2);
  });

  it("omits the playoff note when the league has none set", () => {
    render(<StandingsTable standings={standings} playoffTeams={null} myRosterId={null} />);
    expect(screen.queryByText(/make the playoffs/i)).not.toBeInTheDocument();
  });
});
