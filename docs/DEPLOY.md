# Deploying

Free-tier layout: web on Vercel, API on Vercel (Python), database on Neon, worker as a scheduled
GitHub Actions job. Never commit connection strings; they live in secrets and git-ignored `.env.local`.

| Piece | Where | Config |
|---|---|---|
| Database | Neon (project branch `production`) | pooled URL for the app, direct URL for migrations |
| Web (`frontend/`) | Vercel project `web`, root directory `frontend` | env `API_URL` = the API project's URL |
| API (`backend/`) | Vercel project `api`, root directory `backend` | env `DATABASE_URL` = Neon **pooled** URL |
| Migrations | GitHub Actions `Migrate database` | secret `DATABASE_URL_UNPOOLED` |
| Worker | GitHub Actions `Worker` (every ~15 min) | secret `DATABASE_URL`, repo variable `WORKER_ENABLED=true` |

## One-time setup

1. **Database:** create the Neon project; copy the pooled and direct connection strings.
2. **Secrets:** `gh secret set DATABASE_URL` (pooled) and `gh secret set DATABASE_URL_UNPOOLED` (direct).
3. **Migrations:** Actions -> *Migrate database* -> Run workflow (also runs when `main` changes migrations).
4. **API project:** Vercel -> Add New Project -> import this repo -> name `api`, Root Directory `backend`
   (framework FastAPI is detected from `backend/app.py`). Add env var `DATABASE_URL` (pooled URL).
5. **Web project:** in the `web` project add env var `API_URL` = the API project's production URL
   (no trailing slash), then redeploy.
6. **Worker:** set repo variable `WORKER_ENABLED` to `true` (Settings -> Secrets and variables ->
   Actions -> Variables) once steps 1-3 are done.

## Notes

- Vercel Hobby is for non-commercial personal use and allows 100 deployments a day. To stay under it,
  only `main` deploys: no other branch (`develop`, feature, bot or release branches) does, CI still
  tests them, and an `ignoreCommand` in both `vercel.json` files skips anything that is not `main` as
  a catch-all. `web` also skips a build when `frontend/` is unchanged and `api` when `backend/` is
  unchanged. Try a change on localhost (see "Testing develop" below), not on Vercel. When the limit is hit, builds fail with "Deployment rate
  limited" and resume about 24 hours later; production keeps serving the last good deployment.
- Neon free compute suspends when idle; the first request after a pause is slower.
- GitHub cron is best-effort (runs can be late; schedules pause after 60 days without commits).
- The first league connect loads Sleeper's player database if the table is empty; the worker also
  refreshes it daily.
- Known risk: connecting a league syncs it inside one request (about 40 Sleeper calls). If the first
  connect hits the serverless time limit, let the worker run once (it loads the player database and
  syncs active leagues) and retry; a background sync-on-connect is a follow-up.
- The worker also refreshes kickoff times from nflverse once a day (job `sync_kickoffs`), Sleeper's
  projections every 3 hours (`sync_projections`), add and drop trends and weekly stats hourly
  (`sync_trending`, `sync_stats`), past seasons game by game once (`sync_history`: the 18 weekly stat lines of each of the last two seasons plus their schedules, about 6 MB of database per season, measured on 2024 and 2025; regular season only, playoffs are not included) ESPN's ownership
  percentages every 3 hours (`sync_ownership`) and every team's depth chart every 3 hours
  (`sync_depth_charts`). A failed download only leaves the previous numbers in place.
- **Live games.** From an hour before a kickoff until five hours after (or while Sleeper says a game
  is in progress) the app runs faster: the API answers reads with a 10 second cache instead of 30,
  ESPN's scoreboard is cached 15 seconds, the worker syncs the stat lines every 2 minutes and the
  schedule every 3 (instead of hourly and every 10), and a worker run that starts inside the window
  keeps cycling about once a minute for up to 11 minutes (the next scheduled run carries on; a game
  Sleeper still calls in progress 8 hours after kickoff is treated as stale). Pages with a live game,
  or one about to kick off, refresh themselves every 15 seconds, with a Pause button. GitHub's scheduled runs
  start every 15 minutes and can be late, so stats are as fresh as the last worker minute; a
  continuously running worker would make them steadier. Outside the window nothing changes, so
  quiet days cost nothing.
- `backend/app.py` is the Vercel entrypoint; locally use `uvicorn sleeper_assistant.api:app`.

## Testing develop before a release

`develop` is not deployed. Run it on your machine, against its own SQLite database:

```bash
make setup     # once: install backend and frontend dependencies
make dev       # migrates ./backend/dev.db, then runs the API (:8000) and the web app (:3000)
```

For a first look without Sleeper, run `make preview-data` once: it loads a made-up league (id 100001,
open http://localhost:3000/league/100001). Or open http://localhost:3000 and connect your Sleeper username once to load a league (the first
connect also loads Sleeper's player list). The worker is not needed for a first look; run
`uv run python -m sleeper_assistant.worker --once` in `backend/` to fetch projections and rankings.
To see how a page looks at phone and desktop width, run `npm run screenshots` in `frontend/`.

## LLM (optional)

Alert advice can be written by a model (`llm.py`). It is off unless configured, and the app falls
back to its computed text whenever the model is off, fails, or states a number that is not in the
facts. Set these as environment variables (never commit keys):

- `LLM_PROVIDER`: `none` (default), `anthropic`, or `openai_compatible` (Qwen via Ollama, vLLM,
  OpenRouter or any OpenAI-style server).
- `LLM_MODEL`, `LLM_API_KEY` (or `ANTHROPIC_API_KEY`), `LLM_BASE_URL` (OpenAI-compatible only).
- `LLM_MAX_CALLS_PER_RUN`: call cap per worker run (default 50).

Free option (Google Gemini, no code change): create an API key in Google AI Studio, then set
`LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`,
`LLM_MODEL=gemini-2.5-flash` (repository variables) and `LLM_API_KEY=<the key>` (a repository
secret) for the worker.
Free-tier limits and terms are Google's and can change; when it throttles, alerts keep their
computed text. The ruled-out and waiver alerts then carry an "AI assistant" suggestion.

Privacy: when a model is on, the worker sends each alert's facts (player names, projections, fantasy
team names and rosters from Sleeper's public API, never emails, tokens or keys) to that provider.
Some free tiers may use submitted content to improve their models; read the provider's terms
before turning it on, and leave `LLM_PROVIDER` unset to keep everything local.

A Claude.ai chat subscription cannot be used by a server; Claude needs an Anthropic API key.
