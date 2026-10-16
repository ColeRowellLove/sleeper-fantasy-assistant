import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AccuracyTable from "../components/AccuracyTable";
import type { LineupAccuracy } from "../lib/api";
import { parseTab } from "../lib/league";
import { expectNoA11yViolations } from "./a11y";

const data: LineupAccuracy = {
  league_id: "1",
  teams: [
    {
      roster_id: 2,
      team: "Dad Bods",
      points: 950.5,
      potential: 950.5,
      accuracy: 1,
      left_on_bench: 0,
    },
    { roster_id: 1, team: "Cole", points: 900, potential: 1000, accuracy: 0.9, left_on_bench: 100 },
    {
      roster_id: 3,
      team: "Sis",
      points: 800,
      potential: null,
      accuracy: null,
      left_on_bench: null,
    },
  ],
};

describe("lineup accuracy", () => {
  it("is a tab", () => {
    expect(parseTab("accuracy")).toBe("accuracy");
  });

  it("shows Sleeper's points and potential points with the accuracy between them", () => {
    render(<AccuracyTable data={data} leagueId="1" myRosterId={1} />);
    const table = screen.getByRole("table", { name: /Lineup accuracy by team/ });
    const cole = within(table).getByRole("row", { name: /^Cole/ });
    expect(within(cole).getByText("90.0%")).toBeInTheDocument();
    expect(within(cole).getByText("900.0")).toBeInTheDocument();
    expect(within(cole).getByText("1000.0")).toBeInTheDocument();
    expect(within(cole).getByText("100.0")).toBeInTheDocument();
    expect(within(cole).getByText("(you)")).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /^Dad Bods/ })).toHaveTextContent("100.0%");
  });

  it("shows a dash, never a guess, for a team Sleeper reports nothing for", () => {
    render(<AccuracyTable data={data} leagueId="1" myRosterId={null} />);
    const sis = within(screen.getByRole("table")).getByRole("row", { name: /^Sis/ });
    expect(within(sis).getAllByText("–")).toHaveLength(3);
    expect(screen.queryByText(/has not reported/)).not.toBeInTheDocument();
  });

  it("says so when Sleeper reports no potential points for anyone", () => {
    const none = { ...data, teams: [data.teams[2]] };
    render(<AccuracyTable data={none} leagueId="1" myRosterId={null} />);
    expect(screen.getByRole("status")).toHaveTextContent("has not reported potential points");
  });

  it("links each team to its roster", () => {
    render(<AccuracyTable data={data} leagueId="1" myRosterId={null} />);
    expect(screen.getByRole("link", { name: "Cole" })).toHaveAttribute(
      "href",
      "/league/1?tab=rosters&roster=1",
    );
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<AccuracyTable data={data} leagueId="1" myRosterId={1} />);
  });
});
