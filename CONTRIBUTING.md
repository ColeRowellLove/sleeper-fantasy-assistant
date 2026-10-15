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

- Python: ruff, `mypy --strict`, pytest with an 80% coverage floor.
- Every parser for an external data source needs a fixture test.
- League rules are read from Sleeper, never hard-coded.
- Never commit secrets. Use environment variables; `.env` files are git-ignored.

## Releases

1. Make sure `develop` is green and contains what should ship.
2. Open a PR **from `develop` into `main`** titled `chore: release vX.Y.Z` (no issue link needed).
3. After CI is green, **squash merge** it.
4. Release notes are drafted automatically from merged PR titles (Releases tab). Review the draft,
   then publish it to create the tag.

Urgent fixes use a `hotfix/<name>` branch from `main` into `main`, then are merged back into `develop`.

## Reporting problems

Bugs and feature ideas go in [issues](../../issues). For security problems, see
[SECURITY.md](SECURITY.md) and do not open a public issue.
