# Contributing

Thanks for helping out! The short version of how work happens here:

1. **Find or open an issue.** Every pull request needs exactly one issue, and one issue per PR.
2. **Branch from `develop`** using a type prefix: `feature/`, `bugfix/`, `chore/`, `docs/`,
   `refactor/` or `test/` (for example `feature/waiver-alerts`).
3. **Open a PR into `develop`** with `Closes #<issue>` in the description. Only `develop` is
   merged into `main` (release PRs).
4. **CI must be green** before merging. PRs are **squash merged**.
5. **Frontend changes** need accessibility tests and, when feasible, lightweight screenshots.

The full rules live in [CLAUDE.md](CLAUDE.md#workflow-required) (written for both humans and AI agents).

## Local setup

Shortcut (needs `make`, or use the devcontainer): `make setup`, `make check`, `make fmt`, `make hooks`;
see `make help`. The manual commands are:

```bash
# backend (Python 3.12+, uv)
cd backend && uv sync
uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest

# frontend (Node 22+)
cd frontend && npm ci
npm run typecheck && npm run lint && npm test
```

Install the hooks once with `uv run pre-commit install` (from `backend/`).

## Standards

CI runs the backend and frontend jobs only for PRs that change those folders (or `ci.yml`); a skipped
job reports as skipped, which counts as passing for the required checks. Pushes to `develop` and `main`
always run everything.

- Python: ruff, `mypy --strict`, pytest with an 80% coverage floor.
- Every parser for an external data source needs a fixture test.
- League rules are read from Sleeper, never hard-coded.
- Never commit secrets. Use environment variables; `.env` files are git-ignored.

## Dependency updates

Dependabot opens grouped weekly PRs (minor/patch together, majors separately) into `develop`.
They follow the same rules as any PR: green CI, squash merge. Nothing auto-merges.

## Releases

Releases are squash merged like everything else. Squashing `develop` into `main` leaves `main` with
a commit that `develop`'s history does not contain, so the next plain `develop` -> `main` PR
conflicts. The first release (v0.1.0) was a plain PR; later releases carry develop's exact files:

1. Make sure `develop` is green and contains what should ship. Open an issue "Release vX.Y.Z".
2. Branch from `main`: `git checkout -b hotfix/release-vX-Y-Z origin/main`.
3. Copy develop's tree onto it: `git read-tree -u --reset origin/develop`, then commit as
   `chore: release vX.Y.Z` (it must end up identical to develop: `git diff origin/develop` is empty).
4. Open a PR into `main` (title `chore: release vX.Y.Z`, body `Closes #<issue>`), wait for CI, then
   **squash merge**. Close the issue by hand (GitHub only auto-closes on merges into `develop`).
5. Release notes are drafted from merged PR titles (Releases tab); publish the draft to tag it.

Production (Vercel `web` and `api`) deploys from `main`; previews come from `develop` and PRs.
Urgent fixes use a `hotfix/<name>` branch from `main`, then the fix is applied to `develop` too.

## Reporting problems

Bugs and feature ideas go in [issues](../../issues). For security problems, see
[SECURITY.md](SECURITY.md) and do not open a public issue.
