# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## What this is

A public web app that connects to any Sleeper fantasy football league by username, blends several
ranking/projection sources into a consensus, and produces waiver alerts, trade ideas, rankings,
playoff odds and weekly recaps. The Sleeper API is public and **read-only**: the app recommends,
users act in the Sleeper app. See [docs/PLAN.md](docs/PLAN.md) for the full build plan and milestones.

## How we work (read first)

1. **Reuse before you write.** Before adding code, look for what already exists and use it:
   `backend/src/sleeper_assistant` (`core/` rules and calculations such as `stat_lines`, `projections`,
   `lineup_slots`, `matchup_rank`; `alerts/helpers`; `utils/`; `constants.py`), `frontend/lib` (`format.ts` numbers, `time.ts` times, game state, lineups, alerts, positions) and
   `frontend/components` (`PlayerIdentity`, `PlayerStatLine`, `StatTable`, `FilterChips`, `GameBadge`, `GameLine`, `ReasonChips`, `PanelTabs`, `LocalTime`,
   `WinBar`). Search first (`grep`), read the module, then extend it. Do not write a second version.
2. **Duplicated logic becomes a shared util.** The second time the same logic is needed, move it to
   one shared module (backend: a small module named for what it does; frontend: `lib/<topic>.ts`),
   point both callers at it, and give it its own test. A private helper imported across modules
   (`_name`) is a sign it should be public and shared.
3. **Separation of concerns.** One responsibility per module. Rules and data live in the backend
   (scoring, projections, alerts, win chances); formatting and view decisions live in `frontend/lib`;
   components lay things out and call `lib`. League rules are read from Sleeper, never hard-coded.
   Pages do not format numbers, components do not own business rules, and CSS values come from the
   tokens in `app/styles/tokens.css`.
4. **Frontend: reuse existing elements.** A new screen is built from the shared components and CSS
   patterns in [docs/DESIGN.md](docs/DESIGN.md). If a component does not do what you need, change it
   for every screen (and let the consistency test hold the line). Never create a one-off table, chip
   group, player row, card or colour.
5. **The code does nothing until it looks right.** Treat a UI change as unfinished until you have
   looked at it. Open the screenshots on the PR (phone first, then desktop, light and dark) and go in
   assuming something is wrong. If anything looks off (cramped, wrapped letter by letter, too wide,
   too tall, misaligned, inconsistent with another screen, hard to read), fix it before asking for a
   merge; do not wait for the owner to spot it.
6. **Visual findings become issues automatically.** Any visual problem found while reviewing images or
   the layout check that is not fixed in the same PR gets an issue straight away (what is wrong, the
   page and width, the screenshot, labels `bug` or `enhancement` plus `frontend`, a milestone), and is
   then worked in the owner's order. Never leave a known visual problem unrecorded.
7. **Every issue has a milestone and labels.** Issues are created with both; a PR gets its issue's
   milestone.

## Layout

- `backend/` — Python 3.12 (FastAPI, Pydantic, httpx). Package `src/sleeper_assistant`. Managed with **uv**.
  - `api/` the app, shared dependencies (`deps`) and the league routes. Routes stay thin: they call a view.
  - `views/` read models, one per page or tool (dashboard, lineups, games, players, player detail, team depth,
    rankings, waiver wire, start/sit, transactions, news, lineup accuracy). They read stored data, never fetch.
  - `alerts/` the engine (`engine`), what every detector needs (`helpers`), model `advice` and the detectors
    (`bye`, `injury`, `lineup`, `waiver`, registered in `detectors`).
  - `sync/` getting data in and keeping it fresh: league, player, stats, depth chart, news and kickoff syncs,
    the crosswalk, and the job queue (`jobs`, `job_schedule`).
  - `sources/` outside services we read from: Sleeper, ESPN (scoreboard, ownership, box score), news feeds and
    the language model client (`llm`, with its `prompts/`). Parsing of an unofficial source lives here.
  - `core/` rules and calculations the rest builds on: scoring and projections, lineup slots, injury statuses,
    win probability, matchup ranks, the NFL schedule and team helpers.
  - `utils/` small shared helpers (reading untrusted JSON, text, time, caches); `constants.py` values used by
    more than one module.
  - top level: `db` (tables), `worker` (runs queued jobs), `boot` and `sample_league` (made-up data for previews).
  - **Where a new file goes:** a new data source in `sources/` (see the `add-source-parser` skill) and the code
    that stores it in `sync/`; a page's read model in `views/` and its route in `api/`; a rule or calculation
    in `core/`; an alert in `alerts/` following the detector pattern in `alerts/engine.py`; a helper two modules
    need in `utils/`; a value two modules need in `constants.py`. Dependencies mostly point one way:
    `api` -> `views`/`alerts` -> `core` -> `sources` -> `utils`/`constants`; `sync` uses `sources` and `core`.
    Known exception: `alerts` and `views` still import each other (the waiver wire reuses the waiver alert's
    board, the lineup alert reuses start/sit); do not add more, move shared logic down to `core/`.
- `frontend/` — Next.js (App Router, TypeScript). Managed with **npm**.
- `.github/workflows/` — CI (`ci.yml`), PR policy, secret scan, dependency review (CodeQL is enabled in repo settings).
- `.claude/skills/` — project skills: `ship-pr` (issue -> branch -> review -> CI -> squash merge),
  `run-checks` (what CI runs), `add-source-parser` (new data source checklist). `scripts/ship-pr.sh` backs `ship-pr`.
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
npm run format         # prettier --write (CI runs npm run format:check)
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
- Frontend: `prettier --check`, `tsc --noEmit`, `eslint`, `vitest` (including accessibility tests) must pass.

## Workflow (required)

- **One issue per PR, and every PR needs an issue.** Create or find the issue first; the PR body
  must say `Closes #<n>`. Keep each PR scoped to its single issue.
- **Branch names** use a type prefix and start from `develop`: `feature/<short-name>`,
  `bugfix/<short-name>`, `chore/<short-name>`, `docs/<short-name>`, `refactor/<short-name>`,
  `test/<short-name>`. Hotfixes branch from `main` as `hotfix/<short-name>`.
- **Feature, bugfix, chore and docs branches merge into `develop` only — never into `main`.**
- **`develop` merges into `main` only** (a release PR). Nothing else targets `main`
  (except `hotfix/*`, which is then back-merged into `develop`).
- **CI must pass before anything is merged**, into `develop` or `main`. No admin overrides, no
  skipping hooks. If CI is red, fix it on the branch.
- **Squash merge every PR** (`gh pr merge --squash --delete-branch`), including release PRs
  from `develop` to `main`. Squash commit titles follow Conventional Commits.
- **Frontend changes** must include (1) accessibility tests (axe assertions plus role/label queries
  via Testing Library, keyboard reachability for interactive elements) and (2) lightweight
  screenshots (desktop and mobile width, no secrets or real user data). The Screenshots workflow
  shoots every page against the made-up sample league (`backend/src/sleeper_assistant/sample_league.py`)
  and posts the images on the PR; read the phone ones first. Locally: `make preview-data`, `make dev-api`,
  then `npm run screenshots` in `frontend/`. The run also checks the layout at phone width against
  `frontend/scripts/layout-baseline.json`, a list of known problems that may only shrink; the job is
  "Frontend screenshots" and must be a required check in branch protection to block merging. Read
  the images in the PR comment before merging and act on them (see "How we work", points 5 and 6).
  Tooling: `tests/a11y.ts` (`expectNoA11yViolations`) and Testing Library.
- **Review before pushing.** Run the `code-review` skill on the branch diff before pushing code
  changes and fix its findings first. Also run `a11y-enforcer:a11y-check` for UI changes and
  `security-review` for anything touching auth, user input, secrets or external requests.
- Commits use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).

## Design

Take inspiration from Sleeper and theScore (inspiration only, no assets): see [docs/DESIGN.md](docs/DESIGN.md).
Build from the shared patterns there, keep the number of tabs small, and keep content to one width
so tables and cards never span the whole screen. Look at every UI change at phone (390 px) and
desktop width in both themes before it ships, phone first: names must not wrap letter by letter,
rows must not be tall blocks, and nothing may scroll the page sideways.

## Conventions

- League rules (scoring, roster slots, deadlines, waiver type) are **read from Sleeper, never hard-coded**.
- Every league-scoped table is keyed by `league_id`; player-level data is shared across leagues.
- Every recommendation ships a one-line "why" plus the numbers behind it.
- LLM output (recaps, trash talk) is written only around a fixed JSON of computed facts; validate numbers.
- Recaps default to family-friendly tone.
- Treat unofficial endpoints as fragile: cache raw responses, version schemas, alert on parse failures.
- Backend modules stay small and named for what they do; extract a helper when two modules need it.
- Frontend `lib/` holds pure functions (formatting, state, view rules) with unit tests; components
  stay thin.
- Never commit secrets; API keys go in environment variables (`.env` is git-ignored).
