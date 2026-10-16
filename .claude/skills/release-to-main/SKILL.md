---
name: release-to-main
description: Release develop to main (production) the way this repo requires - release issue, hotfix branch carrying develop's exact tree, squash merge, manual issue close, then verify the automatic production migration, the worker and the live endpoints. Use when the user says to release, ship to production, or merge develop into main.
---

# Release develop to main

Only `develop` goes into `main`, and only through a release PR. Squash merging leaves `main` with a
commit `develop` does not contain, so a plain `develop` -> `main` PR conflicts after the first release.
Later releases therefore carry develop's exact files. CONTRIBUTING.md "Releases" is the source of truth.

Releasing is outward-facing (production), so only start when the user has asked for it.

## Before

1. `git fetch`, then confirm `develop` is green: `gh run list --branch develop --workflow CI --limit 1`.
   If it is still running, wait (`gh run watch <id> --exit-status`).
2. Pick the version from the last release (`git log --oneline origin/main -3` shows `chore: release vX.Y.Z`):
   new features bump the minor, fixes only bump the patch.
3. Check whether the release has database migrations (`git diff --stat origin/main origin/develop -- backend/migrations`).
   Production migrates itself when `main` changes `backend/migrations/**` or `db.py`.

## Release

1. `gh issue create --title "Release vX.Y.Z" --body "<what ships, and which migrations>"`.
2. `git checkout -b hotfix/release-vX-Y-Z origin/main`
3. `git read-tree -u --reset origin/develop`, then `git commit -m "chore: release vX.Y.Z"` (end with the
   co-author line). `git diff origin/develop` must be empty.
4. `git push -u origin hotfix/release-vX-Y-Z`, then
   `gh pr create --base main --title "chore: release vX.Y.Z" --body "Closes #<issue> ..."`.
5. Wait for the required checks (Backend, Frontend, PR policy, Secret scan, Pre-commit). Vercel checks
   are not required; if they fail with "Deployment rate limited" the free plan's daily limit is hit.
6. `gh pr merge <pr> --squash --delete-branch`. A local "not possible to fast-forward" message after the
   merge is harmless; check `git log origin/main -1`.
7. Close the issue by hand: `gh issue close <n> -c "Released in vX.Y.Z (#<pr>)."` (GitHub only auto-closes on
   merges into `develop`).
8. `git checkout develop && git pull`. If `frontend/tsconfig.json` blocks the checkout, a build rewrote it:
   `git checkout -- frontend/tsconfig.json`.

## After (verify, do not assume)

- **Migrations:** `gh run list --workflow "Migrate database" --limit 2` shows a successful run for the
  merge. Run it by hand with `gh workflow run "Migrate database"` only if it did not trigger.
- **Worker:** `gh variable list` shows `WORKER_ENABLED`. Setting it is a production change, so tell the
  user first. `gh workflow run Worker` runs one batch; check the log for `worker cycle: enqueued N, ran N`.
- **Live endpoints:** web https://web-cole-b6ee.vercel.app and API https://api-cole-b6ee.vercel.app
  (`/health`, `/health/db`). For data, compare the production standings with Sleeper's rosters.
- **Deployment:** `gh api repos/ColeRowellLove/sleeper-fantasy-assistant/commits/main/status` shows the
  Vercel states. If both say "rate limited", production still serves the previous version; say so plainly
  and do not report the release as live.
- Release notes are drafted by Release Drafter from PR titles; publishing the draft tags the release.

Never print or commit connection strings; they live in GitHub secrets and Vercel env vars only.
