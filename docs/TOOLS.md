# Tools and services

What each tool is, what it does in this project, and why it was chosen. Free-tier limits change, so
check each provider's pricing page before relying on a number.

## Hosting and data

### Neon (database)

- **What it is:** a hosted Postgres database. "Serverless" means its compute sleeps when idle and wakes
  on the first query.
- **What it does here:** stores everything the app knows: leagues, rosters, matchups, transactions,
  players, the player ID crosswalk and the job queue. The API reads and writes it; the worker fills it.
- **Why it was chosen:**
  - It is real Postgres, which the plan needs (job queue with `SKIP LOCKED`, JSON columns, and room
    to grow into the simulator and accuracy tracking).
  - The free tier is enough for a personal project, so it costs nothing at this scale.
  - **Branching:** a `develop` branch is a copy-on-write copy of production, so changes can be tested on
    real-shaped data without touching production (see [DEPLOY.md](DEPLOY.md)).
  - It has a pooled connection endpoint, which suits serverless hosts that open many short connections.
- **Trade-offs:** the free compute sleeps after idle time, so the first request after a quiet period is
  slower. The free tier has storage and compute limits.
- **Where it is configured:** connection strings live in GitHub secrets, Vercel environment variables
  and the git-ignored `.env.local`. `neon.ts` holds the project config. Two connection strings are used:
  pooled for the app and worker, direct for migrations.

### Vercel (web app and API hosting)

- **What it is:** a hosting platform that builds and deploys straight from GitHub, giving every branch
  and pull request its own preview URL.
- **What it does here:** two projects. `web` serves the Next.js site; `api` runs the FastAPI backend as
  a Python serverless function. Merges to `main` go to production and `develop` gets a preview; work branches do not deploy (the free plan caps deployments per day).
- **Why it was chosen:**
  - Zero-config deploys for both Next.js and FastAPI, and no server to look after.
  - Preview deployments per branch make it possible to test changes before they reach `main`.
  - The free Hobby plan covers a personal project. It is for non-commercial use, and it has limits on
    function time and deployments.
  - Functions can be pinned to a region; ours run in Portland next to the Neon database, which cut page
    loads from about 0.7 s to about 0.2 s.
- **Trade-offs:** serverless functions have time limits, which matters for the first sync of a league. The
  scheduled worker cannot live there, so it runs on GitHub Actions instead.

### GitHub (repository, CI, automation)

- **What it is:** the code host, plus Actions (automation), Dependabot (dependency updates) and security scanning.
- **What it does here:** holds the code and issues; runs CI on every PR; enforces the workflow rules
  (PR policy, required checks, squash merges); runs the scheduled worker and database migrations;
  scans for secrets and vulnerable dependencies.
- **Why it was chosen:** it is where the code lives, Actions is free for public repos, and it keeps
  automation next to the code.

### Sleeper API (data source)

- **What it is:** Sleeper's public, read-only API for leagues, rosters, matchups, transactions and players.
- **What it does here:** the system of record for everything about a league. No login is needed.
- **Why:** it is public, covers what the app needs, and never requires users' credentials.
- **Trade-offs:** it has no projections or live game state; those come from other sources later (issues #109, #131).

### ESPN fantasy API (ownership, start percentages, depth charts and live games)

- **What it is:** ESPN's public fantasy football API. It is undocumented, needs no key, and is the one free
  source we found for "what share of leagues roster and start this player".
- **What it does here:** every few hours the worker pulls the top 900 players' `percentOwned` and
  `percentStarted` (about 4 MB compressed) and the Players tab shows them as ESPN-wide numbers, never as
  Sleeper's. ESPN players are matched to Sleeper players by ESPN id where Sleeper has one, otherwise by
  name, team and position; a name that matches two players is left out rather than guessed (97% of players
  with points, and every rostered or high-scoring one, matched on real data).
- **Depth charts:** the same family of free endpoints gives each team's full depth chart (offense
  including the offensive line, defense by scheme, and special teams with the holder and returners), one
  request per team. The worker refreshes all 32 every few hours (a few seconds in total) and matches the
  players to Sleeper's by ESPN id or name within the team (99% matched on real data). Sleeper's own depth
  chart fields are the fallback when ESPN has nothing, and a failed pull keeps the last good chart.
- **Live games:** ESPN's scoreboard (one small request for the whole week) gives each game's score,
  quarter and clock to the minute. The API asks for it only while a game could be on (from an hour before
  a kickoff to five hours after, or while Sleeper says a game is in progress) and keeps the answer for 45
  seconds in memory, so many viewers cause one request. If ESPN is down the badge falls back to Sleeper's
  state, and final scores come from the nflverse schedule. Where ESPN and Sleeper disagree about whether
  a game has started, ESPN's answer is shown, because it is fresher.
- **Why:** Sleeper publishes no such numbers, and this is free.
- **Trade-offs:** it can change without notice, so the parser is tested against a recorded shape and a
  failed or empty pull leaves the previous numbers in place. Personal, non-commercial use only; revisit if
  the project ever charges or runs ads.

### nflverse (kickoff times)

- **What it is:** an open-source project that publishes NFL data, including the full schedule, under CC BY 4.0.
- **What it does here:** Sleeper's schedule has game dates but no kickoff time, so a daily job reads
  nflverse's schedule file and stores each game's kickoff (converted from US Eastern to UTC). The site
  then shows it in each viewer's own time zone.
- **Why:** free, no key, complete (all 272 regular-season games matched Sleeper's), and credit is all it asks.
- **Trade-offs:** it is a third-party file, so a failed download just leaves the last known times, and
  the footer credits nflverse. nflverse calls the Rams `LA` where Sleeper says `LAR`; one code is mapped.

## Backend

| Tool | What it is | What it does here | Why |
|---|---|---|---|
| Python 3.12 | Language | All backend code | Strong data and modeling libraries for the later simulator and rankings |
| FastAPI | Web framework | The API (`/api/...`, `/health`, `/health/db`) | Typed, fast to build, automatic validation of inputs |
| Pydantic | Data validation | Models for Sleeper payloads and API responses | Catches schema drift in unofficial sources early |
| SQLAlchemy | Database toolkit | Table definitions and queries | Works on Postgres in production and SQLite in tests |
| Alembic | Migration tool | Versioned database schema changes | Reproducible schema across production, `develop` and local |
| httpx | HTTP client | Calls the Sleeper API | Modern, easy to mock in tests |
| uv | Package manager | Installs dependencies from a lockfile | Fast, reproducible installs |

## Frontend

| Tool | What it is | What it does here | Why |
|---|---|---|---|
| Next.js | React framework | The website, rendered on the server | Fast pages, simple routing, first-class Vercel support |
| TypeScript | Typed JavaScript | All frontend code | Catches mistakes before they ship |
| CSS tokens | Plain CSS | Themes, position colors and layout | No framework needed; light and dark from one set of variables |

## Quality, testing and security

| Tool | What it does here | Why |
|---|---|---|
| ruff | Python lint and format | One fast tool for both |
| mypy (strict) | Python type checking | Types catch bugs the tests miss |
| pytest, pytest-cov, hypothesis | Backend tests with an 80% coverage floor | Fixtures protect against external-data drift |
| Vitest, Testing Library, vitest-axe | Frontend tests, including accessibility | Accessibility is tested, not assumed |
| Playwright | Screenshots of the site | Visual checks on desktop and phone sizes |
| pre-commit | Runs lint, format and secret checks before each commit | Catches problems before CI |
| gitleaks, GitHub secret scanning | Block committed secrets | The repo is public |
| CodeQL, dependency review, Dependabot | Find vulnerable code and dependencies | Free for public repos |

## Working with Claude Code

- **CLAUDE.md** holds the workflow rules (one issue per PR, typed branches, squash merges, CI green before merge).
- **`.claude/skills/`** has project skills: `ship-pr`, `run-checks`, `add-source-parser`.
- Code is reviewed with the `code-review` skill before it is pushed.
