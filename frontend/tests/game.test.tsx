import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import GameBadge from "../components/GameBadge";
import RostersPanel from "../components/RostersPanel";
import type { Dashboard, GameInfo } from "../lib/api";
import { formatGameDate, formatKickoff, gameLabel } from "../lib/game";
import { expectNoA11yViolations } from "./a11y";

const upcoming: GameInfo = { state: "upcoming", date: "2026-09-20", opponent: "CHI", home: true };

describe("game labels", () => {
  it("formats dates as UTC so server and browser agree", () => {
    expect(formatGameDate("2026-09-20")).toBe("Sun, Sep 20");
    expect(formatGameDate(null)).toBeNull();
    expect(formatGameDate("not a date")).toBeNull();
  });

  it("describes each state in words", () => {
    expect(gameLabel({ state: "bye", date: null, opponent: null, home: null })).toEqual({
      state: "bye",
      text: "Bye week",
      detail: null,
    });
    expect(gameLabel(upcoming)).toEqual({
      state: "upcoming",
      text: "Upcoming",
      detail: "Sun, Sep 20 vs CHI",
    });
    expect(gameLabel({ ...upcoming, home: false })?.detail).toBe("Sun, Sep 20 at CHI");
    expect(gameLabel({ ...upcoming, state: "live" })).toEqual({
      state: "live",
      text: "Live",
      detail: "vs CHI",
    });
    expect(gameLabel({ ...upcoming, state: "final" })?.text).toBe("Played");
  });

  it("shows nothing when there is no game info", () => {
    expect(gameLabel(null)).toBeNull();
    expect(gameLabel(undefined)).toBeNull();
  });
});

describe("GameBadge", () => {
  it("has no accessibility violations for every state", async () => {
    await expectNoA11yViolations(
      <div>
        <GameBadge game={{ state: "bye", date: null, opponent: null, home: null }} />
        <GameBadge game={upcoming} />
        <GameBadge game={{ ...upcoming, state: "live" }} />
        <GameBadge game={{ ...upcoming, state: "final" }} />
      </div>,
    );
  });

  it("puts the state in visible text, not only color", () => {
    render(<GameBadge game={{ state: "bye", date: null, opponent: null, home: null }} />);
    expect(screen.getByText("Bye week")).toBeInTheDocument();
  });

  it("renders nothing without a game", () => {
    const { container } = render(<GameBadge game={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("rosters with game status", () => {
  const rosters: Dashboard["rosters"] = [
    {
      roster_id: 1,
      team: "Cole",
      owner_id: "u1",
      players: [
        {
          player_id: "1",
          name: "Playing Today",
          position: "RB",
          team: "SF",
          status: "starter",
          slot: "RB",
          game: upcoming,
        },
        {
          player_id: "2",
          name: "Resting Receiver",
          position: "WR",
          team: "MIN",
          status: "bench",
          slot: null,
          game: { state: "bye", date: null, opponent: null, home: null },
        },
      ],
    },
  ];

  it("shows each player's game or bye and which NFL week it refers to", async () => {
    render(<RostersPanel rosters={rosters} myRosterId={1} week={6} />);
    expect(screen.getByText("Bye week")).toBeInTheDocument();
    expect(screen.getByText("Sun, Sep 20 vs CHI")).toBeInTheDocument();
    expect(screen.getByText(/NFL week 6/)).toBeInTheDocument();
    await expectNoA11yViolations(<RostersPanel rosters={rosters} myRosterId={1} week={6} />);
  });

  it("omits the week note when the week is unknown", () => {
    render(<RostersPanel rosters={rosters} myRosterId={1} />);
    expect(screen.queryByText(/NFL week/)).not.toBeInTheDocument();
  });
});

describe("kickoff time", () => {
  const withKickoff: GameInfo = { ...upcoming, kickoff: "2026-09-20T17:00:00Z" };

  it("formats the instant in the viewer's own zone, with the zone named", () => {
    const text = formatKickoff("2026-09-20T17:00:00Z");
    expect(text).toMatch(/\d{1,2}:00\s?(a.m.|p.m.|AM|PM)/i);
    expect(text).toMatch(/[A-Z]{2,5}|GMT[+-]\d+|UTC/); // a zone abbreviation, not a bare time
    expect(formatKickoff(null)).toBeNull();
    expect(formatKickoff("not a date")).toBeNull();
  });

  it("uses the localized kickoff in place of the date when it is known", () => {
    const kickoff = formatKickoff(withKickoff.kickoff);
    expect(gameLabel(withKickoff, kickoff)?.detail).toBe(`${kickoff} vs CHI`);
    expect(gameLabel(withKickoff)?.detail).toBe("Sun, Sep 20 vs CHI");
  });

  it("shows the kickoff time on the badge and has no accessibility violations", async () => {
    render(<GameBadge game={withKickoff} />);
    expect(screen.getByText(/\d:00\s?(a.m.|p.m.|AM|PM)/i)).toBeInTheDocument();
    await expectNoA11yViolations(<GameBadge game={withKickoff} />);
  });

  it("falls back to the date when the schedule has no time yet", () => {
    render(<GameBadge game={{ ...upcoming, kickoff: null }} />);
    expect(screen.getByText("Sun, Sep 20 vs CHI")).toBeInTheDocument();
  });
});
