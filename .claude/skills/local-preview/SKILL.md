---
name: local-preview
description: Run a local copy of the current branch (API on SQLite plus a built web app) for the user to click through, on ports that do not touch their own dev server. Covers migrating the preview database, populating it from a real league, restarting after every rebuild, and checking the layout. Use when the user asks for a develop session, a preview, or to see a change before it ships.
---

# Local preview

The user usually has their own `next dev` on port 3000. Never stop or reuse it. This preview uses
**API on 8124** and **web on 3126** so both can run side by side.

Use PowerShell for starting servers on Windows (`Start-Process -WindowStyle Hidden`); Bash backgrounding
ties the servers to the tool call.

## Start (or refresh) it

1. **Stop only the preview ports** (not 3000):
   `Get-NetTCPConnection -LocalPort 3126,8124 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }`
   A running server also locks files in `backend/.venv`, which makes `uv sync` fail with "Access is denied".
2. **Migrate the preview database** (SQLite in the temp folder, not the repo; `*.db` is git-ignored), from `backend/`:
   `$env:DATABASE_URL="sqlite:///$($env:TEMP -replace '\\','/')/preview.db"; .\.venv\Scripts\alembic.exe upgrade head`
3. **Start the API** with the same `DATABASE_URL`:
   `Start-Process -WindowStyle Hidden .\.venv\Scripts\uvicorn.exe -ArgumentList "sleeper_assistant.api:app","--port","8124"`
4. **Build and start the web app** from `frontend/` with `$env:API_URL="http://127.0.0.1:8124"`:
   `npm run build`, then
   `Start-Process -WindowStyle Hidden node -ArgumentList "node_modules\next\dist\bin\next","start","-p","3126"`
5. **Populate it** by connecting a real league through the local API (public Sleeper data, no login):
   `curl -X POST http://127.0.0.1:8124/api/leagues/<league_id>/connect`. Re-run this after any change
   that adds a synced field, because existing rows only gain it on the next sync. The kickoff times come
   from a separate job: call `sync_kickoffs` (see `kickoffs.py`) against the preview database.
6. **Check it** before saying it is ready: `http://localhost:3126/` returns 200, `http://127.0.0.1:8124/health`
   returns 200, and the league page loads (`/league/<league_id>?tab=standings`, `rosters`, `lineups`, `settings`).

## Rules learned the hard way

- **Restart the web server after every `npm run build`.** A running `next start` keeps serving the old
  build's page, which points at CSS and script files the new build deleted, so the site shows as plain
  unstyled HTML. If the page looks unstyled, the server is stale: restart it.
- A build rewrites `frontend/tsconfig.json`; run `git checkout -- frontend/tsconfig.json` before switching
  branches.
- The data refreshes about every 30 seconds (fetch cache), so reload after changing the database.
- To check layout, use the browser pane's `resize_window` with the `mobile` preset, then reset it to
  `desktop` when done. If the viewport reports zero width, the pane is hidden: measure in `desktop` size
  or use `get_page_text` instead of trusting numbers from a hidden pane.
- Tell the user the URL and what is (and is not) in the build, for example "this is develop as of <commit>;
  <feature> is not merged yet".

Never put a real connection string in the preview: it uses a throwaway SQLite file only.
