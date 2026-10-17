import { describe, expect, it } from "vitest";

import type { GameInfo } from "../lib/api";
import { gameCardLabel } from "../lib/game";

const base: GameInfo = {
  state: "upcoming",
  date: "2026-10-18",
  opponent: "ARI",
  home: true,
  team: "WAS",
};

describe("gameCardLabel", () => {
  it("gives every state the same shape: the state and at most one short line", () => {
    expect(gameCardLabel(base, "Sun 5:31 PM")).toEqual({
      state: "upcoming",
      text: "Upcoming",
      detail: "Sun 5:31 PM",
    });
    expect(
      gameCardLabel({
        ...base,
        state: "live",
        period_text: "Q2 2:24",
        team_score: 7,
        opponent_score: 3,
      }),
    ).toEqual({ state: "live", text: "Live", detail: "Q2 2:24" });
    expect(gameCardLabel({ ...base, state: "final", team_score: 24, opponent_score: 21 })).toEqual({
      state: "final",
      text: "Final",
      detail: null,
    });
  });

  it("never repeats the opponent or the score", () => {
    const label = gameCardLabel({ ...base, state: "final", team_score: 24, opponent_score: 21 });
    expect(JSON.stringify(label)).not.toMatch(/ARI|24/);
  });

  it("handles a bye and a missing game", () => {
    expect(gameCardLabel({ ...base, state: "bye" })?.text).toBe("Bye week");
    expect(gameCardLabel(null)).toBeNull();
  });
});
