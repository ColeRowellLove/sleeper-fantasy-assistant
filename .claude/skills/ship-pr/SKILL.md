---
name: ship-pr
description: Ship a change through this repo's required workflow - issue, typed branch off develop, local checks, code review, PR into develop, green CI, squash merge. Use whenever you finish a change and need to open or merge a PR here.
---

# Ship a PR

Follow CLAUDE.md "Workflow (required)". Steps:

1. **Issue first.** Every PR has exactly one issue. Find or create it (`gh issue create`) before coding.
   Never bundle two issues in one PR.
2. **Branch from `develop`** with a type prefix: `feature/`, `bugfix/`, `chore/`, `docs/`,
   `refactor/`, `test/`. Never commit to `develop` or `main` directly.
3. **Run the checks** with the `run-checks` skill. Everything must pass locally.
4. **Review before pushing.** Run the `code-review` skill on the diff and fix its findings; also
   `a11y-enforcer:a11y-check` for UI changes and `security-review` for auth, user input, secrets or
   external requests. Frontend changes need accessibility tests, and the Screenshots workflow's comment on the PR must be read (phone first) before merging; fix any layout problem it reports.
5. **Ship** with `scripts/ship-pr.sh <issue> "<conventional title>" "<summary>"`. It commits,
   pushes, opens the PR into `develop`, waits for CI and squash merges. If CI fails, read the log
   (`gh run view --log-failed`), fix on the same branch and push again. Never `--admin`, never skip hooks.
6. **Releases** are the only PRs into `main`: a `develop` -> `main` PR, squash merged after CI is green.

Do not commit secrets. Use the noreply email for commits (`git config user.email`).
