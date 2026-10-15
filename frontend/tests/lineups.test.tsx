import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import WeeklyLineups from "../components/WeeklyLineups";
import type { Lineups } from "../lib/api";
import { expectNoA11yViolations } from "./a11y";

const data: Lineups = {
  week: 5,
  weeks: [4, 5],
  matchups: [
    {
      matchup_id: 7,
      teams: [
        {
          roster_id: 1,
          team: "Cole",
          points: 20.5,
          starters: [
            { slot: "RB", player_id: "10", name: "Star RB", position: "RB", team: "SF", points: 20.5 },
            { slot: "WR", player_id: null, name: "Empty", position: null, team: null, points: null },
          ],
          bench: [
            { slot: "BN", player_id: "11", name: "Bench WR", position: "WR", team: "MIN", points: 3.25 },
          ],
        },
        { roster_id: 2, team: "Dad", points: 11, starters: [], bench: [] },
      ],
    },
  ],
};

describe("WeeklyLineups", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<WeeklyLineups data={data} />);
  });

  it("has a labelled week selector inside a GET form", () => {
    render(<WeeklyLineups data={data} />);
    const select = screen.getByLabelText("Week");
    expect(select).toHaveValue("5");
    expect(select.closest("form")).toHaveAttribute("method", "get");
    expect(screen.getByRole("button", { name: "Show week" })).toBeInTheDocument();
  });

  it("shows each matchup with starters by slot, then bench, with points", () => {
    render(<WeeklyLineups data={data} />);
    expect(screen.getByRole("heading", { level: 3, name: /Cole vs Dad/ })).toBeInTheDocument();

    const table = screen.getByRole("table", { name: /Cole: 20.50 points/ });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(4); // header + 2 starters + 1 bench
    expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent("RB"); // slot column
    expect(within(rows[1]).getByText("20.50")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Empty")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Bench")).toBeInTheDocument();
    expect(within(rows[3]).getByText("3.25")).toBeInTheDocument();
  });

  it("explains when nothing is synced and hides the selector", () => {
    render(<WeeklyLineups data={{ week: null, weeks: [], matchups: [] }} />);
    expect(screen.getByText("No matchups have been synced yet.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Week")).not.toBeInTheDocument();
  });
});
