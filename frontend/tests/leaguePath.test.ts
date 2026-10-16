import { describe, expect, it } from "vitest";
import { leaguePath } from "../lib/league";

describe("leaguePath", () => {
  it("builds an encoded league URL", () => {
    expect(leaguePath("123/4")).toBe("/league/123%2F4");
  });

  it("appends a query string when given one", () => {
    expect(leaguePath("123", "?tab=lineups&week=6")).toBe("/league/123?tab=lineups&week=6");
  });
});
