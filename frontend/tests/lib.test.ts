import { describe, expect, it } from "vitest";
import { leaguePath } from "../lib";

describe("leaguePath", () => {
  it("builds an encoded league URL", () => {
    expect(leaguePath("123/4")).toBe("/league/123%2F4");
  });
});
