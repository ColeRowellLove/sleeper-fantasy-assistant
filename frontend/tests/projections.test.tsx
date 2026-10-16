import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MatchupCard from "../components/MatchupCard";
import RostersPanel from "../components/RostersPanel";
import type { Dashboard, TeamLineup } from "../lib/api";
import { formatProjection, projectionDelta, winPercent } from "../lib/lineups";
import { expectNoA11yViolations } from "./a11y";

describe("formatProjection", () => {
  it("shows two decimals and nothing when there is no projection", () => {
    expect(formatProjection(12.3)).toBe("12.30");
    expect(formatProjection(0)).toBe("0.00"); // a real projection of zero is still a projection
    expect(formatProjection(null)).toBeNull();
    expect(formatProjection(undefined)).toBeNull();
  });
});

describe("projectionDelta", () => {
  it("is the signed difference for a finished week", () => {
    expect(projectionDelta(15.3, 12.1, "played")).toBe("+3.2");
    expect(projectionDelta(8, 12.04, "played")).toBe("-4.0");
    expect(projectionDelta(10, 10.02, "played")).toBe("0.0");
  });

  it("is absent until the week is over, since partial points would mislead", () => {
    expect(projectionDelta(0, 12, "upcoming")).toBeNull();
    expect(projectionDelta(40, 120, "current")).toBeNull();
  });

  it("is absent when either number is missing", () => {
    expect(projectionDelta(null, 12, "played")).toBeNull();
    expect(projectionDelta(10, null, "played")).toBeNull();
    expect(projectionDelta(10, undefined, "played")).toBeNull();
  });
});

const lineup = (
  id: number,
  name: string,
  withProjection: boolean,
): TeamLineup => ({
  roster_id: id,
  team: name,
  owner_id: null,
  points: 104.2,
  projected: withProjection ? 98.1 : null,
  starters: [
    {
      slot: "RB",
      player_id: `p${id}`,
      name: `${name} RB`,
      position: "RB",
      team: "SF",
      points: 15.8,
      projected: withProjection ? 12.4 : null,
    },
  ],
  bench: [],
});

describe("projected points in the matchup", () => {
  const matchup = (a: boolean, b: boolean) => ({
    matchup_id: 1,
    teams: [lineup(1, "Cole", a), lineup(2, "Dad", b)],
  });

  it("shows each team's projected total and each player's projection beside the actual", () => {
    render(
      <MatchupCard
        matchup={matchup(true, true)}
        state="played"
        week={6}
        myRosterId={1}
      />,
    );
    expect(screen.getAllByText(/Projected 98\.10/)).toHaveLength(2);
    expect(screen.getAllByText(/Proj 12\.40/)).toHaveLength(2);
  });

  it("states the difference in words for screen readers, not by color", () => {
    render(
      <MatchupCard
        matchup={matchup(true, false)}
        state="played"
        week={6}
        myRosterId={1}
      />,
    );
    // 104.2 - 98.1 = +6.1 for the team, 15.8 - 12.4 = +3.4 for the player
    expect(screen.getByText(/\(\+6\.1/)).toBeInTheDocument();
    expect(screen.getByText(/\(\+3\.4/)).toBeInTheDocument();
    expect(
      screen.getAllByText("against projection", { exact: false }),
    ).toHaveLength(2);
  });

  it("shows no projection line, and no zero, for a team or player without one", () => {
    render(
      <MatchupCard
        matchup={matchup(false, false)}
        state="played"
        week={6}
        myRosterId={1}
      />,
    );
    expect(screen.queryByText(/Proj/)).not.toBeInTheDocument();
  });

  it("shows the projection but no comparison while the week is still being played", () => {
    render(
      <MatchupCard
        matchup={matchup(true, true)}
        state="current"
        week={6}
        myRosterId={1}
      />,
    );
    expect(screen.getAllByText(/Proj 12\.40/)).toHaveLength(2);
    expect(screen.queryByText(/against projection/)).not.toBeInTheDocument();
  });

  it("shows the projection but no comparison before the games", () => {
    render(
      <MatchupCard
        matchup={matchup(true, true)}
        state="upcoming"
        week={7}
        myRosterId={1}
      />,
    );
    expect(screen.getAllByText(/Proj 12\.40/)).toHaveLength(2);
    expect(screen.queryByText(/against projection/)).not.toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <MatchupCard
        matchup={matchup(true, true)}
        state="played"
        week={6}
        myRosterId={1}
      />,
    );
  });
});

describe("projected points on rosters", () => {
  const rosters: Dashboard["rosters"] = [
    {
      roster_id: 1,
      team: "Cole",
      owner_id: "u1",
      players: [
        {
          player_id: "1",
          name: "Has Projection",
          position: "WR",
          team: "LAR",
          status: "starter",
          slot: "WR",
          projected: 22.44,
        },
        {
          player_id: "2",
          name: "No Projection",
          position: "WR",
          team: "SEA",
          status: "bench",
          slot: null,
        },
      ],
    },
  ];

  it("shows a projection with a spoken label, and nothing for a player without one", () => {
    render(<RostersPanel rosters={rosters} myRosterId={1} />);
    expect(screen.getByText("Projected", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/22\.4/)).toBeInTheDocument();
    expect(screen.getAllByText("Projected", { exact: false })).toHaveLength(1);
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <RostersPanel rosters={rosters} myRosterId={1} />,
    );
  });
});

describe("win chance in the matchup", () => {
  const withChance = (a: number | null, b: number | null) => ({
    matchup_id: 1,
    teams: [
      { ...lineup(1, "Cole", true), win_probability: a },
      { ...lineup(2, "Dad", true), win_probability: b },
    ],
  });

  it("rounds to a whole percent and never shows 0 or 100", () => {
    expect(winPercent(0.6234)).toBe(62);
    expect(winPercent(0.5)).toBe(50);
    expect(winPercent(0.9999)).toBe(99);
    expect(winPercent(0.0001)).toBe(1);
    expect(winPercent(null)).toBeNull();
    expect(winPercent(undefined)).toBeNull();
    expect(winPercent(Number.NaN)).toBeNull();
  });

  it("shows each team's chance with a full sentence for screen readers", () => {
    render(
      <MatchupCard
        matchup={withChance(0.62, 0.38)}
        state="upcoming"
        week={7}
        myRosterId={1}
      />,
    );
    expect(screen.getByText("Win chance 62%")).toBeInTheDocument();
    expect(screen.getByText("Win chance 38%")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Cole has a 62 percent chance to win, from projected points",
      ),
    ).toBeInTheDocument();
  });

  it("is shown while the week is being played too", () => {
    render(
      <MatchupCard
        matchup={withChance(0.8, 0.2)}
        state="current"
        week={6}
        myRosterId={1}
      />,
    );
    expect(screen.getByText("Win chance 80%")).toBeInTheDocument();
  });

  it("is not shown once the matchup is played, or when there is no chance to show", () => {
    const { unmount } = render(
      <MatchupCard
        matchup={withChance(0.62, 0.38)}
        state="played"
        week={5}
        myRosterId={1}
      />,
    );
    expect(screen.queryByText(/Win chance/)).not.toBeInTheDocument();
    unmount();
    render(
      <MatchupCard
        matchup={withChance(null, null)}
        state="upcoming"
        week={7}
        myRosterId={1}
      />,
    );
    expect(screen.queryByText(/Win chance/)).not.toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <MatchupCard
        matchup={withChance(0.62, 0.38)}
        state="upcoming"
        week={7}
        myRosterId={1}
      />,
    );
  });
});

describe("this week's points on rosters", () => {
  const withPoints: Dashboard["rosters"] = [
    {
      roster_id: 1,
      team: "Cole",
      owner_id: "u1",
      players: [
        {
          player_id: "1",
          name: "Scored",
          position: "WR",
          team: "SF",
          status: "starter",
          slot: "WR",
          points: 14.25,
          projected: 12,
        },
        {
          player_id: "2",
          name: "Scored Zero",
          position: "WR",
          team: "SF",
          status: "bench",
          slot: null,
          points: 0,
        },
        {
          player_id: "3",
          name: "Not Played",
          position: "WR",
          team: "LAR",
          status: "bench",
          slot: null,
          projected: 9,
        },
      ],
    },
  ];

  it("shows points for a player whose game has started, with a spoken label", () => {
    render(<RostersPanel rosters={withPoints} myRosterId={1} />);
    const scored = screen.getByText("Scored").closest("li") as HTMLElement;
    expect(within(scored).getByText("14.3")).toBeInTheDocument();
    expect(
      within(scored).getByText("Points this week", { exact: false }),
    ).toBeInTheDocument();
    expect(
      within(scored).getByText("Projected", { exact: false }),
    ).toBeInTheDocument(); // still there
  });

  it("shows a real zero but nothing for a player who has not played", () => {
    render(<RostersPanel rosters={withPoints} myRosterId={1} />);
    expect(
      screen.getAllByText("Points this week", { exact: false }),
    ).toHaveLength(2); // 14.25 and 0
    expect(screen.getByText("0.0")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <RostersPanel rosters={withPoints} myRosterId={1} />,
    );
  });
});

describe("a projection of zero", () => {
  it("is shown like any other projection, so every row has a Proj number", () => {
    const zero = lineup(1, "Cole", true);
    zero.starters[0] = {
      ...zero.starters[0],
      projected: 0,
      projection_missing: true,
    };
    const matchup = { matchup_id: 1, teams: [zero, lineup(2, "Dad", true)] };
    render(
      <MatchupCard
        matchup={matchup}
        state="upcoming"
        week={7}
        myRosterId={1}
      />,
    );
    expect(screen.getByText("Proj 0.00")).toBeInTheDocument();
    expect(screen.getAllByText(/Proj 12\.40/)).toHaveLength(1); // the other side still has its number
  });
});
