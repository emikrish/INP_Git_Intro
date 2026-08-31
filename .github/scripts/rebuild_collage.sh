#!/usr/bin/env bash
# Rebuild collage.jpg from photos/ and push it to the default branch.
#
# Invoked from two places, because one trigger genuinely is not enough:
#
#   - update-collage.yml, on a push to photos/** by a person.
#   - auto-merge-photo.yml, right after the bot merges a photo. A push made with
#     GITHUB_TOKEN never raises a push event, by design, so relying on the push
#     trigger alone would mean the collage silently never rebuilt for the one
#     case that matters most.
#
# The collage is fully derived from photos/, so losing a push race is resolved by
# rebuilding against the new tip rather than by rebasing a binary file.
set -euo pipefail

BRANCH="${COLLAGE_BRANCH:-master}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3; do
  echo "::group::Attempt $attempt"
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"

  python code/make_collage.py

  # Staged, then compared: `git diff` alone ignores an untracked collage.jpg and
  # would silently never commit the first one.
  git add collage.jpg
  if git diff --cached --quiet -- collage.jpg; then
    echo "collage.jpg is already up to date."
    exit 0
  fi

  git commit -m "Rebuild collage"

  if git push origin "HEAD:$BRANCH"; then
    echo "Pushed the rebuilt collage."
    exit 0
  fi
  echo "Push rejected, $BRANCH moved. Rebuilding against the new tip."
  echo "::endgroup::"
done

echo "::error::Could not push the rebuilt collage after 3 attempts."
exit 1
