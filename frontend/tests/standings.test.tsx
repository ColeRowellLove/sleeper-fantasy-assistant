import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("sorting", () => {
  const league = [
    row(1, 3, "Dad", 4, 1),
    row(2, 1, "Cole", 3, 1, 1),
    row(3, 2, "Sis", 2, 3),
    row(4, 4, "alex", 1, 4),
  ];
  const teams = () =>
    screen
      .getAllByRole("rowheader")
      .map((cell) => cell.textContent?.replace("You", ""));
  const sortBy = (name: RegExp) => userEvent.click(screen.getByRole("button", { name }));
  const renderLeague = (myRosterId: number | null = null) =>
    render(<StandingsTable standings={league} playoffTeams={2} myRosterId={myRosterId} />);

  it("starts in rank order with every column offering a sort button", () => {
    renderLeague();
    expect(teams()).toEqual(["Dad", "Cole", "Sis", "alex"]);
    for (const name of ["Rank", "Team", "Record", "PF", "PA"]) {
      expect(screen.getByRole("button", { name: new RegExp(`^${name}`) })).toBeInTheDocument();
    }
    expect(screen.getByRole("columnheader", { name: /Rank/ })).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByRole("columnheader", { name: /PF/ })).toHaveAttribute("aria-sort", "none");
  });

  it("sorts every column high to low, then low to high", async () => {
    renderLeague();
    await sortBy(/^PF/); // PF is 700 + roster id: first click is high to low
    expect(teams()).toEqual(["alex", "Dad", "Sis", "Cole"]);
    await sortBy(/^PF/);
    expect(teams()).toEqual(["Cole", "Sis", "Dad", "alex"]);

    await sortBy(/^Record/);
    expect(teams()).toEqual(["Dad", "Cole", "Sis", "alex"]);
    await sortBy(/^Record/);
    expect(teams()).toEqual(["alex", "Sis", "Cole", "Dad"]);

    await sortBy(/^Rank/);
    await sortBy(/^Rank/);
    expect(teams()).toEqual(["alex", "Sis", "Cole", "Dad"]); // worst first
  });

  it("sorts team names A to Z ignoring case, then Z to A", async () => {
    renderLeague();
    await sortBy(/^Team/);
    expect(teams()).toEqual(["alex", "Cole", "Dad", "Sis"]);
    await sortBy(/^Team/);
    expect(teams()).toEqual(["Sis", "Dad", "Cole", "alex"]);
  });

  it("sorts PA with ties kept in rank order both ways", async () => {
    renderLeague(); // every team has the same PA
    await sortBy(/^PA/);
    expect(teams()).toEqual(["Dad", "Cole", "Sis", "alex"]);
    await sortBy(/^PA/);
    expect(teams()).toEqual(["Dad", "Cole", "Sis", "alex"]);
  });

  it("tells assistive tech which column is sorted and which way", async () => {
    renderLeague();
    await sortBy(/^PF/);
    expect(screen.getByRole("columnheader", { name: /PF/ })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: /Rank/ })).toHaveAttribute("aria-sort", "none");
    expect(screen.getByRole("status")).toHaveTextContent("Sorted by PF, high to low");
    await sortBy(/^PF/);
    expect(screen.getByRole("columnheader", { name: /PF/ })).toHaveAttribute("aria-sort", "ascending");
  });

  it("works from the keyboard", async () => {
    renderLeague();
    const user = userEvent.setup();
    await user.tab(); // Rank
    await user.tab(); // Team
    await user.keyboard("{Enter}");
    expect(teams()).toEqual(["alex", "Cole", "Dad", "Sis"]);
    await user.keyboard(" "); // Space also activates it
    expect(teams()).toEqual(["Sis", "Dad", "Cole", "alex"]);
  });

  it("keeps each team's real rank, playoff marks and You highlight when reordered", async () => {
    renderLeague(1);
    await sortBy(/^Team/);
    const rows = screen.getAllByRole("row").slice(1);
    const cole = rows.find((r) => within(r).queryByText("Cole"))!;
    expect(within(cole).getByText("2")).toBeInTheDocument(); // still rank 2, not row 2
    expect(cole).toHaveAttribute("aria-current", "true");
    expect(cole.className).toContain("cutoff");
    expect(rows[3].className).not.toContain("playoff"); // Sis, rank 3, sorts last-but-one
    expect(screen.getAllByText("You")).toHaveLength(1);
  });

  it("has no accessibility violations while sorted", async () => {
    await expectNoA11yViolations(
      <StandingsTable standings={league} playoffTeams={2} myRosterId={1} />,
    );
  });
});
