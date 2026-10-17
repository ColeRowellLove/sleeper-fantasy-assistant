// Screenshots and layout checks for PRs. Expects `npm run build` first and, for the league pages,
// the API running on API_URL (default http://localhost:8000) with the sample league loaded
// (`make preview-data` then `make dev-api`). Without the API only the home page is shot.
//
// usage: npm run screenshots       writes ./screenshots/<page>-<viewport>-<theme>.png (git-ignored)
// Exits 1 when a layout check fails at phone or desktop width.
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";

const PORT = 3123;
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const LEAGUE = "100001"; // the sample league (backend/src/sleeper_assistant/sample_league.py)
const PAGES = [
  { name: "home", path: "/" },
  ...[
    "rosters",
    "startsit",
    "lineups",
    "games",
    "players",
    "waiver",
    "rankings",
    "teams&team=SF",
    "standings",
    "settings",
    "alerts",
  ].map((tab) => ({ name: tab.split("&")[0], path: `/league/${LEAGUE}?tab=${tab}`, league: true })),
];
const VIEWPORTS = [
  { name: "mobile", width: 390, height: 844 },
  { name: "desktop", width: 1280, height: 800 },
];
const THEMES = ["light", "dark"];
const SHOT_HEIGHT = 2000; // px: pictures show the top of a page, so a long list stays readable
// Known problems at phone width. The list may only shrink: a new problem fails the run, and so
// does a listed one that has been fixed (delete its entry). Keys are "<page>@<viewport>:<kind>".
const baseline = JSON.parse(await readFile("scripts/layout-baseline.json", "utf8"));

const apiUp = await fetch(`${API_URL}/health`).then(
  (r) => r.ok,
  () => false,
);
if (!apiUp) {
  // in CI a missing API must fail the run, or a green check would mean only the home page was looked at
  if (process.env.CI) throw new Error(`API not reachable at ${API_URL}`);
  console.warn(`API not reachable at ${API_URL}: league pages are skipped`);
}

// Fail loudly instead of screenshotting a stale server that is already on the port.
const alreadyUp = await fetch(`http://localhost:${PORT}/`).then(
  () => true,
  () => false,
);
if (alreadyUp) throw new Error(`port ${PORT} is already in use; stop that server first`);

// Run next directly (no shell) so server.kill() really stops it, including on Windows.
const server = spawn(
  process.execPath,
  ["node_modules/next/dist/bin/next", "start", "-p", String(PORT)],
  { stdio: "ignore", env: { ...process.env, API_URL } },
);

async function waitForServer() {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://localhost:${PORT}/`);
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("server did not start");
}

/** What is wrong with the page's layout at this width, as short sentences. */
async function layoutProblems(page) {
  return page.evaluate(() => {
    const problems = [];
    const root = document.documentElement;
    if (root.scrollWidth > window.innerWidth + 1) {
      problems.push({
        kind: "scrolls-sideways",
        text: `the page scrolls sideways (${root.scrollWidth}px wide in ${window.innerWidth}px)`,
      });
    }
    // a name is squeezed when it is cut off ("Jayd…") or wraps onto more than two lines
    for (const el of document.querySelectorAll(".player-name, .cell-name")) {
      const box = el.getBoundingClientRect();
      const line = parseFloat(getComputedStyle(el).lineHeight) || box.height;
      const cut = el.scrollWidth > el.clientWidth + 1; // a block cut off with an ellipsis
      const lines = el.getClientRects().length; // an inline name has one box per line it wraps onto
      if (
        box.width > 0 &&
        window.innerWidth < 600 &&
        (cut || lines > 2 || box.height > line * 2.2)
      ) {
        problems.push({
          kind: "name-squeezed",
          text: `"${el.textContent}" is cut off or wrapped to many lines (${Math.round(box.width)}px wide)`,
        });
        break;
      }
    }
    return problems;
  });
}

const found = new Map(); // "<page>@<viewport>:<kind>" -> sentence
try {
  await waitForServer();
  await mkdir("screenshots", { recursive: true });
  const browser = await chromium.launch(
    process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  );
  for (const vp of VIEWPORTS) {
    for (const theme of THEMES) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        colorScheme: theme,
      });
      await context.addCookies([
        { name: `sa_team_${LEAGUE}`, value: "1", url: `http://localhost:${PORT}` },
      ]);
      const page = await context.newPage();
      for (const p of PAGES) {
        if (p.league && !apiUp) continue;
        await page.goto(`http://localhost:${PORT}${p.path}`);
        await page.waitForTimeout(400); // images and the client render settle (live pages keep polling)
        const height = await page.evaluate(() => document.documentElement.scrollHeight);
        await page.screenshot({
          path: `screenshots/${p.name}-${vp.name}-${theme}.png`,
          fullPage: true,
          clip: { x: 0, y: 0, width: vp.width, height: Math.min(height, SHOT_HEIGHT) },
        });
        if (theme === "light") {
          for (const problem of await layoutProblems(page)) {
            found.set(`${p.name}@${vp.name}:${problem.kind}`, problem.text);
          }
        }
      }
      await context.close();
    }
  }
  await browser.close();
  console.log("screenshots written to frontend/screenshots/");
} finally {
  server.kill();
}
const fresh = [...found].filter(([key]) => !baseline.includes(key));
const fixed = baseline.filter((key) => !found.has(key) && apiUp);
await writeFile(
  "screenshots/layout-problems.txt",
  [...found].map(([key, text]) => `${key}: ${text}`).join("\n") + "\n",
);
if (fresh.length) {
  console.error("New layout problems:\n" + fresh.map(([k, t]) => `  - ${k}: ${t}`).join("\n"));
}
if (fixed.length) {
  console.error(
    "Fixed, so remove them from scripts/layout-baseline.json:\n" +
      fixed.map((k) => `  - ${k}`).join("\n"),
  );
}
if (fresh.length || fixed.length) process.exit(1);
console.log(`layout checks passed (${baseline.length} known problems on the list)`);
