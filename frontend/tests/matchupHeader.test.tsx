import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MatchupHeader from "../components/MatchupHeader";
import type { GameInfo, LineupPlayer, StandingsRow, TeamLineup } from "../lib/api";
import { streakText, teamInitials, yetToPlay } from "../lib/lineups";
import { expectNoA11yViolations } from "./a11y";

const game = (state: GameInfo["state"]): GameInfo => ({
  state,
  date: "2026-10-18",
  opponent: "SF",
  home: true,
});

const player = (position: string, state: GameInfo["state"]): LineupPlayer => ({
  slot: position,
  player_id: `${position}-${state}`,
  name: `${position} Player`,
  position,
  team: "SEA",
  points: null,
  game: game(state),
});

const team = (id: number, name: string, starters: LineupPlayer[]): TeamLineup => ({
  roster_id: id,
  team: name,
  owner_id: null,
  points: 12.5,
  projected: 100.2,
  starters,
  bench: [],
});

const row = (id: number, over: Partial<StandingsRow> = {}): StandingsRow => ({
  rank: id,
  roster_id: id,
  team: "x",
  manager: `mgr${id}`,
  owner_id: null,
  wins: 3,
  losses: 2,
  ties: 0,
  points_for: 0,
  points_against: 0,
  streak: "2W",
  ...over,
});

describe("yetToPlay", () => {
  it("counts the starters whose game is not over, by position in the usual order", () => {
    const t = team(1, "A", [
      player("WR", "upcoming"),
      player("RB", "live"),
      player("WR", "upcoming"),
      player("QB", "final"),
      player("TE", "bye"),
      player("DEF", "upcoming"),
    ]);
    expect(yetToPlay(t)).toEqual({ count: 4, text: "RB, 2 WR, DEF" });
  });

  it("is null when nobody is left", () => {
    expect(yetToPlay(team(1, "A", [player("QB", "final")]))).toBeNull();
    expect(yetToPlay(team(1, "A", []))).toBeNull();
  });
});

describe("streakText and teamInitials", () => {
  it("adds an arrow to a streak and keeps the letter", () => {
    expect(streakText("3W")).toBe("▲3W");
    expect(streakText("2L")).toBe("▼2L");
    expect(streakText("1T")).toBe("1T");
    expect(streakText(null)).toBeNull();
    expect(streakText("nonsense")).toBeNull();
  });

  it("takes up to two initials from the team name", () => {
    expect(teamInitials("Shough Around & Find Out")).toBe("SA");
    expect(teamInitials("Dad Bods")).toBe("DB");
    expect(teamInitials("Wolves")).toBe("W");
    expect(teamInitials("狼 隊")).toBe("狼隊"); // letters of any script
    expect(teamInitials("🔥🔥")).toBe("🔥"); // nothing alphabetic: the first symbol
    expect(teamInitials("   ")).toBe("?");
  });
});

describe("MatchupHeader", () => {
  const a = team(1, "Cole", [player("QB", "upcoming"), player("RB", "upcoming")]);
  const b = team(2, "Dad", [player("QB", "final")]);
  const ui = (
    <MatchupHeader
      a={a}
      b={b}
      state="current"
      winner={null}
      myRosterId={1}
      leagueId="9"
      standings={[row(1, { streak: "2W" }), row(2, { wins: 1, losses: 4, streak: "3L" })]}
    />
  );

  it("shows each team's manager, record, streak and seed, score and what is left to play", async () => {
    render(ui);
    expect(screen.getByText("@mgr1")).toBeInTheDocument();
    expect(screen.getByText(/3-2/)).toBeInTheDocument();
    expect(screen.getByText("▲2W")).toBeInTheDocument();
    expect(screen.getByText("▼3L")).toBeInTheDocument();
    expect(screen.getByText("Yet to play (2)")).toBeInTheDocument();
    expect(screen.getByText("QB, RB")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cole" })).toHaveAttribute(
      "href",
      "/league/9?tab=rosters&roster=1",
    );
    expect(screen.getAllByText("Projected 100.20")).toHaveLength(2);
    await expectNoA11yViolations(ui);
  });

  it("hides the record and what is left to play for a finished week", () => {
    render(
      <MatchupHeader
        a={a}
        b={b}
        state="played"
        winner={1}
        myRosterId={null}
        standings={[row(1)]}
      />,
    );
    expect(screen.queryByText(/@mgr1/)).not.toBeInTheDocument(); // the standings are today's
    expect(screen.queryByText(/Yet to play/)).not.toBeInTheDocument();
    expect(screen.getByText("Winner")).toBeInTheDocument();
  });

  it("still works without standings", () => {
    render(<MatchupHeader a={a} b={b} state="current" winner={null} myRosterId={null} />);
    expect(screen.getByText("Cole")).toBeInTheDocument();
    expect(screen.queryByText(/@mgr/)).not.toBeInTheDocument();
  });
});
