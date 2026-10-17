import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import BoxScorePanel from "../components/BoxScorePanel";
import type { BoxScoreData } from "../lib/api";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=games&week=7&box=WAS-KC"),
}));

const data: BoxScoreData = {
  home: "KC",
  away: "WAS",
  final: true,
  teams: [
    {
      team: "WAS",
      tables: [
        {
          key: "passing",
          title: "Passing",
          columns: ["C/ATT", "YDS"],
          rows: [
            { name: "Jayden Daniels", position: "QB", player_id: "p1", stats: ["20/30", "250"] },
          ],
          totals: ["20/30", "250"],
        },
        {
          key: "defensive",
          title: "Defensive",
          columns: ["TOT", "SACKS"],
          rows: [{ name: "Bobby Wagner", position: "LB", stats: ["9", "1.0"] }],
        },
      ],
    },
    {
      team: "KC",
      tables: [
        {
          key: "rushing",
          title: "Rushing",
          columns: ["CAR", "YDS"],
          rows: [{ name: "Isiah Pacheco", position: "RB", stats: ["15", "70"] }],
        },
      ],
    },
  ],
};

const panel = (mine: string[] = []) => (
  <BoxScorePanel data={data} leagueId="1" week={7} mine={mine} />
);

describe("BoxScorePanel", () => {
  it("shows every category as a table with the stat columns and a team total", () => {
    render(panel());
    const passing = screen.getByRole("table", { name: "WAS passing" });
    expect(within(passing).getByRole("columnheader", { name: "C/ATT" })).toBeInTheDocument();
    expect(within(passing).getByRole("rowheader", { name: /Jayden Daniels/ })).toBeInTheDocument();
    expect(within(passing).getByRole("rowheader", { name: "Team" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "WAS defensive" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← All games" })).toHaveAttribute(
      "href",
      "/league/1?tab=games&week=7",
    );
  });

  it("marks your players and links the ones it could match", () => {
    render(panel(["p1"]));
    const row = screen.getByRole("rowheader", { name: /Jayden Daniels/ });
    expect(within(row).getByText("You")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Jayden Daniels" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: /Bobby Wagner/ })).not.toHaveTextContent("You");
  });

  it("switches teams with the tabs, by keyboard too", async () => {
    const user = userEvent.setup();
    render(panel());
    await user.click(screen.getByRole("tab", { name: "KC" }));
    expect(screen.getByRole("table", { name: "KC rushing" })).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "WAS passing" })).not.toBeInTheDocument();
  });

  it("says so when ESPN has no box score", () => {
    render(<BoxScorePanel data={null} leagueId="1" week={7} mine={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent("not available");
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(panel(["p1"]));
  });
});

describe("BoxScorePanel without teams", () => {
  it("says it is not available rather than showing empty tabs", () => {
    render(
      <BoxScorePanel
        data={{ home: "KC", away: "WAS", final: true, teams: [] }}
        leagueId="1"
        week={7}
        mine={[]}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("not available");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });
});
