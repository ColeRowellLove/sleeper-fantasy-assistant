# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## What this is

A public web app that connects to any Sleeper fantasy football league by username, blends several
ranking/projection sources into a consensus, and produces waiver alerts, trade ideas, rankings,
playoff odds and weekly recaps. The Sleeper API is public and **read-only**: the app recommends,
users act in the Sleeper app. See [docs/PLAN.md](docs/PLAN.md) for the full build plan and milestones.

## Layout

- `backend/` — Python 3.12 (FastAPI, Pydantic, httpx). Package `src/sleeper_assistant`. Managed with **uv**.
- `frontend/` — Next.js (App Router, TypeScript). Managed with **npm**.
- `.github/workflows/` — CI (`ci.yml`).
- `docs/` — plan and engineering notes.

## Commands

Backend (run from `backend/`):

```bash
uv sync --frozen            # install from lockfile
uv run ruff format .        # format
uv run ruff check .         # lint
uv run mypy                 # strict type check on src/
uv run pytest               # tests + coverage (80% floor), live tests skipped
uv run uvicorn sleeper_assistant.api:app --reload
```

Frontend (run from `frontend/`):

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run dev
```

## Engineering standards (enforced in CI and pre-commit)

- **ruff** for lint + format; rules `E,F,W,I,B,UP,SIM,RUF,PL`; line length 100.
- **mypy** `strict = true` on `src/` with the pydantic plugin. Only per-line `# type: ignore[code]`; no blanket ignores.
- **pytest** with an 80% coverage floor on `src/`. Use recorded JSON fixtures for Sleeper and other sources.
  Tests that hit the real network are marked `@pytest.mark.live` and are skipped in CI.
- **hypothesis** for simulator invariants (odds sum to 1, W+L = games played).
- Every parser for an unofficial source gets a fixture test so schema changes fail CI, not silently drop data.
- Frontend: `tsc --noEmit`, `eslint`, `vitest` must pass.

## Conventions

- Branches: `main` is release/production, `develop` is integration. Branch features from `develop`
  (`feat/…`, `fix/…`, `chore/…`) and open PRs into `develop`. Merge `develop` into `main` to release.
  Never push directly to `main`.
- Commits: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- League rules (scoring, roster slots, deadlines, waiver type) are **read from Sleeper, never hard-coded**.
- Every league-scoped table is keyed by `league_id`; player-level data is shared across leagues.
- Every recommendation ships a one-line "why" plus the numbers behind it.
- LLM output (recaps, trash talk) is written only around a fixed JSON of computed facts; validate numbers.
- Recaps default to family-friendly tone.
- Treat unofficial endpoints as fragile: cache raw responses, version schemas, alert on parse failures.
- Never commit secrets; API keys go in environment variables (`.env` is git-ignored).
