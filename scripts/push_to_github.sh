#!/usr/bin/env bash
# Requires the user to create an empty GitHub repo first and authenticate git normally.
set -euo pipefail
REPO="${1:-Shtenco/timeweb_synergy_retry_storm_lab}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -d .git ]] || { echo 'ERROR: .git not found (restore from the .bundle first)' >&2; exit 2; }
if git remote get-url origin >/dev/null 2>&1; then
  echo 'Existing origin:';git remote get-url origin
else
  git remote add origin "https://github.com/${REPO}.git"
fi
git push --set-upstream origin main
printf 'Published: https://github.com/%s\n' "$REPO"
