// Lightweight screenshots for PRs: builds nothing, expects `npm run build` first.
// usage: npm run screenshots            (writes ./screenshots/*.png, git-ignored)
import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const PORT = 3123;
const PAGES = [{ name: "home", path: "/" }];
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

const server = spawn("npx", ["next", "start", "-p", String(PORT)], {
  stdio: "ignore",
  shell: true,
});

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

try {
  await waitForServer();
  await mkdir("screenshots", { recursive: true });
  const browser = await chromium.launch();
  for (const vp of VIEWPORTS) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    for (const p of PAGES) {
      await page.goto(`http://localhost:${PORT}${p.path}`);
      await page.screenshot({ path: `screenshots/${p.name}-${vp.name}.png`, fullPage: true });
    }
    await page.close();
  }
  await browser.close();
  console.log("screenshots written to frontend/screenshots/");
} finally {
  server.kill();
}
