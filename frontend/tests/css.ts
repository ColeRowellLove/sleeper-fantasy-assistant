import { readFileSync } from "node:fs";

/** The stylesheets in the order app/layout.tsx imports them, as one string (the cascade order). */
const FILES = [
  "tokens",
  "shell",
  "forms",
  "league",
  "rosters",
  "lineups",
  "widgets",
  "settings",
];

export function readAllCss(): string {
  return FILES.map((name) =>
    readFileSync(new URL(`../app/styles/${name}.css`, import.meta.url), "utf-8"),
  ).join("\n");
}

export const STYLE_FILES = FILES;
