# Sleeper Fantasy Assistant

[![CI](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Next.js](https://img.shields.io/badge/frontend-Next.js-black)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A public web app that connects to any [Sleeper](https://sleeper.com) fantasy football league by
username, blends several ranking and projection sources into one consensus, and turns it into
waiver alerts, trade ideas, rankings, playoff odds and weekly league recaps.

> **Status:** early development (Milestone 1, foundation). Sleeper's API is public and read-only,
> so the assistant only recommends; you make the move in the Sleeper app.

## What it will do

| Area | Features |
|------|----------|
| Rankings | Consensus positional rankings (weekly and rest of season) with source spread and tiers |
| Waivers | Free-agent scoring, FAAB bid advisor, injury report and status-change alerts |
| Trades | Needs-based trade suggestions, fleece alerts, manager profiles |
| Odds | Monte Carlo season simulator: projected records, playoff, bye and title odds, power rankings |
| Game day | Start/sit optimizer, matchup previews, live win probability, playoff leverage |
| Recaps | Weekly write-ups, trash talk, team names, season awards (family-friendly by default) |
| Offseason | News feed, draft assistant, keeper/dynasty mode, ask-the-assistant chat |

See [docs/PLAN.md](docs/PLAN.md) for the plan, [docs/TOOLS.md](docs/TOOLS.md) for what each tool and
service is and why it was chosen, [docs/DEPLOY.md](docs/DEPLOY.md) for hosting, and the
[milestones](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/milestones) and
[issues](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/issues) for progress.

## Principles

1. **Consensus over any single source**: every value shows its source spread.
2. **Calibrated numbers**: odds come from simulation, with accuracy tracked against reality.
3. **League-aware**: scoring, roster slots and deadlines are read from Sleeper, never hard-coded.
4. **Explain every recommendation**: a one-line why plus the numbers behind it.

## Architecture

A Python core ingests data on a schedule into Postgres; the web app only reads from it.

```
Sleeper API + other sources -> ingest jobs -> Postgres -> FastAPI -> Next.js dashboard
                                   |                         |
                              job queue/worker          alerts, recaps (LLM)
```

| Part | Tech |
|------|------|
| Backend (`backend/`) | Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, httpx, managed with [uv](https://docs.astral.sh/uv/) |
| Frontend (`frontend/`) | Next.js (App Router), TypeScript, Vitest, ESLint |
| Storage | Postgres (SQLite for quick local tests) |
| CI | GitHub Actions: ruff, mypy (strict), pytest + coverage, tsc, eslint, vitest |

## Project structure

```
backend/
  src/sleeper_assistant/   api, sleeper client, ingest, rules, db models
  migrations/              Alembic migrations
  tests/                   pytest tests and recorded JSON fixtures
frontend/                  Next.js app
docs/PLAN.md               build plan and milestones
CLAUDE.md                  workflow and engineering rules for contributors and AI agents
```

## Getting started

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
# backend
cd backend
uv sync
uv run alembic upgrade head          # creates ./dev.db (SQLite) by default
uv run uvicorn sleeper_assistant.api:app --reload   # http://localhost:8000/health
```

```bash
# frontend
cd frontend
npm ci
npm run dev                          # http://localhost:3000
```

### Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | SQLAlchemy URL for the app and migrations | `sqlite:///./dev.db` |
| `TEST_DATABASE_URL` | Run the test suite against Postgres | in-memory SQLite |

Never commit secrets; put keys in environment variables or a git-ignored `.env`.

### Tests and checks

```bash
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && npm run typecheck && npm run lint && npm test
```

## Contributing

Work happens through issues and small PRs into `develop`; see [CONTRIBUTING.md](CONTRIBUTING.md)
and [CLAUDE.md](CLAUDE.md). Security issues: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
