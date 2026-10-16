// @vitest-environment node
import { describe, expect, it } from "vitest";

import { readAllCss } from "./css";

// jsdom cannot compute CSS, so axe never checks palette contrast. This reads the real tokens from
// the stylesheets and checks WCAG AA (4.5:1 for normal text) for both themes.
const css = readAllCss();

function block(source: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const m of source.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) tokens[m[1]] = m[2];
  return tokens;
}

/** The text between a selector's "{" and its closing "}" (the token blocks have no nesting). */
function sliceBlock(selector: string): string {
  const start = css.indexOf(selector);
  if (start === -1) throw new Error(`selector not found in the stylesheets: ${selector}`);
  const open = css.indexOf("{", start);
  return css.slice(open + 1, css.indexOf("}", open));
}

const darkBlock = css.slice(0, css.indexOf("@media (prefers-color-scheme: light)"));
// two copies of the light tokens: for devices that prefer light, and for an explicit toggle choice
const lightFromMedia = block(sliceBlock(':root:not([data-theme="dark"]) {'));
const lightFromToggle = block(sliceBlock(':root[data-theme="light"] {'));
const dark = block(darkBlock);
const light = { ...dark, ...lightFromToggle };

function rgb(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [number, number, number];
}

function luminance([r, g, b]: [number, number, number]): number {
  const lin = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function ratio(a: [number, number, number], b: [number, number, number]): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** A color at the given opacity over a surface (the chip and badge tints in the stylesheets). */
function chipBackgroundAt(color: string, surface: string, alpha: number): [number, number, number] {
  const p = rgb(color);
  const s = rgb(surface);
  return p.map((v, i) => v * alpha + s[i] * (1 - alpha)) as [number, number, number];
}

/** Position chip background: the position color at 16% over the surface (see .chip). */
function chipBackground(pos: string, surface: string): [number, number, number] {
  return chipBackgroundAt(pos, surface, 0.16);
}

const themes = { dark, light } as const;

describe("theme token copies", () => {
  it("keeps the device-preference light tokens identical to the toggle's light tokens", () => {
    expect(Object.keys(lightFromToggle).length).toBeGreaterThan(10);
    expect(lightFromMedia).toEqual(lightFromToggle);
  });
});

describe.each(Object.entries(themes))("%s theme contrast", (_name, t) => {
  it.each(["qb", "rb", "wr", "te", "k", "def"])("%s chip text is AA on its tinted chip", (pos) => {
    const onSurface = ratio(rgb(t[pos]), chipBackground(t[pos], t.surface));
    const onPage = ratio(rgb(t[pos]), chipBackground(t[pos], t.bg));
    expect(onSurface).toBeGreaterThanOrEqual(4.5);
    expect(onPage).toBeGreaterThanOrEqual(4.5);
  });

  it("body and muted text are readable on the page and on cards", () => {
    expect(ratio(rgb(t.text), rgb(t.bg))).toBeGreaterThanOrEqual(7);
    expect(ratio(rgb(t.muted), rgb(t.bg))).toBeGreaterThanOrEqual(4.5);
    expect(ratio(rgb(t.muted), rgb(t.surface))).toBeGreaterThanOrEqual(4.5);
    expect(ratio(rgb(t.muted), rgb(t["surface-2"]))).toBeGreaterThanOrEqual(4.5);
  });

  it("primary button text is readable", () => {
    expect(ratio(rgb(t["on-accent"]), rgb(t.accent))).toBeGreaterThanOrEqual(4.5);
  });

  it("roster role colors are readable on cards", () => {
    for (const role of ["role-bench", "role-ir", "role-taxi", "role-starter"]) {
      expect(ratio(rgb(t[role]), rgb(t.surface))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("count badge text stays readable on its role tint (18% of the role color)", () => {
    for (const role of ["role-bench", "role-ir", "role-taxi", "role-starter"]) {
      const tint = chipBackgroundAt(t[role], t.surface, 0.18);
      expect(ratio(rgb(t.text), tint)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("game status badge text is readable on its tint, on cards and on the page", () => {
    for (const token of ["game-bye", "game-live"]) {
      expect(ratio(rgb(t[token]), chipBackgroundAt(t[token], t.surface, 0.16))).toBeGreaterThanOrEqual(4.5);
      expect(ratio(rgb(t[token]), chipBackgroundAt(t[token], t.bg, 0.16))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("lineup row tints (bench 7%, IR and taxi 8% of their role color) keep text readable", () => {
    for (const [role, alpha] of [["role-bench", 0.07], ["role-ir", 0.08], ["role-taxi", 0.08]] as const) {
      const tint = chipBackgroundAt(t[role], t.surface, alpha);
      expect(ratio(rgb(t.muted), tint)).toBeGreaterThanOrEqual(4.5);
      expect(ratio(rgb(t.text), tint)).toBeGreaterThanOrEqual(7);
    }
  });

  it("the IR and taxi slot labels are readable on their row tints", () => {
    for (const role of ["role-ir", "role-taxi"]) {
      const tint = chipBackgroundAt(t[role], t.surface, 0.08);
      expect(ratio(rgb(t[role]), tint)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("injury badge text is readable on its tint, on cards and on the page", () => {
    for (const token of ["injury-out", "injury-doubtful", "injury-questionable"]) {
      expect(ratio(rgb(t[token]), chipBackgroundAt(t[token], t.surface, 0.16))).toBeGreaterThanOrEqual(4.5);
      expect(ratio(rgb(t[token]), chipBackgroundAt(t[token], t.bg, 0.16))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("focus ring and error color stand out from the page", () => {
    expect(ratio(rgb(t.focus), rgb(t.bg))).toBeGreaterThanOrEqual(3);
    expect(ratio(rgb(t.danger), rgb(t.surface))).toBeGreaterThanOrEqual(4.5);
  });
});

// the win chance bar is a graphic, so it needs 3:1 (WCAG non-text contrast) for each segment
// against the card it sits on and against the other segment, in both themes
describe.each(Object.entries(themes))("%s theme win chance bar", (_name, t) => {
  it("keeps both segments visible against the card and against each other", () => {
    const card = rgb(t.surface);
    expect(ratio(rgb(t.accent), card)).toBeGreaterThanOrEqual(3);
    expect(ratio(rgb(t.muted), card)).toBeGreaterThanOrEqual(3);
    expect(ratio(rgb(t.accent), rgb(t.muted))).toBeGreaterThanOrEqual(1.5); // told apart by position too
  });
});
