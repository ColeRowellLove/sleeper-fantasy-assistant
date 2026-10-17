import { describe, expect, it } from "vitest";

import { NONE, count, fixed, fractionPercent, percent, percentWhole } from "../lib/format";

describe("number formats", () => {
  it("writes a missing number as a dash, never zero", () => {
    for (const f of [fixed, percent, percentWhole, fractionPercent, count]) {
      expect(f(null)).toBe(NONE);
      expect(f(undefined)).toBe(NONE);
    }
    expect(fixed(0)).toBe("0.0"); // a real zero is still a number
  });

  it("writes the numbers the way the screens show them", () => {
    expect(fixed(13.54)).toBe("13.5");
    expect(fixed(13.5, 2)).toBe("13.50");
    expect(percent(88)).toBe("88.0%");
    expect(percentWhole(64.4)).toBe("64%");
    expect(fractionPercent(0.52)).toBe("52.0%");
    expect(count(1204)).toBe("1,204");
  });
});
