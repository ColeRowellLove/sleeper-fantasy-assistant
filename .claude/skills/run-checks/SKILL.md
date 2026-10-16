---
name: run-checks
description: Run the same backend and frontend checks CI runs (ruff, mypy, pytest, tsc, eslint, vitest, pre-commit). Use before committing or when CI fails and you need to reproduce it locally.
---

# Run checks

Run what is relevant to the files you changed; run both before opening a PR that touches both.

Backend (from `backend/`):

```bash
uv sync --frozen
uv run ruff format .        # CI uses --check
uv run ruff check .
uv run mypy
uv run pytest               # SQLite by default; set TEST_DATABASE_URL to also test on Postgres
```

Frontend (from `frontend/`):

```bash
npm ci
npm run format:check && npm run typecheck && npm run lint && npm test && npm run build
```

Everything (hooks incl. actionlint and gitleaks), from `backend/`:

```bash
uvx pre-commit run --all-files
```

Notes:
- New or changed models need an Alembic migration: `DATABASE_URL=sqlite:///gen.db uv run alembic upgrade head`
  then `... alembic revision --autogenerate -m "<what>" --rev-id <next>`; delete `gen.db` afterwards.
- CI's Postgres run catches things SQLite hides (e.g. integer overflow); reproduce with a local Postgres
  and `TEST_DATABASE_URL`.
- actionlint/shellcheck on Linux can be stricter than on Windows; trust CI's output.
