import { describe, expect, it } from "vitest";

import { boxPath, parseBox } from "../lib/boxScore";

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
