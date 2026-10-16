import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import WeeklyLineups from "../components/WeeklyLineups";
import type { LineupPlayer, Lineups, TeamLineup } from "../lib/api";
import {
  formatPoints,
  isMine,
  orderMatchups,
  orientMatchup,
  pairRows,
  weekState,
  winnerId,
} from "../lib/lineups";
import { expectNoA11yViolations } from "./a11y";

const player = (
  slot: string,
  name: string,
  points: number | null,
  extra: Partial<LineupPlayer> = {},
): LineupPlayer => ({
  slot,
  player_id: name,
  name,
  position: slot === "BN" ? "WR" : slot,
  team: "SF",
  points,
  ...extra,
});

const team = (
  id: number,
  name: string,
  points: number,
  starters: LineupPlayer[],
  bench: LineupPlayer[] = [],
): TeamLineup => ({
  roster_id: id,
  team: name,
  owner_id: `u${id}`,
  points,
  starters,
  bench,
});

const cole = team(
  1,
  "Cole",
  120.5,
  [
    player("QB", "Cole QB", 24.5, {
      game: { state: "final", date: "2026-10-04", opponent: "CHI", home: true },
      stat_line: "24/35, 281 yds, 2 TD",
    }),
    player("RB", "Cole RB", 10),
  ],
  [player("BN", "Cole Bench", 3.25), player("BN", "Cole Bench Two", 1)],
);
const dad = team(
  2,
  "Dad",
  98,
  [
    player("QB", "Dad QB", 18),
    player("RB", "Empty", null, { player_id: null, position: null, team: null }),
  ],
  [player("BN", "Dad Bench", 9)],
);
const other = team(3, "Sis", 80, [player("QB", "Sis QB", 10)]);
const rival = team(4, "Bro", 70, [player("QB", "Bro QB", 9)]);

const data: Lineups = {
  week: 5,
  current_week: 6,
  weeks: [4, 5, 6, 7],
  matchups: [
    { matchup_id: 1, teams: [other, rival] },
    { matchup_id: 2, teams: [cole, dad] },
  ],
};

describe("WeeklyLineups", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<WeeklyLineups data={data} leagueId="9" myRosterId={1} />);
  });

  it("puts your matchup first and labels it", () => {
    render(<WeeklyLineups data={data} leagueId="9" myRosterId={1} />);
    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("Your matchup")).toBeInTheDocument();
    expect(within(cards[0]).getAllByText("Cole").length).toBeGreaterThan(0);
    expect(within(cards[1]).queryByText("Your matchup")).not.toBeInTheDocument();
  });

  it("always puts your team on the left, even when the data lists it second", () => {
    const flipped: Lineups = { ...data, matchups: [{ matchup_id: 2, teams: [dad, cole] }] };
    render(<WeeklyLineups data={flipped} leagueId="9" myRosterId={1} />);
    const table = screen.getByRole("table", { name: /Cole versus Dad/ });
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers[0]).toBe("Cole");
    expect(headers[4]).toBe("Dad");
    const firstRow = within(table).getAllByRole("row")[1];
    const cells = within(firstRow).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("Cole QB");
    expect(cells[cells.length - 1]).toHaveTextContent("Dad QB");
  });

  it("keeps the given order when no team is yours", () => {
    render(<WeeklyLineups data={data} leagueId="9" myRosterId={null} />);
    expect(within(screen.getAllByRole("article")[0]).getAllByText("Sis").length).toBeGreaterThan(0);
  });

  it("aligns the two lineups row by row with the slot in the middle and the bench below", () => {
    render(<WeeklyLineups data={data} leagueId="9" myRosterId={1} />);
    const table = screen.getByRole("table", { name: /Cole versus Dad/ });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(1 + 2 + 2); // header + 2 starters + 2 bench rows (the longer bench)
    expect(within(rows[1]).getByRole("rowheader", { name: "QB" })).toBeInTheDocument();
    expect(within(rows[1]).getByText("Cole QB")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Dad QB")).toBeInTheDocument();
    expect(within(rows[3]).getByRole("rowheader", { name: "Bench" })).toBeInTheDocument();
    expect(within(rows[3]).getByText("Cole Bench")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Dad Bench")).toBeInTheDocument();
    expect(within(rows[4]).getByText("Cole Bench Two")).toBeInTheDocument(); // Dad has no second bench player
  });

  it("shows a scoreboard with the winner marked in text for a played week", () => {
    render(<WeeklyLineups data={data} leagueId="9" myRosterId={1} />);
    expect(screen.getByText("120.50")).toBeInTheDocument();
    expect(screen.getByText("98.00")).toBeInTheDocument();
    expect(screen.getAllByText("Winner")).toHaveLength(2); // one per played matchup
    expect(screen.getByText("Final scores for this week.")).toBeInTheDocument();
  });

  it("shows each player's game status in the lineup", () => {
    render(<WeeklyLineups data={data} leagueId="9" myRosterId={1} />);
    expect(screen.getByText("Played")).toBeInTheDocument();
    expect(screen.getByText("vs CHI")).toBeInTheDocument();
  });

  it("summarises how a player did once his game has started, and says nothing before", () => {
    render(<WeeklyLineups data={data} leagueId="9" myRosterId={1} />);
    expect(screen.getByText("24/35, 281 yds, 2 TD")).toBeInTheDocument();
    expect(screen.getAllByText(/Stats this week:/)).toHaveLength(1); // only the one player has a line
  });

  it("offers week chips as links with the selected, current and upcoming weeks identified", () => {
    render(<WeeklyLineups data={data} leagueId="9" myRosterId={1} />);
    const nav = screen.getByRole("navigation", { name: "Week" });
    const links = within(nav).getAllByRole("link");
    expect(links).toHaveLength(4);
    expect(links[1]).toHaveAttribute("aria-current", "page"); // week 5 is selected
    expect(links[1]).toHaveAttribute("href", "/league/9?tab=lineups&week=5");
    expect(within(nav).getByText("(this week)")).toBeInTheDocument();
    expect(within(nav).getByText("(upcoming)")).toBeInTheDocument();
  });

  it("hides scores for an upcoming week and explains what the lineups are", () => {
    const upcoming: Lineups = {
      ...data,
      week: 7,
      matchups: [{ matchup_id: 2, teams: [cole, dad] }],
    };
    render(<WeeklyLineups data={upcoming} leagueId="9" myRosterId={1} />);
    expect(
      screen.getByText(/Upcoming week: lineups show each team's current starters/),
    ).toBeInTheDocument();
    expect(screen.queryByText("120.50")).not.toBeInTheDocument();
    expect(screen.queryByText("Winner")).not.toBeInTheDocument();
  });

  it("explains an empty state and hides the chips", () => {
    render(<WeeklyLineups data={{ week: null, weeks: [], matchups: [] }} leagueId="9" />);
    expect(screen.getByText("No matchups have been synced yet.")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Week" })).not.toBeInTheDocument();
  });

  it("handles a team without an opponent", () => {
    render(
      <WeeklyLineups
        data={{ ...data, matchups: [{ matchup_id: null, teams: [other] }] }}
        leagueId="9"
        myRosterId={null}
      />,
    );
    expect(screen.getByText("No opponent this week.")).toBeInTheDocument();
  });
});

describe("lineup helpers", () => {
  it("classifies weeks against the current week", () => {
    expect(weekState(5, 6)).toBe("played");
    expect(weekState(6, 6)).toBe("current");
    expect(weekState(7, 6)).toBe("upcoming");
    expect(weekState(3, null)).toBe("played");
  });

  it("orders your matchup first without disturbing the rest", () => {
    const ordered = orderMatchups(data.matchups, 1);
    expect(ordered.map((m) => m.matchup_id)).toEqual([2, 1]);
    expect(orderMatchups(data.matchups, 99).map((m) => m.matchup_id)).toEqual([1, 2]);
    expect(isMine(data.matchups[1], 1)).toBe(true);
    expect(isMine(data.matchups[0], null)).toBe(false);
  });

  it("orients only your own matchup", () => {
    const flipped = { matchup_id: 2, teams: [dad, cole] };
    expect(orientMatchup(flipped, 1).teams.map((t) => t.roster_id)).toEqual([1, 2]);
    expect(orientMatchup(flipped, 2).teams.map((t) => t.roster_id)).toEqual([2, 1]);
    expect(orientMatchup(flipped, 99)).toBe(flipped); // not your matchup: untouched
    expect(orientMatchup(flipped, null)).toBe(flipped);
    expect(orientMatchup({ matchup_id: 5, teams: [cole] }, 1).teams).toHaveLength(1);
  });

  it("pairs rows, padding the shorter side", () => {
    const rows = pairRows(cole, dad);
    expect(rows.map((r) => r.slot)).toEqual(["QB", "RB", "Bench", "Bench"]);
    expect(rows[3].right).toBeNull();
    expect(rows.filter((r) => r.kind === "bench")).toHaveLength(2);
  });

  it("shows IR and taxi players in their own labelled rows after the bench", () => {
    const hurt = player("IR", "Hurt Guy", 0);
    const stash = player("TAXI", "Stash Guy", 0);
    const a = team(1, "A", 10, [player("QB", "A QB", 10)], [player("BN", "A Bench", 1), hurt]);
    const b = team(2, "B", 9, [player("QB", "B QB", 9)], [stash]);
    const rows = pairRows(a, b);
    expect(rows.map((r) => [r.slot, r.kind])).toEqual([
      ["QB", "starter"],
      ["Bench", "bench"],
      ["IR", "ir"],
      ["Taxi", "taxi"],
    ]);
    expect(rows[2].left?.name).toBe("Hurt Guy");
    expect(rows[2].right).toBeNull();
    expect(rows[3].right?.name).toBe("Stash Guy");
  });

  it("never drops a non-starter, even with an unexpected slot label", () => {
    const a = team(1, "A", 1, [player("QB", "A QB", 1)], [player("MYSTERY", "Odd Slot Guy", 2)]);
    const b = team(2, "B", 1, [player("QB", "B QB", 1)]);
    const rows = pairRows(a, b);
    expect(rows.map((r) => r.left?.name)).toContain("Odd Slot Guy");
    expect(rows.find((r) => r.left?.name === "Odd Slot Guy")?.kind).toBe("bench");
  });

  it("renders IR and taxi rows with a visible text label and their own row class", () => {
    const a = team(1, "A", 10, [player("QB", "A QB", 10)], [player("IR", "Hurt Guy", 0)]);
    const b = team(2, "B", 9, [player("QB", "B QB", 9)]);
    render(
      <WeeklyLineups
        data={{
          week: 5,
          current_week: 6,
          weeks: [5],
          matchups: [{ matchup_id: 1, teams: [a, b] }],
        }}
        leagueId="9"
        myRosterId={null}
      />,
    );
    const irRow = screen.getByRole("rowheader", { name: "IR" }).closest("tr") as HTMLElement;
    expect(irRow.className).toBe("ir");
    expect(within(irRow).getByText("Hurt Guy")).toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: "Bench" })).not.toBeInTheDocument();
  });

  it("finds the winner, or nobody on a tie", () => {
    expect(winnerId(cole, dad)).toBe(1);
    expect(winnerId(dad, cole)).toBe(1);
    expect(winnerId(cole, { ...dad, points: 120.5 })).toBeNull();
  });

  it("formats points", () => {
    expect(formatPoints(3.256)).toBe("3.26");
    expect(formatPoints(null)).toBe("–");
  });
});
