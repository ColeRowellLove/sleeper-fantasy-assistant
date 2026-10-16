import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import GameBadge from "../components/GameBadge";
import RostersPanel from "../components/RostersPanel";
import type { Dashboard, GameInfo } from "../lib/api";
import {
  conditionsLabel,
  formatGameDate,
  formatKickoff,
  gameLabel,
  matchupDifficulty,
  matchupText,
  ordinal,
  playerUnitLabel,
  scoreText,
  situationLabel,
  spreadText,
  unitOnField,
} from "../lib/game";
import { expectNoA11yViolations } from "./a11y";

const upcoming: GameInfo = {
  state: "upcoming",
  date: "2026-09-20",
  opponent: "CHI",
  home: true,
};

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

describe("defense rank against a position", () => {
  const jax = { opponent: "JAX", rank: 3, teams: 32, points: 24.1, games: 5 };

  it("writes ordinals", () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 32].map(ordinal)).toEqual([
      "1st",
      "2nd",
      "3rd",
      "4th",
      "11th",
      "12th",
      "13th",
      "21st",
      "22nd",
      "23rd",
      "32nd",
    ]);
  });

  it("explains the rank in a full sentence", () => {
    expect(matchupText(jax, "RB")).toEqual({
      difficulty: "easy",
      word: "Easy",
      text: "3rd",
      spoken: "JAX ranks 3rd against RBs (easy matchup)",
      description:
        "JAX allows the 3rd most fantasy points to RBs of 32 teams (24.1 per game over 5 games)",
    });
    expect(matchupText({ ...jax, games: 1 }, null)?.description).toContain("over 1 game)");
    expect(matchupText(null, "RB")).toBeNull();
  });

  it("describes a team defense by the offense it faces", () => {
    const offense = {
      opponent: "CHI",
      rank: 2,
      teams: 32,
      points: 11.3,
      games: 4,
      side: "offense" as const,
    };
    expect(matchupText(offense, "DEF")).toEqual({
      difficulty: "easy",
      word: "Easy",
      text: "2nd",
      spoken: "CHI offense ranks 2nd easiest for a defense (easy matchup)",
      description:
        "CHI scores the 2nd fewest fantasy points of 32 teams (11.3 per game over 4 games)",
    });
  });

  it("shows the rank next to the opponent, readable without color", async () => {
    render(<GameBadge game={upcoming} matchup={jax} position="RB" />);
    expect(screen.getByText("3rd · Easy")).toBeInTheDocument();
    expect(screen.getByText("JAX ranks 3rd against RBs (easy matchup)")).toBeInTheDocument();
    await expectNoA11yViolations(<GameBadge game={upcoming} matchup={jax} position="RB" />);
  });

  it("names how hard a matchup is: the easiest quarter easy, the hardest tough", () => {
    const at = (rank: number) => matchupDifficulty({ ...jax, rank, teams: 32 });
    expect(at(1)).toBe("easy");
    expect(at(8)).toBe("easy");
    expect(at(9)).toBe("average");
    expect(at(24)).toBe("average");
    expect(at(25)).toBe("tough");
    expect(at(32)).toBe("tough");
    const small = (rank: number, teams: number) => matchupDifficulty({ ...jax, rank, teams });
    expect(small(7, 30)).toBe("easy"); // 30 teams: the easiest 7.5
    expect(small(8, 30)).toBe("average");
    expect(small(23, 30)).toBe("tough");
    expect(small(1, 0)).toBe("average"); // no team count: not a confident label
  });

  it("colours the chip by difficulty and always says the word", () => {
    const { container, rerender } = render(
      <GameBadge game={upcoming} matchup={jax} position="RB" />,
    );
    expect(container.querySelector(".rank-easy")).toHaveTextContent("3rd · Easy");
    rerender(<GameBadge game={upcoming} matchup={{ ...jax, rank: 28 }} position="RB" />);
    expect(container.querySelector(".rank-tough")).toHaveTextContent("28th · Tough");
    rerender(<GameBadge game={upcoming} matchup={{ ...jax, rank: 16 }} position="RB" />);
    expect(container.querySelector(".rank-average")).toHaveTextContent("16th · Average");
    const offense = {
      opponent: "CHI",
      rank: 30,
      teams: 32,
      points: 24,
      games: 4,
      side: "offense" as const,
    };
    rerender(<GameBadge game={upcoming} matchup={offense} position="DEF" />);
    expect(container.querySelector(".rank-tough")).toHaveTextContent("30th · Tough");
  });

  it("has no accessibility violations on the average and tough chips", async () => {
    await expectNoA11yViolations(
      <GameBadge game={upcoming} matchup={{ ...jax, rank: 16 }} position="RB" />,
    );
    await expectNoA11yViolations(
      <GameBadge game={upcoming} matchup={{ ...jax, rank: 30 }} position="RB" />,
    );
  });

  it("shows no rank on a bye week", () => {
    render(
      <GameBadge
        game={{ state: "bye", date: null, opponent: null, home: null }}
        matchup={jax}
        position="RB"
      />,
    );
    expect(screen.queryByText("3rd · Easy")).not.toBeInTheDocument();
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
          matchup: { opponent: "CHI", rank: 3, teams: 32, points: 21.4, games: 5 },
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
    render(<RostersPanel leagueId="1" rosters={rosters} myRosterId={1} week={6} />);
    expect(screen.getByText("Bye week")).toBeInTheDocument();
    expect(screen.getByText("Sun, Sep 20 vs CHI")).toBeInTheDocument();
    expect(screen.getByText(/NFL week 6/)).toBeInTheDocument();
    expect(screen.getByText("3rd · Easy")).toBeInTheDocument(); // the opponent's rank for his position
    expect(screen.getByText("CHI ranks 3rd against RBs (easy matchup)")).toBeInTheDocument();
    await expectNoA11yViolations(
      <RostersPanel leagueId="1" rosters={rosters} myRosterId={1} week={6} />,
    );
  });

  it("omits the week note when the week is unknown", () => {
    render(<RostersPanel leagueId="1" rosters={rosters} myRosterId={1} />);
    expect(screen.queryByText(/NFL week/)).not.toBeInTheDocument();
  });
});

describe("kickoff time", () => {
  const withKickoff: GameInfo = {
    ...upcoming,
    kickoff: "2026-09-20T17:00:00Z",
  };

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

describe("live and final game status", () => {
  const live: GameInfo = {
    state: "live",
    date: "2026-10-18",
    opponent: "DEN",
    home: false,
    team: "SEA",
    team_score: 3,
    opponent_score: 14,
    period_text: "Q2 2:24",
  };

  it("writes the score from the player's side, team first", () => {
    expect(scoreText(live)).toBe("SEA 3 - DEN 14");
    expect(
      scoreText({
        ...live,
        team: "DEN",
        opponent: "SEA",
        team_score: 14,
        opponent_score: 3,
      }),
    ).toBe("DEN 14 - SEA 3");
    expect(scoreText({ ...live, team_score: null })).toBeNull(); // no score yet: nothing invented
    expect(scoreText({ ...live, team: null })).toBeNull();
    expect(scoreText({ ...live, team_score: 0, opponent_score: 0 })).toBe("SEA 0 - DEN 0"); // 0 is a score
  });

  it("shows the clock and the score on a game in progress", () => {
    expect(gameLabel(live)).toEqual({
      state: "live",
      text: "Live",
      detail: "Q2 2:24, SEA 3 - DEN 14",
    });
    expect(gameLabel({ ...live, period_text: "Halftime" })?.detail).toBe(
      "Halftime, SEA 3 - DEN 14",
    );
  });

  it("falls back to the opponent when the live data is missing", () => {
    const bare: GameInfo = {
      state: "live",
      date: "2026-10-18",
      opponent: "DEN",
      home: false,
    };
    expect(gameLabel(bare)).toEqual({
      state: "live",
      text: "Live",
      detail: "at DEN",
    });
    expect(gameLabel({ ...bare, period_text: "Q3 10:00" })?.detail).toBe("Q3 10:00"); // clock, no score yet
  });

  it("shows the final score once a game is over", () => {
    const final: GameInfo = {
      ...live,
      state: "final",
      period_text: "Final",
      team_score: 17,
      opponent_score: 24,
    };
    expect(gameLabel(final)).toEqual({
      state: "final",
      text: "Played",
      detail: "Final, SEA 17 - DEN 24",
    });
    expect(gameLabel({ state: "final", date: null, opponent: "DEN", home: true })?.detail).toBe(
      "vs DEN",
    );
  });

  it("renders in the badge and has no accessibility violations", async () => {
    render(<GameBadge game={live} />);
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("Q2 2:24, SEA 3 - DEN 14")).toBeInTheDocument();
    await expectNoA11yViolations(<GameBadge game={live} />);
  });
});

describe("game conditions", () => {
  const outdoors: GameInfo = {
    ...upcoming,
    team: "SF",
    conditions: {
      roof: "outdoors",
      surface: "grass",
      temp: 28,
      wind: 18,
      spread: -3.5,
      total: 44.5,
    },
  };

  it("writes the spread from the team's side", () => {
    expect(spreadText("SF", -3.5)).toBe("SF -3.5");
    expect(spreadText("DAL", 3.5)).toBe("DAL +3.5");
    expect(spreadText("SF", 0)).toBe("SF pick'em");
    expect(spreadText(null, -1)).toBe("-1");
  });

  it("describes outdoor weather in words, flagging wind and cold", () => {
    expect(conditionsLabel(outdoors)).toEqual({
      setting: "28°F (freezing), wind 18 mph (windy)",
      surface: "Grass",
      line: "SF -3.5, O/U 44.5",
    });
    expect(conditionsLabel(outdoors, true)).toEqual({
      setting: "28°F (freezing), wind 18 mph (windy)",
      surface: null,
      line: null,
    });
  });

  it("says dome or closed roof instead of weather", () => {
    const dome = { ...outdoors, conditions: { roof: "dome", temp: null, wind: null } };
    expect(conditionsLabel(dome, true)?.setting).toBe("Dome");
    expect(conditionsLabel({ ...dome, conditions: { roof: "closed" } }, true)?.setting).toBe(
      "Closed roof",
    );
  });

  it("shows nothing when nothing is known, on a bye, or without a game", () => {
    expect(conditionsLabel({ ...outdoors, conditions: null })).toBeNull();
    expect(conditionsLabel({ ...outdoors, conditions: {} })).toBeNull();
    expect(conditionsLabel({ ...outdoors, state: "bye" })).toBeNull();
    expect(conditionsLabel(null)).toBeNull();
    expect(conditionsLabel({ ...outdoors, conditions: { roof: "outdoors" } }, true)?.setting).toBe(
      "Outdoors",
    );
  });

  it("is plain text on the badge and has no accessibility violations", async () => {
    render(<GameBadge game={outdoors} conditions="full" />);
    expect(
      screen.getByText("28°F (freezing), wind 18 mph (windy) · Grass · SF -3.5, O/U 44.5"),
    ).toBeInTheDocument();
    await expectNoA11yViolations(<GameBadge game={outdoors} conditions="full" />);
  });

  it("shows nothing unless asked", () => {
    render(<GameBadge game={outdoors} />);
    expect(screen.queryByText(/freezing/)).not.toBeInTheDocument();
  });
});

describe("live game situation", () => {
  const live = (over: Partial<GameInfo> = {}): GameInfo => ({
    state: "live",
    date: "2026-10-18",
    opponent: "SEA",
    home: true,
    team: "DEN",
    situation: { possession: "DEN", down_distance: "3rd & 4", ball_on: "SEA 18", red_zone: true },
    ...over,
  });

  it("says who has the ball, the down and where, in words", () => {
    expect(situationLabel(live())).toEqual({
      text: "DEN have the ball · 3rd & 4 · at SEA 18",
      spot: "Ball on SEA 18",
      redZone: true,
    });
    expect(situationLabel(live({ situation: { ball_on: "SEA 40" } }))).toEqual({
      text: "Ball on SEA 40",
      spot: "Ball on SEA 40",
      redZone: false,
    });
    expect(situationLabel(live({ situation: { red_zone: true } }))).toEqual({
      text: null,
      spot: null,
      redZone: true,
    });
  });

  it("shows nothing at halftime or the end of a quarter, whatever ESPN last reported", () => {
    expect(situationLabel(live({ period_text: "Halftime" }))).toBeNull();
    expect(situationLabel(live({ period_text: "End of 2nd" }))).toBeNull();
    expect(unitOnField(live({ period_text: "Halftime" }), "DEN")).toBeNull();
    expect(playerUnitLabel(live({ period_text: "Halftime" }), "QB")).toBeNull();
    expect(situationLabel(live({ period_text: "Q3 4:12" }))?.redZone).toBe(true);
  });

  it("says nothing unless the game is live and ESPN reported something", () => {
    expect(situationLabel(live({ state: "final" }))).toBeNull();
    expect(situationLabel(live({ state: "upcoming" }))).toBeNull();
    expect(situationLabel(live({ situation: null }))).toBeNull();
    expect(situationLabel(live({ situation: {} }))).toBeNull();
    expect(situationLabel(live({ situation: { red_zone: false } }))).toBeNull();
    expect(situationLabel(null)).toBeNull();
  });

  it("knows which unit is on the field: the offense with the ball, the defense without it", () => {
    expect(unitOnField(live(), "DEN")).toBe("offense");
    expect(unitOnField(live(), "SEA")).toBe("defense");
    expect(unitOnField(live({ situation: { ball_on: "SEA 40" } }), "DEN")).toBeNull(); // ball unknown
    expect(unitOnField(live({ state: "final" }), "DEN")).toBeNull();
    expect(unitOnField(live(), null)).toBeNull();
  });

  it("labels a player whose unit is on the field and no one else", () => {
    expect(playerUnitLabel(live(), "QB")).toBe("Offense on field");
    expect(playerUnitLabel(live(), "WR")).toBe("Offense on field");
    expect(playerUnitLabel(live(), "DEF")).toBeNull(); // his defense is on the bench
    expect(playerUnitLabel(live(), "K")).toBeNull();
    const defending = live({ team: "SEA" });
    expect(playerUnitLabel(defending, "DEF")).toBe("Defense on field");
    expect(playerUnitLabel(defending, "RB")).toBeNull(); // his offense is on the bench
    expect(playerUnitLabel(defending, "LB")).toBe("Defense on field"); // individual defenders
    expect(playerUnitLabel(live({ state: "upcoming" }), "QB")).toBeNull();
  });

  it("puts the full line on the game and only the unit, red zone and spot on a player's row", async () => {
    const { rerender } = render(<GameBadge game={live()} position="RB" conditions="full" />);
    expect(screen.getByText("Offense on field")).toBeInTheDocument();
    expect(screen.getByText("Red zone")).toBeInTheDocument();
    expect(screen.getByText("DEN have the ball · 3rd & 4 · at SEA 18")).toBeInTheDocument();
    rerender(<GameBadge game={live()} position="RB" conditions="compact" />);
    expect(screen.getByText("Ball on SEA 18")).toBeInTheDocument();
    expect(screen.queryByText(/have the ball/)).not.toBeInTheDocument();
    rerender(<GameBadge game={live()} position="RB" />);
    expect(screen.getByText("Offense on field")).toBeInTheDocument();
    expect(screen.getByText("Red zone")).toBeInTheDocument();
    expect(screen.queryByText(/Ball on|have the ball/)).not.toBeInTheDocument();
    await expectNoA11yViolations(<GameBadge game={live()} position="RB" conditions="full" />);
  });

  it("shows no red zone badge outside the red zone, and nothing for a game that is not live", () => {
    const { rerender } = render(
      <GameBadge
        game={live({ situation: { possession: "DEN", red_zone: false } })}
        position="QB"
      />,
    );
    expect(screen.queryByText("Red zone")).not.toBeInTheDocument();
    expect(screen.getByText("Offense on field")).toBeInTheDocument();
    rerender(<GameBadge game={live({ state: "final" })} position="QB" />);
    expect(screen.queryByText("Offense on field")).not.toBeInTheDocument();
    expect(screen.queryByText(/have the ball/)).not.toBeInTheDocument();
  });
});
