import { describe, expect, it } from "vitest";

import { boxMineIds, boxPath, hasBoxScore, parseBox } from "../lib/boxScore";

describe("box score links", () => {
  it("round-trips a game", () => {
    const path = boxPath("9", 7, "WAS", "KC");
    expect(path).toBe("/league/9?tab=games&week=7&box=WAS-KC");
    expect(parseBox("WAS-KC")).toEqual({ away: "WAS", home: "KC" });
  });
  it("ignores anything that is not two team codes", () => {
    for (const bad of [undefined, "", "wasKC", "WAS-", "../x", "WAS-KC-X"]) {
      expect(parseBox(bad)).toBeNull();
    }
  });
});

describe("box score helpers", () => {
  const games = [
    {
      away: "WAS",
      home: "KC",
      players: [
        { player_id: "a", owner_roster_id: 2 },
        { player_id: "b", owner_roster_id: 3 },
        { player_id: "c", owner_roster_id: null },
      ],
    },
    { away: "SF", home: "LAR", players: [{ player_id: "d", owner_roster_id: 2 }] },
  ];
  it("marks only your players of this game", () => {
    expect(boxMineIds(games, { away: "WAS", home: "KC" }, 2)).toEqual(["a"]);
    expect(boxMineIds(games, { away: "WAS", home: "KC" }, null)).toEqual([]);
    expect(boxMineIds([], { away: "WAS", home: "KC" }, 2)).toEqual([]);
  });
  it("only offers a box score once the game has started", () => {
    expect(hasBoxScore("live")).toBe(true);
    expect(hasBoxScore("final")).toBe(true);
    for (const state of ["upcoming", "bye", undefined]) expect(hasBoxScore(state)).toBe(false);
  });
});
