import { describe, expect, it } from "vitest";

import { POSITIONS, positionClass, positionName } from "../lib/positions";

describe("positions", () => {
  it("gives every fantasy position its own color class", () => {
    const classes = POSITIONS.map((p) => positionClass(p));
    expect(classes).toEqual(["pos-qb", "pos-rb", "pos-wr", "pos-te", "pos-k", "pos-def"]);
    expect(new Set(classes).size).toBe(POSITIONS.length);
  });

  it("is case-insensitive and neutral for unknown or missing positions", () => {
    expect(positionClass("wr")).toBe("pos-wr");
    expect(positionClass("LB")).toBe("pos-na");
    expect(positionClass(null)).toBe("pos-na");
    expect(positionClass(undefined)).toBe("pos-na");
  });

  it("has a readable name for each position", () => {
    expect(positionName("DEF")).toBe("Defense");
    expect(positionName("TE")).toBe("Tight end");
  });
});
