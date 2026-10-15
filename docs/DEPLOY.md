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

- Vercel Hobby is for non-commercial personal use.
- Neon free compute suspends when idle; the first request after a pause is slower.
- GitHub cron is best-effort (runs can be late; schedules pause after 60 days without commits).
- The first league connect loads Sleeper's player database if the table is empty; the worker also
  refreshes it daily.
- Known risk: connecting a league syncs it inside one request (about 40 Sleeper calls). If the first
  connect hits the serverless time limit, let the worker run once (it loads the player database and
  syncs active leagues) and retry; a background sync-on-connect is a follow-up.
- `backend/app.py` is the Vercel entrypoint; locally use `uvicorn sleeper_assistant.api:app`.
