import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import GameLine from "../components/GameLine";
import type { GameInfo } from "../lib/api";
import { abbreviateName, gameLineParts, weatherIcon } from "../lib/game";
import { expectNoA11yViolations } from "./a11y";

const game = (over: Partial<GameInfo>): GameInfo => ({
  state: "upcoming",
  date: "2026-10-18",
  opponent: "SF",
  home: false,
  team: "WAS",
  ...over,
});

describe("abbreviateName", () => {
  it("keeps the first initial and the rest, and leaves defenses and single names whole", () => {
    expect(abbreviateName("Jayden Daniels")).toBe("J. Daniels");
    expect(abbreviateName("Amon-Ra St. Brown")).toBe("A. St. Brown");
    expect(abbreviateName("LAR defense")).toBe("LAR defense");
    expect(abbreviateName("Madonna")).toBe("Madonna");
  });
});

describe("gameLineParts", () => {
  it("words an upcoming game as the time then @ or vs the opponent", () => {
    expect(gameLineParts(game({}), "Mon 5:15 PM")).toEqual({
      state: "upcoming",
      time: "Mon 5:15 PM",
      score: null,
      versus: "@",
      opponent: "SF",
    });
    expect(gameLineParts(game({ home: true }))?.versus).toBe("vs");
  });

  it("shows the clock and score of a live game and W or L for a finished one", () => {
    const live = game({
      state: "live",
      period_text: "Q2 2:24",
      team_score: 14,
      opponent_score: 17,
    });
    expect(gameLineParts(live)).toMatchObject({ time: "Q2 2:24", score: "14-17" });
    const won = game({ state: "final", team_score: 24, opponent_score: 20 });
    expect(gameLineParts(won)).toMatchObject({ time: "Final", score: "W 24-20" });
    expect(gameLineParts({ ...won, team_score: 10 })?.score).toBe("L 10-20");
  });

  it("says bye week without an opponent, and nothing without a game", () => {
    expect(gameLineParts(game({ state: "bye" }))).toMatchObject({
      time: "Bye week",
      opponent: null,
    });
    expect(gameLineParts(null)).toBeNull();
  });
});

describe("weatherIcon", () => {
  it("shows an icon only for notable weather", () => {
    expect(weatherIcon(game({ conditions: { roof: "outdoors", temp: 64, wind: 5 } }))).toBeNull();
    expect(weatherIcon(game({ conditions: { roof: "outdoors", temp: 20, wind: 5 } }))?.label).toBe(
      "Freezing",
    );
    expect(weatherIcon(game({ conditions: { roof: "dome" } }))?.label).toBe("Dome");
    expect(weatherIcon(game({ state: "bye", conditions: { roof: "dome" } }))).toBeNull();
  });
});

describe("GameLine", () => {
  const matchup = { opponent: "SF", rank: 3, teams: 32, points: 24, games: 6 };

  it("shows the opponent coloured by difficulty with the word for screen readers", async () => {
    const ui = <GameLine game={game({})} matchup={matchup} position="QB" />;
    const { container } = render(ui);
    const opponent = screen.getByText("SF");
    expect(opponent).toHaveClass("diff-easy");
    expect(container.textContent).toContain("easy matchup"); // the spoken form, not only colour
    await expectNoA11yViolations(ui);
  });

  it("shows a live game with its score and nothing for a missing game", () => {
    render(
      <GameLine
        game={game({ state: "live", period_text: "Q3 0:41", team_score: 10, opponent_score: 7 })}
      />,
    );
    expect(screen.getByText("Q3 0:41")).toBeInTheDocument();
    expect(screen.getByText("10-7")).toBeInTheDocument();
    const { container } = render(<GameLine game={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
