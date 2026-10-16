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

See [docs/PLAN.md](docs/PLAN.md) for the plan, [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md) for what to build next, [docs/TOOLS.md](docs/TOOLS.md) for what each tool and
service is and why it was chosen, [docs/DEPLOY.md](docs/DEPLOY.md) for hosting, and the
[milestones](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/milestones) and
[issues](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/issues) for progress.

## What works today

Connect a league by Sleeper username and the app shows, for each league:

- **Standings:** sortable by any column (rank, team, record, streak, points for and against), with
  each manager's team name and your own team highlighted, plus the playoff line.
- **Rosters:** starters, bench, injured reserve and taxi, with injury status and each player's NFL
  game (kickoff in your time zone, live, final, or bye week).
- **Lineups:** every matchup side by side for any week, in the Sleeper starter order.
- **Players:** every relevant NFL player through your league: filter by position and availability, search, and sort by Sleeper adds and drops, ESPN owned and start percentages, positional rank, season points under your scoring, and projected points.
- **Player pop-up:** click any player (rosters, lineups, Players tab) for their bio, position rank, week-by-week points with every stat that counted, this week's projected stats, and past seasons, all scored with your league's rules.
- **Projections:** projected points (scored with your league's own rules) next to actual points on rosters and lineups, with a team total in each matchup and a win chance for each team (a simple model from the two projected totals; see `backend/src/sleeper_assistant/win_probability.py` for the assumptions).
- **Teams:** any NFL team's full depth chart (offense including the line, defense and special teams) with injuries, who is next up when a starter is out, and which of the players are on your league's rosters.
- **Settings:** the league's rules and scoring as Sleeper reports them.

Dark and light themes, phone and desktop layouts, and keyboard and screen-reader support throughout.
Kickoff times come from [nflverse](https://github.com/nflverse/nflverse-data) (CC BY 4.0).

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
| CI | GitHub Actions: ruff, mypy (strict), pytest + coverage, tsc, eslint, vitest, accessibility and screenshot checks |

## Project structure

```
backend/
  src/sleeper_assistant/   api, sleeper client, ingest, rules, db models
  migrations/              Alembic migrations
  tests/                   pytest tests and recorded JSON fixtures
frontend/                  Next.js app
docs/                      PLAN.md (build plan), TOOLS.md (tools and why), DEPLOY.md (hosting)
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
