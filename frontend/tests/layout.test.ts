// @vitest-environment node
import { describe, expect, it } from "vitest";

import { readdirSync } from "node:fs";

import { STYLE_FILES, readAllCss } from "./css";

// jsdom cannot lay anything out, so this guards a CSS trap found on a real phone: .visually-hidden is
// absolutely positioned, so inside a scrollable row that is not itself positioned it escapes the
// row's clipping and widens the whole page.
const css = readAllCss();

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

describe("stylesheets", () => {
  it("lists every file in app/styles, so the tests read the whole cascade", () => {
    const onDisk = readdirSync(new URL("../app/styles", import.meta.url))
      .map((f) => f.replace(/\.css$/, ""))
      .sort();
    expect([...STYLE_FILES].sort()).toEqual(onDisk);
  });
});

describe("player pop-up", () => {
  // table.players sets a 46rem minimum for the Players tab; inside the dialog it must not apply or
  // the dialog's content grows wider than the dialog and the values fall off the right edge
  it("keeps its tables from inheriting the Players tab's minimum width", () => {
    const players = css.indexOf("\ntable.players {");
    const override = css.indexOf("\ntable.players.pd-table {");
    expect(players).toBeGreaterThan(-1);
    expect(override).toBeGreaterThan(players);
    expect(rule("table.players.pd-table")).toContain("min-width: 0");
  });

  it("lets the dialog body shrink to its container", () => {
    expect(rule(".player-dialog-body")).toContain("minmax(0, 1fr)");
  });
});

describe("Players list rows", () => {
  // a game badge, a long team name or an injury must not make one row taller than the rest
  it("keeps one fixed height per row and keeps each line from wrapping", () => {
    expect(rule(".players-list tbody tr")).toContain("height:");
    expect(rule(".player-meta")).toContain("white-space: nowrap");
    expect(rule(".player-meta")).toContain("min-height");
    expect(rule(".status-owned")).toContain("white-space: nowrap");
  });

  it("keeps the game and injury badges on one line inside a row", () => {
    expect(rule(".player-meta .game,\n.player-meta .injury")).toContain("flex-wrap: nowrap");
  });

  it("does not apply the fixed row height to the pop-up's tables", () => {
    expect(rule(".players tbody tr")).toBe("");
  });
});

describe("roster row columns", () => {
  // each trailing column has a fixed width so numbers, slot and position line up from row to row
  it("fixes the width of the points, projection, slot and position columns", () => {
    for (const selector of [".player-proj", ".slot", ".player-chip"]) {
      expect(rule(selector)).toMatch(/flex: 0 0 [\d.]+rem/);
    }
  });
});

describe("compact tables", () => {
  it("keeps the player tables narrow enough for a laptop and a phone's sideways scroll", () => {
    expect(rule("table.players")).toContain("min-width: 36rem");
    expect(rule(".players .player-cell")).toContain("min-width: 16rem");
    expect(rule(".players-list tbody tr")).toContain("height: 4rem");
  });

  it("uses tighter row padding in the standings and the lineups", () => {
    expect(css).toContain("padding: 0.6rem 0.85rem;");
    expect(rule(".h2h th,\n.h2h td")).toContain("padding: 0.4rem 0.5rem");
  });
});
