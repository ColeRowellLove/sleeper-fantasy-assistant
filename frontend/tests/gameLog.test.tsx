import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import GameLog from "../components/GameLog";
import type { PlayerDetail } from "../lib/api";
import { gameLogRows, opponentText, rankTone } from "../lib/gameLog";
import { expectNoA11yViolations } from "./a11y";

const matchup = (rank: number) => ({ opponent: "X", rank, teams: 32, points: 20, games: 5 });

const detail: PlayerDetail = {
  player_id: "1",
  name: "Jayden Daniels",
  position: "QB",
  team: "WAS",
  season: { points: 50, games: 2, average: 25, rank: 4 },
  weeks: [
    {
      week: 1,
      team: "WAS",
      opponent: "PHI",
      home: false,
      points: 17.7,
      rank: 14,
      stats: { pass_yd: 164 },
      final: true,
    },
    {
      week: 2,
      team: "WAS",
      opponent: "DAL",
      home: true,
      points: 32.3,
      rank: 2,
      stats: { pass_yd: 199 },
      final: true,
    },
  ],
  schedule: [
    { week: 1, opponent: "PHI", home: false, matchup: matchup(3) },
    { week: 2, opponent: "DAL", home: true, matchup: matchup(16) },
    { week: 3, bye: true },
    { week: 4, opponent: "SEA", home: true, matchup: matchup(30) },
  ],
  past_seasons: [],
};

describe("rankTone", () => {
  it("tints the top 12 green, 13 to 24 yellow and the rest red, nothing without a rank", () => {
    expect(rankTone(1)).toBe("great");
    expect(rankTone(12)).toBe("great");
    expect(rankTone(13)).toBe("ok");
    expect(rankTone(24)).toBe("ok");
    expect(rankTone(25)).toBe("poor");
    expect(rankTone(null)).toBeNull();
  });
});

describe("gameLogRows", () => {
  it("lists every week of the schedule: played, still to come and bye", () => {
    const rows = gameLogRows(detail);
    expect(rows.map((r) => [r.week, r.kind])).toEqual([
      [1, "played"],
      [2, "played"],
      [3, "bye"],
      [4, "upcoming"],
    ]);
    expect(rows[0]).toMatchObject({ points: 17.7, rank: 14, difficulty: "easy" });
    expect(rows[3]).toMatchObject({ points: null, difficulty: "tough", opponent: "SEA" });
  });

  it("falls back to the weeks he played without a schedule", () => {
    const rows = gameLogRows({ ...detail, schedule: undefined });
    expect(rows.map((r) => r.week)).toEqual([1, 2]);
  });

  it("writes an away game with an @, like Sleeper", () => {
    expect(opponentText({ opponent: "PHI", home: false })).toBe("@PHI");
    expect(opponentText({ opponent: "DAL", home: true })).toBe("DAL");
    expect(opponentText({ opponent: null, home: null })).toBeNull();
  });
});

describe("GameLog", () => {
  const columns = [{ key: "pass_yd", label: "Pass yds" }];
  const totals = { pass_yd: 363 };
  const ui = <GameLog detail={detail} columns={columns} totals={totals} />;

  it("shows every week, colours the opponent and the rank, and greys the bye", async () => {
    render(ui);
    const table = screen.getByRole("table", { name: /every week of the season/i });
    expect(within(table).getAllByRole("row")).toHaveLength(1 + 4 + 1); // header, four weeks, total
    expect(within(table).getByText("@PHI").closest(".gl-opponent")).toHaveClass("diff-easy");
    expect(within(table).getByText("SEA").closest(".gl-opponent")).toHaveClass("diff-tough");
    expect(within(table).getByText("BYE")).toBeInTheDocument();
    expect(within(table).getByText("14").closest("td")).toHaveClass("tone-ok");
    const week2 = within(table).getByRole("row", { name: /^2 DAL/ });
    expect(within(week2).getAllByRole("cell")[2]).toHaveClass("tone-great"); // rank 2
    // the colour is never alone: the opponent has its difficulty in words for a screen reader
    expect(within(table).getAllByText(/\(easy matchup\)/).length).toBeGreaterThan(0);
    await expectNoA11yViolations(ui);
  });

  it("has a keyboard-reachable scroll area", () => {
    render(ui);
    expect(screen.getByRole("region", { name: /game log/i })).toHaveAttribute("tabindex", "0");
  });
});
