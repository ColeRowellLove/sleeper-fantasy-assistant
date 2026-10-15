#!/usr/bin/env bash
# Commit, push, open a PR into develop, wait for CI, and squash merge.
# usage: scripts/ship-pr.sh <issue-number> "<conventional commit title>" "<PR summary>"
# Run from a feature/bugfix/chore/docs branch AFTER running the code-review skill.
set -eo pipefail

ISSUE=${1:?issue number required}
TITLE=${2:?conventional commit title required}
SUMMARY=${3:?PR summary required}

BRANCH=$(git branch --show-current)
case "$BRANCH" in
  feature/* | bugfix/* | chore/* | docs/* | refactor/* | test/*) ;;
  *) echo "Branch '$BRANCH' must start with feature/ bugfix/ chore/ docs/ refactor/ or test/" >&2; exit 1 ;;
esac

git add -A
git commit -q -m "$TITLE

Closes #$ISSUE

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push -q -u origin "$BRANCH"

PR=$(gh pr create --base develop --title "$TITLE" --body "$SUMMARY

Closes #$ISSUE.

🤖 Generated with [Claude Code](https://claude.com/claude-code)" | grep -oE '[0-9]+$')
echo "Opened PR #$PR"

# checks appear a few seconds after the PR is created
until [ -n "$(gh pr checks "$PR" 2>/dev/null)" ]; do sleep 5; done
gh pr checks "$PR" --watch

# never use --admin: CI must be green
gh pr merge "$PR" --squash --delete-branch

git checkout -q develop
git pull -q origin develop
git branch -D "$BRANCH" > /dev/null
echo "Issue #$ISSUE: $(gh issue view "$ISSUE" --json state -q .state)"
