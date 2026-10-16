import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MatchupCard from "../components/MatchupCard";
import PlayersTable from "../components/PlayersTable";
import RostersPanel from "../components/RostersPanel";
import StandingsTable from "../components/StandingsTable";
import type { Dashboard, StandingsRow, TeamLineup } from "../lib/api";
import { rosterPath } from "../lib/league";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/league/123",
  useSearchParams: () => new URLSearchParams("tab=standings"),
}));

const row = (rank: number, id: number, team: string): StandingsRow => ({
  rank,
  roster_id: id,
  team,
  owner_id: `u${id}`,
  wins: 3,
  losses: 2,
  ties: 0,
  points_for: 700,
  points_against: 650,
});

describe("rosterPath", () => {
  it("links to the Rosters tab starting on that team", () => {
    expect(rosterPath("123", 4)).toBe("/league/123?tab=rosters&roster=4");
    expect(rosterPath("12/3", 4)).toBe("/league/12%2F3?tab=rosters&roster=4"); // the id is encoded
  });
});

describe("team names in the standings", () => {
  const standings = [row(1, 3, "Dad Bods"), row(2, 1, "Cole")];

  it("are links to that team's roster when the league is known", () => {
    render(
      <StandingsTable standings={standings} playoffTeams={null} myRosterId={1} leagueId="123" />,
    );
    expect(screen.getByRole("link", { name: "Dad Bods" })).toHaveAttribute(
      "href",
      "/league/123?tab=rosters&roster=3",
    );
    expect(screen.getByRole("link", { name: "Cole" })).toHaveAttribute(
      "href",
      "/league/123?tab=rosters&roster=1",
    );
  });

  it("stay plain text without a league id, and keep the You marker", () => {
    render(<StandingsTable standings={standings} playoffTeams={null} myRosterId={1} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("You")).toBeInTheDocument();
  });

  it("have no accessibility violations", async () => {
    await expectNoA11yViolations(
      <StandingsTable standings={standings} playoffTeams={null} myRosterId={1} leagueId="123" />,
    );
  });
});

describe("team names in a matchup", () => {
  const lineup = (id: number, name: string): TeamLineup => ({
    roster_id: id,
    team: name,
    owner_id: null,
    points: 10,
    starters: [],
    bench: [],
  });
  const matchup = {
    matchup_id: 1,
    teams: [lineup(1, "Cole"), lineup(2, "Dad")],
  };

  it("link to each team's roster", () => {
    render(
      <MatchupCard matchup={matchup} state="current" week={6} myRosterId={1} leagueId="123" />,
    );
    const names = screen.getAllByRole("link", { name: "Cole" })[0];
    expect(names).toHaveAttribute("href", "/league/123?tab=rosters&roster=1");
    expect(screen.getAllByRole("link", { name: "Dad" })[0]).toHaveAttribute(
      "href",
      "/league/123?tab=rosters&roster=2",
    );
  });

  it("stay plain text without a league id", () => {
    render(<MatchupCard matchup={matchup} state="current" week={6} myRosterId={1} />);
    expect(screen.queryByRole("link", { name: "Cole" })).not.toBeInTheDocument();
  });
});

describe("owner team names on the Players tab", () => {
  const player = {
    player_id: "1",
    name: "Puka Nacua",
    position: "WR",
    team: "LAR",
    owner_roster_id: 3,
    owner_team: "Dad Bods",
    adds: null,
    drops: null,
    total_points: 10,
    rank: 1,
    projected: null,
  };

  it("link to the owner's roster, and an available player has no owner link", () => {
    const data = {
      league_id: "123",
      week: 6,
      players: [
        player,
        {
          ...player,
          player_id: "2",
          name: "Free Guy",
          owner_roster_id: null,
          owner_team: null,
        },
      ],
    };
    render(<PlayersTable data={data} myRosterId={null} leagueId="123" />);
    const owned = screen.getByRole("row", { name: /Puka Nacua/ });
    expect(within(owned).getByRole("link", { name: "Dad Bods" })).toHaveAttribute(
      "href",
      "/league/123?tab=rosters&roster=3",
    );
    const free = screen.getByRole("row", { name: /Free Guy/ });
    expect(within(free).getByText("Available")).toBeInTheDocument();
  });
});

describe("rosters opened from a link", () => {
  const rosters: Dashboard["rosters"] = [
    {
      roster_id: 1,
      team: "Cole",
      owner_id: "u1",
      players: [
        {
          player_id: "a",
          name: "Cole Player",
          position: "WR",
          team: "LAR",
          status: "starter",
          slot: "WR",
        },
      ],
    },
    {
      roster_id: 3,
      team: "Dad Bods",
      owner_id: "u3",
      players: [
        {
          player_id: "b",
          name: "Dad Player",
          position: "RB",
          team: "SF",
          status: "starter",
          slot: "RB",
        },
      ],
    },
  ];

  it("starts on the linked team instead of your own", () => {
    render(<RostersPanel rosters={rosters} myRosterId={1} initialRosterId={3} />);
    expect(screen.getByRole("combobox", { name: "Team" })).toHaveValue("3");
    expect(screen.getByText("Dad Player")).toBeInTheDocument();
    expect(screen.queryByText("Cole Player")).not.toBeInTheDocument();
  });

  it("starts on your team when there is no link, or the link is not one of the league's teams", () => {
    const { unmount } = render(<RostersPanel rosters={rosters} myRosterId={1} />);
    expect(screen.getByRole("combobox", { name: "Team" })).toHaveValue("1");
    unmount();
    render(<RostersPanel rosters={rosters} myRosterId={1} initialRosterId={99} />);
    expect(screen.getByRole("combobox", { name: "Team" })).toHaveValue("1");
  });
});
