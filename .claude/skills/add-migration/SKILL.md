---
name: add-migration
description: Change the database schema in this repo - SQLAlchemy model in db.py, a numbered Alembic migration, test and fixture updates, and the rollout order for the develop and production databases. Use whenever a column or table is added, changed or removed.
---

# Add a database migration

Schema lives in `backend/src/sleeper_assistant/db/**`; migrations live in `backend/migrations/versions/`
and are numbered `0001`, `0002`, ... (the last one is the highest number in that folder).

## Steps

1. **Model first.** Edit the SQLAlchemy model in `db.py`. New columns on tables that already hold rows
   must be nullable or have a default, because production data exists. Keep the type portable: tests run
   on SQLite, production on Postgres.
2. **Write the migration by hand** as the next number, `backend/migrations/versions/00NN_short_name.py`,
   copying the header of the previous one (`revision = '00NN'`, `down_revision = '00NN-1'`). Put the real
   change in `upgrade()` (`op.add_column(...)`) and its inverse in `downgrade()`. Do not rely on
   autogenerate output; read what it would do and keep only the intended change.
3. **Apply it locally** from `backend/` against a throwaway database, never the real one:
   `DATABASE_URL=sqlite:///./scratch.db uv run alembic upgrade head` (then delete `scratch.db`; `*.db` is
   git-ignored). Also run `alembic downgrade -1` and `upgrade head` once to prove it reverses.
4. **Carry the data through.** Update the ingest (`ingest.py`), the response models (`dashboard.py` or
   `api.py`) and the frontend types in `frontend/lib/api.ts`. A new field should be optional in the
   frontend type so an older API response still renders.
5. **Tests.** Extend the recorded fixture in `backend/tests/fixtures/sleeper_league.json` with a sample
   of the new field (including the missing/null case) and assert it end to end in
   `tests/test_api_connect.py`. The `engine` fixture builds tables from the models, so tests pass even if
   the migration is wrong; step 3 is what checks the migration.
6. Run the `run-checks` skill, then ship with the `ship-pr` skill.

## Rollout (what happens after the merge)

- **develop:** merging into `develop` runs `Migrate develop database` automatically (it watches
  `backend/migrations/**` and `db.py`), so the develop Neon branch stays at develop's schema.
- **production:** merging the release into `main` runs `Migrate database` automatically. It uses the
  direct (unpooled) connection string from the `DATABASE_URL_UNPOOLED` secret. Confirm with
  `gh run list --workflow "Migrate database" --limit 2`; run `gh workflow run "Migrate database"` only if
  it did not trigger. Use the `release-to-main` skill.
- **Order matters:** the app code that reads a new column ships in the same release as the migration. The
  migration runs on the main merge while the new API deploys, so reads of the new column must tolerate it
  being empty until the worker or a connect fills it (a streak, for example, appears after the next sync).
- Existing leagues only gain a new synced field after they are synced again (the worker does this about
  every 15 minutes for recently viewed leagues; locally, `POST /api/leagues/<id>/connect` re-syncs).

Never print, log or commit a connection string.
