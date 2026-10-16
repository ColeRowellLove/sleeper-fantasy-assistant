import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MatchupCard from "../components/MatchupCard";
import PlayerStatLine from "../components/PlayerStatLine";
import type { GameInfo, TeamLineup } from "../lib/api";
import { expectNoA11yViolations } from "./a11y";

const game = (state: GameInfo["state"]): GameInfo =>
  ({ state, opponent: "ARI", home: true, kickoff: "2026-10-18T17:00:00Z" }) as GameInfo;

const team = (id: number, name: string, state: GameInfo["state"], line: string): TeamLineup => ({
  roster_id: id,
  team: name,
  owner_id: null,
  points: 20,
  projected: 100,
  starters: [
    {
      slot: "RB",
      player_id: `p${id}`,
      name: `${name} RB`,
      position: "RB",
      team: "SF",
      points: state === "upcoming" ? null : 12.5,
      projected: 14,
      game: game(state),
      stat_line: line,
      stat_line_projected: state === "upcoming",
    },
  ],
  bench: [],
});

describe("PlayerStatLine", () => {
  it("tags a forecast as projected, in words for screen readers too", () => {
    render(<PlayerStatLine line="58 yds, 0.6 TD" projected />);
    expect(screen.getByText("Proj")).toBeInTheDocument();
    expect(screen.getByText(/Projected stats:/)).toBeInTheDocument();
    expect(screen.queryByText(/Stats this week/)).not.toBeInTheDocument();
  });

  it("shows a real line as stats and nothing without a line", () => {
    const { container, rerender } = render(<PlayerStatLine line="18 car, 92 yds" />);
    expect(screen.getByText(/Stats this week:/)).toBeInTheDocument();
    expect(screen.queryByText("Proj")).not.toBeInTheDocument();
    rerender(<PlayerStatLine line={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("a player who has not played yet in a week under way", () => {
  const matchup = {
    matchup_id: 1,
    teams: [
      team(1, "Cole", "upcoming", "58 yds, 0.6 TD"),
      team(2, "Dad", "final", "18 car, 92 yds"),
    ],
  };

  it("shows a dash for points and his projected line; the player who played shows both", async () => {
    const ui = <MatchupCard matchup={matchup} state="current" week={7} myRosterId={1} />;
    render(ui);
    expect(screen.getByText("58 yds, 0.6 TD")).toBeInTheDocument();
    expect(screen.getByText("18 car, 92 yds")).toBeInTheDocument();
    expect(screen.getByText("12.50")).toBeInTheDocument(); // the one who played
    expect(screen.getAllByText("–").length).toBeGreaterThan(0); // the one who has not
    await expectNoA11yViolations(ui);
  });
});
