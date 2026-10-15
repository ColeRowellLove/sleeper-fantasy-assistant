// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// jsdom cannot lay anything out, so this guards a CSS trap found on a real phone: .visually-hidden is
// absolutely positioned, so inside a scrollable row that is not itself positioned it escapes the
// row's clipping and widens the whole page.
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf-8");

function rule(selector: string): string {
  // plain string search instead of building a regex from the selector (no escaping to get wrong)
  const start = css.indexOf(`
${selector} {`);
  if (start === -1) return "";
  const open = css.indexOf("{", start);
  return css.slice(open + 1, css.indexOf("}", open));
}

describe("scrollable rows containing screen-reader text", () => {
  it.each([".week-chips", ".tabs"])("%s clips its own hidden text", (selector) => {
    const body = rule(selector);
    expect(body).toContain("overflow-x: auto");
    expect(body).toContain("position: relative");
  });
});

describe("settings rows", () => {
  // the global `dl` rule is a two-column grid; without display: block each row's div became a grid
  // item and the rows ran sideways out of their card
  it(".setting-rows opts out of the global dl grid", () => {
    expect(rule("dl")).toContain("display: grid");
    expect(rule(".setting-rows")).toContain("display: block");
  });
});
