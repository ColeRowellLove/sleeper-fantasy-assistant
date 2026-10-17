import { describe, expect, it } from "vitest";

import { nextSort } from "../lib/sort";

describe("nextSort", () => {
  const asc = (k: string) => k === "name";
  it("flips the active column", () => {
    expect(nextSort({ key: "name", direction: "asc" }, "name", asc)).toEqual({
      key: "name",
      direction: "desc",
    });
  });
  it("starts another column at its natural order", () => {
    expect(nextSort({ key: "name", direction: "desc" }, "name2", asc).direction).toBe("desc");
    expect(nextSort({ key: "x", direction: "desc" }, "name", asc).direction).toBe("asc");
  });
});
