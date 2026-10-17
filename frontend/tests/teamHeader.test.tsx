import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TeamHeader from "../components/TeamHeader";
import type { Lineups, StandingsRow } from "../lib/api";
import { ownershipText } from "../lib/lineups";
import { teamStanding } from "../lib/teamStanding";
import { expectNoA11yViolations } from "./a11y";

const row = (id: number, rank: number, w: number, l: number, pf: number, pa: number) =>
  ({
    rank,
    roster_id: id,
    team: `T${id}`,
    owner_id: null,
    wins: w,
    losses: l,
    ties: 0,
    points_for: pf,
    points_against: pa,
    streak: id === 1 ? "2W" : null,
  }) as StandingsRow;

const standings = [
  row(1, 4, 3, 2, 142, 120),
  row(2, 1, 5, 0, 200, 90),
  row(3, 2, 4, 1, 150, 100),
  row(4, 3, 3, 2, 120, 130),
];

describe("teamStanding", () => {
  it("gives record, place and the points ranks (most scored, fewest allowed)", () => {
    expect(teamStanding(standings, 1)).toEqual({
      record: "3-2",
      place: "4th",
      pointsFor: "3rd",
      pointsAgainst: "3rd",
      streak: "▲2W",
    });
  });

  it("is null for an unknown team or no standings, and shows ties", () => {
    expect(teamStanding(standings, 99)).toBeNull();
    expect(teamStanding(undefined, 1)).toBeNull();
    const tied = [{ ...standings[0], ties: 1 }];
    expect(teamStanding(tied, 1)?.record).toBe("3-2-1");
  });
});

describe("ownershipText", () => {
  it("writes ESPN's shares like Sleeper does", () => {
    expect(ownershipText({ owned_pct: 88.2, started_pct: 52.6 })).toBe("88% Rostered | 53% Start");
    expect(ownershipText({ owned_pct: 99.9 })).toBe("100% Rostered");
    expect(ownershipText({ owned_pct: null, started_pct: undefined })).toBeNull();
  });
});

describe("TeamHeader", () => {
  const lineups = {
    week: 7,
    current_week: 7,
    weeks: [7],
    matchups: [
      {
        matchup_id: 1,
        teams: [
          {
            roster_id: 1,
            team: "T1",
            owner_id: null,
            points: 0,
            projected: 52.39,
            starters: [],
            bench: [],
          },
          {
            roster_id: 2,
            team: "T2",
            owner_id: null,
            points: 0,
            projected: 54.27,
            starters: [],
            bench: [],
          },
        ],
      },
    ],
  } as unknown as Lineups;

  it("shows the name, standing line and this week's projection", () => {
    render(
      <TeamHeader
        rosterId={1}
        name="Shough Around"
        headingId="h"
        standings={standings}
        lineups={lineups}
      />,
    );
    expect(screen.getByRole("heading", { name: "Shough Around" })).toBeInTheDocument();
    const line = screen.getByRole("list", { name: "Standing" });
    expect(
      within(line)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["3-2 ▲2W", "4th", "PF 3rd", "PA 3rd"]);
    expect(screen.getByText("52.39")).toBeInTheDocument();
    expect(screen.getByText("Week 7 proj")).toBeInTheDocument();
  });

  it("copes with no standings and no matchup, and has no accessibility violations", async () => {
    const { container } = render(<TeamHeader rosterId={1} name="Solo" headingId="h" />);
    expect(container.querySelector(".team-header-line")).toBeNull();
    expect(container.querySelector(".team-header-proj")).toBeNull();
    await expectNoA11yViolations(
      <TeamHeader
        rosterId={1}
        name="Shough Around"
        headingId="h"
        standings={standings}
        lineups={lineups}
      />,
    );
  });
});
