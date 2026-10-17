import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TopPerformers from "../components/TopPerformers";
import type { GameCard, GamePlayer, Games } from "../lib/api";
import { topPerformers } from "../lib/topPerformers";
import { expectNoA11yViolations } from "./a11y";

const player = (id: string, name: string, points: number | null, extra: Partial<GamePlayer> = {}) =>
  ({
    player_id: id,
    name,
    position: "WR",
    team: "SEA",
    points,
    stats: { rec: 12, rec_yd: 134 },
    ...extra,
  }) as GamePlayer;

const card = (id: string, players: GamePlayer[], scored = true): GameCard =>
  ({
    game_id: id,
    week: 6,
    home: "DEN",
    away: "SEA",
    game: {
      state: "final",
      date: "2026-10-15",
      opponent: "SEA",
      home: true,
      team_score: scored ? 17 : null,
      opponent_score: scored ? 14 : null,
    },
    players,
  }) as GameCard;

const data: Games = {
  league_id: "L",
  week: 6,
  current_week: 6,
  weeks: [6],
  games: [
    card("g1", [
      player("1", "J. Smith-Njigba", 26.4),
      player("2", "Projected Guy", 30, { projected: true }),
      player("3", "Zero Guy", 0),
      player("4", "No Points", null),
    ]),
    card("g2", [player("5", "R. Harvey", 18.1, { position: "RB", team: "DEN" })], false),
  ],
};

describe("topPerformers", () => {
  it("lists only players who have played, best first, with the game score and main stats", () => {
    const rows = topPerformers(data.games);
    expect(rows.map((r) => r.player.name)).toEqual(["J. Smith-Njigba", "R. Harvey"]);
    expect(rows[0].game).toBe("SEA 14 - DEN 17");
    expect(rows[1].game).toBeNull(); // no score stored: nothing is claimed
    expect(rows[0].stats.map((s) => s.value)).toContain("134");
    expect(rows[0].stats.length).toBeLessThanOrEqual(3);
  });

  it("stops at the limit", () => {
    expect(topPerformers(data.games, 1)).toHaveLength(1);
  });
});

describe("TopPerformers", () => {
  it("shows a card per performer in a labelled, keyboard-scrollable region", () => {
    render(<TopPerformers data={data} />);
    const region = screen.getByRole("region", { name: /scrolls sideways/i });
    expect(region).toHaveAttribute("tabindex", "0");
    const cards = within(region).getAllByRole("listitem");
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("26.4")).toBeInTheDocument();
  });

  it("renders nothing when nobody has played, and has no accessibility violations", async () => {
    const { container } = render(<TopPerformers data={{ ...data, games: [] }} />);
    expect(container).toBeEmptyDOMElement();
    await expectNoA11yViolations(<TopPerformers data={data} />);
  });
});
