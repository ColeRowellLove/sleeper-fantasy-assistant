import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RosterMatchup from "../components/RosterMatchup";
import RostersPanel from "../components/RostersPanel";
import type { Dashboard, Lineups, TeamLineup } from "../lib/api";
import { matchupFor } from "../lib/lineups";
import { expectNoA11yViolations } from "./a11y";

const team = (id: number, name: string, points: number, win?: number | null): TeamLineup => ({
  roster_id: id,
  team: name,
  owner_id: `u${id}`,
  points,
  win_probability: win,
  starters: [],
  bench: [],
});

const lineups = (over: Partial<Lineups> = {}): Lineups => ({
  week: 6,
  current_week: 6,
  weeks: [6],
  matchups: [
    { matchup_id: 1, teams: [team(1, "Cole", 55.5, 0.62), team(2, "Dad Bods", 41.25, 0.38)] },
    { matchup_id: 2, teams: [team(3, "Sis", 0, null)] },
  ],
  ...over,
});

describe("matchupFor", () => {
  it("finds a team's matchup with that team first and the opponent second", () => {
    const found = matchupFor(lineups(), 2);
    expect(found?.team.team).toBe("Dad Bods");
    expect(found?.opponent?.team).toBe("Cole");
    expect(found?.state).toBe("current");
    expect(found?.week).toBe(6);
  });

  it("has no opponent for a team on a bye and nothing for an unknown team or no lineups", () => {
    expect(matchupFor(lineups(), 3)?.opponent).toBeNull();
    expect(matchupFor(lineups(), 99)).toBeNull();
    expect(matchupFor(null, 1)).toBeNull();
    expect(matchupFor(undefined, 1)).toBeNull();
  });
});

describe("RosterMatchup", () => {
  it("shows the opponent, the score and the same win bar as the lineups", () => {
    render(<RosterMatchup lineups={lineups()} rosterId={1} leagueId="9" />);
    expect(screen.getByRole("heading", { name: "Week 6 matchup" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dad Bods" })).toHaveAttribute(
      "href",
      "/league/9?tab=rosters&roster=2",
    );
    expect(screen.getByText("55.50")).toBeInTheDocument();
    expect(screen.getByText("41.25")).toBeInTheDocument();
    expect(
      screen.getByText(/Cole has a 62 percent chance to win and Dad Bods has 38 percent/),
    ).toBeInTheDocument();
  });

  it("orients the bar from the selected team's side", () => {
    render(<RosterMatchup lineups={lineups()} rosterId={2} leagueId="9" />);
    expect(
      screen.getByText(/Dad Bods has a 38 percent chance to win and Cole has 62 percent/),
    ).toBeInTheDocument();
  });

  it("names the opponent and says why when there is no chance to show", () => {
    const none = lineups({
      matchups: [
        { matchup_id: 1, teams: [team(1, "Cole", 10, null), team(2, "Dad Bods", 8, null)] },
      ],
    });
    render(<RosterMatchup lineups={none} rosterId={1} leagueId="9" />);
    expect(screen.getByText("No win chance to show yet.")).toBeInTheDocument();
    expect(screen.queryByText(/percent chance/)).not.toBeInTheDocument();
  });

  it("gives the result instead of a bar for a finished week", () => {
    const done = lineups({ current_week: 7 });
    render(<RosterMatchup lineups={done} rosterId={1} leagueId="9" />);
    expect(screen.getByText("Cole won this week.")).toBeInTheDocument();
    expect(screen.queryByText(/percent chance/)).not.toBeInTheDocument();
  });

  it("shows no score before the games and handles a team without an opponent", () => {
    const before = lineups({ current_week: 5 });
    const { rerender } = render(<RosterMatchup lineups={before} rosterId={1} leagueId="9" />);
    expect(screen.queryByText(/to 41.25/)).not.toBeInTheDocument();
    rerender(<RosterMatchup lineups={lineups()} rosterId={3} leagueId="9" />);
    expect(screen.getByText("No opponent this week.")).toBeInTheDocument();
  });

  it("shows nothing before the season has a week, instead of a made-up result", () => {
    const offseason = lineups({ week: null, current_week: null });
    const { container } = render(<RosterMatchup lineups={offseason} rosterId={1} leagueId="9" />);
    expect(container).toBeEmptyDOMElement();
    expect(matchupFor(offseason, 1)).toBeNull();
  });

  it("does not label a team as winning or behind before the games are over", () => {
    render(<RosterMatchup lineups={lineups()} rosterId={1} leagueId="9" />);
    expect(screen.queryByText(/Winning|Behind/)).not.toBeInTheDocument();
  });

  it("renders nothing without lineups", () => {
    const { container } = render(<RosterMatchup lineups={null} rosterId={1} leagueId="9" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<RosterMatchup lineups={lineups()} rosterId={1} leagueId="9" />);
  });
});

describe("the Rosters tab", () => {
  const rosters: Dashboard["rosters"] = [
    { roster_id: 1, team: "Cole", owner_id: "u1", players: [] },
    { roster_id: 2, team: "Dad Bods", owner_id: "u2", players: [] },
  ];

  it("puts the selected team's matchup above its roster", () => {
    render(
      <RostersPanel rosters={rosters} myRosterId={1} lineups={lineups()} leagueId="9" week={6} />,
    );
    const section = screen.getByRole("heading", { name: "Week 6 matchup" }).closest("section");
    expect(section).not.toBeNull();
    expect(
      within(section as HTMLElement).getByText(/Cole has a 62 percent chance/),
    ).toBeInTheDocument();
  });

  it("still works without lineups", () => {
    render(<RostersPanel rosters={rosters} myRosterId={1} leagueId="9" />);
    expect(screen.queryByRole("heading", { name: /matchup/ })).not.toBeInTheDocument();
  });
});
