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
  screenshots in the PR description when feasible (before/after, desktop and mobile width,
  compressed PNG, no secrets or real user data). Tooling: `tests/a11y.ts` (`expectNoA11yViolations`), Testing Library, and `npm run screenshots`
  (also produced by the Screenshots workflow as a downloadable artifact).
- **Review before pushing.** Run the `code-review` skill on the branch diff before pushing code
  changes and fix its findings first. Also run `a11y-enforcer:a11y-check` for UI changes and
  `security-review` for anything touching auth, user input, secrets or external requests.
- Commits use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).

## Design

Take inspiration from Sleeper and theScore (inspiration only, no assets): see [docs/DESIGN.md](docs/DESIGN.md).
Reuse the shared patterns there instead of building a new layout per tab, keep the number of tabs
small, and look at a UI change (screenshots at phone and desktop width, both themes) before it ships, and
check the phone one first: names must not wrap letter by letter and rows must not be tall blocks.

## Conventions

- League rules (scoring, roster slots, deadlines, waiver type) are **read from Sleeper, never hard-coded**.
- Every league-scoped table is keyed by `league_id`; player-level data is shared across leagues.
- Every recommendation ships a one-line "why" plus the numbers behind it.
- LLM output (recaps, trash talk) is written only around a fixed JSON of computed facts; validate numbers.
- Recaps default to family-friendly tone.
- Treat unofficial endpoints as fragile: cache raw responses, version schemas, alert on parse failures.
- Never commit secrets; API keys go in environment variables (`.env` is git-ignored).
