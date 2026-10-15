// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// jsdom cannot compute CSS, so axe never checks palette contrast. This reads the real tokens from
// globals.css and checks WCAG AA (4.5:1 for normal text) for both themes.
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf-8");

function block(source: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const m of source.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) tokens[m[1]] = m[2];
  return tokens;
}

const darkBlock = css.slice(0, css.indexOf("@media (prefers-color-scheme: light)"));
const lightStart = css.indexOf("@media (prefers-color-scheme: light)");
const lightBlock = css.slice(lightStart, css.indexOf("* {", lightStart));
const dark = block(darkBlock);
const light = { ...dark, ...block(lightBlock) };

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

/** A color at the given opacity over a surface (the chip and badge tints in globals.css). */
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

  it("muted text stays readable on the lineups bench row tint (7% of the bench role color)", () => {
    const tint = chipBackgroundAt(t["role-bench"], t.surface, 0.07);
    expect(ratio(rgb(t.muted), tint)).toBeGreaterThanOrEqual(4.5);
    expect(ratio(rgb(t.text), tint)).toBeGreaterThanOrEqual(7);
  });

  it("focus ring and error color stand out from the page", () => {
    expect(ratio(rgb(t.focus), rgb(t.bg))).toBeGreaterThanOrEqual(3);
    expect(ratio(rgb(t.danger), rgb(t.surface))).toBeGreaterThanOrEqual(4.5);
  });
});
