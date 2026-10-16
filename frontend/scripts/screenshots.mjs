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
  {
    stdio: "ignore",
  },
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
