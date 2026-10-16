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
  `feature/`, `bugfix/`, `chore/`, `docs/`, `refactor/`, `test/` and `hotfix/` branches do not deploy
  (CI still tests them), `web` skips a build when `frontend/` is unchanged and `api` when `backend/` is
  unchanged. Only `develop` and `main` deploy. When the limit is hit, builds fail with "Deployment rate
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
  keeps cycling about once a minute for up to 12 minutes (the next scheduled run carries on). Pages
  with a live game refresh themselves every 15 seconds, with a Pause button. GitHub's scheduled runs
  start every 15 minutes and can be late, so stats are as fresh as the last worker minute; a
  continuously running worker would make them steadier. Outside the window nothing changes, so
  quiet days cost nothing.
- `backend/app.py` is the Vercel entrypoint; locally use `uvicorn sleeper_assistant.api:app`.

## Testing develop before a release

`develop` is built as a preview on Vercel, so changes can be tried end to end before they reach `main`.

| What | URL |
|---|---|
| Develop web preview | `https://web-git-develop-cole-b6ee.vercel.app` |
| Develop API preview | `https://api-git-develop-cole-b6ee.vercel.app` (`/health/db` shows which database it uses) |

- **Web to API:** previews default `API_URL` to the develop API (see `frontend/lib/apiUrl.ts`). An
  explicit `API_URL` set for the Preview environment in Vercel wins; production never uses the develop API.
- **Separate database:** Neon has a non-expiring `develop` branch (a copy of production). The
  `Migrate develop database` workflow keeps it at develop's schema (secret
  `DATABASE_URL_UNPOOLED_DEVELOP`). To make the develop API use it, in the `api` Vercel project add
  `DATABASE_URL` for the **Preview** environment, Git branch `develop`, with the pooled develop connection
  string. Until that is set, previews use whatever `DATABASE_URL` applies to Preview, which may be production.
- **Data:** connect a league on the develop web preview once to load it into the develop database.
- Pull requests no longer get their own Vercel preview (see the deployment limit above); try a
  change locally or merge it into `develop` and use the develop preview.
