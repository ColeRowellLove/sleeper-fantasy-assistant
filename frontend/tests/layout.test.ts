// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// jsdom cannot lay anything out, so this guards a CSS trap found on a real phone: .visually-hidden is
// absolutely positioned, so inside a scrollable row that is not itself positioned it escapes the
// row's clipping and widens the whole page.
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf-8");

function rule(selector: string): string {
  const match = css.match(new RegExp(`(?:^|\n)${selector.replace(".", "\.")} \{([^}]*)\}`));
  return match ? match[1] : "";
}

describe("scrollable rows containing screen-reader text", () => {
  it.each([".week-chips", ".tabs"])("%s clips its own hidden text", (selector) => {
    const body = rule(selector);
    expect(body).toContain("overflow-x: auto");
    expect(body).toContain("position: relative");
  });
});
