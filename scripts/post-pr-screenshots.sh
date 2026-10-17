#!/usr/bin/env bash
# Publish a folder of screenshots to the branch screenshots/pr-<n> and keep one comment on the
# pull request that shows them. Run by the Screenshots workflow; needs GH_TOKEN and GITHUB_REPOSITORY.
set -euo pipefail

dir=$1
pr=$2
branch="screenshots/pr-${pr}"
repo=${GITHUB_REPOSITORY:?}
marker="<!-- pr-screenshots -->"

shopt -s nullglob
images=("$dir"/*.png)
if [ ${#images[@]} -eq 0 ]; then
  echo "no screenshots to post"
  exit 0
fi

# one orphan commit holding just these pictures; the branch is deleted when the PR closes
work=$(mktemp -d)
cp "${images[@]}" "$work"/
[ -f "$dir/layout-problems.txt" ] && cp "$dir/layout-problems.txt" "$work"/
git -C "$work" init -q -b "$branch"
git -C "$work" config user.name "github-actions[bot]"
git -C "$work" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git -C "$work" add -A
git -C "$work" commit -q -m "Screenshots for #${pr}"
git -C "$work" push -q -f "https://x-access-token:${GH_TOKEN}@github.com/${repo}.git" "HEAD:refs/heads/${branch}"
sha=$(git -C "$work" rev-parse HEAD)
base="https://raw.githubusercontent.com/${repo}/${sha}"

body="${marker}"$'\n'"### Screenshots (sample league, made-up data)"$'\n\n'
body+="Phone (390 px) and desktop (1280 px), light theme; the top of each page. Dark theme and the full set are in the run's \`frontend-screenshots\` artifact."$'\n\n'
if [ -f "$work/layout-problems.txt" ] && [ -n "$(tr -d '[:space:]' < "$work/layout-problems.txt")" ]; then
  body+="<details><summary>Layout problems found at phone width</summary>"$'\n\n'
  body+='```'$'\n'"$(cat "$work/layout-problems.txt")"$'\n''```'$'\n\n'"</details>"$'\n\n'
fi
for mobile in "$dir"/*-mobile-light.png; do
  page=$(basename "$mobile" -mobile-light.png)
  body+="<details><summary><b>${page}</b></summary>"$'\n\n'
  body+="| Phone | Desktop |"$'\n'"| --- | --- |"$'\n'
  body+="| <img src=\"${base}/${page}-mobile-light.png\" width=\"260\"> | <img src=\"${base}/${page}-desktop-light.png\" width=\"520\"> |"$'\n\n'
  body+="</details>"$'\n\n'
done

existing=$(gh api "repos/${repo}/issues/${pr}/comments" --paginate \
  --jq ".[] | select(.body | startswith(\"${marker}\")) | .id" || true)
existing=${existing%%$'\n'*} # the first match, without a pipe that pipefail would trip on
if [ -n "$existing" ]; then
  gh api -X PATCH "repos/${repo}/issues/comments/${existing}" -f body="$body" >/dev/null
else
  gh api "repos/${repo}/issues/${pr}/comments" -f body="$body" >/dev/null
fi
echo "posted screenshots for #${pr}"
