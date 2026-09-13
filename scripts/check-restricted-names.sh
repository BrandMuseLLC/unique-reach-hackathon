#!/usr/bin/env bash
# Fails if any restricted brand name appears in tracked files or in commits about to be pushed.
# The name list lives outside the repo so the names themselves are never committed.
#   RESTRICTED_NAMES_FILE=~/.config/brandmuse/restricted-names.txt scripts/check-restricted-names.sh
# Install as a pre-push hook:  ln -s ../../scripts/check-restricted-names.sh .git/hooks/pre-push
set -euo pipefail

list="${RESTRICTED_NAMES_FILE:-$HOME/.config/brandmuse/restricted-names.txt}"
if [[ ! -f "$list" ]]; then
  echo "restricted-names: no list at $list; create it (one name per line) before pushing." >&2
  exit 1
fi

patterns="$(mktemp)"
trap 'rm -f "$patterns"' EXIT
grep -v '^[[:space:]]*#' "$list" | sed '/^[[:space:]]*$/d' > "$patterns"
if [[ ! -s "$patterns" ]]; then
  echo "restricted-names: $list is empty." >&2
  exit 1
fi

root="$(git rev-parse --show-toplevel)"
cd "$root"
status=0
if git grep -I -n -i -w -F -f "$patterns" -- . ':!package-lock.json'; then
  echo "restricted-names: tracked files contain a restricted name (matches above)." >&2
  status=1
fi
if git log --format=%B "@{upstream}..HEAD" 2>/dev/null | grep -i -w -F -f "$patterns" >/dev/null; then
  echo "restricted-names: an unpushed commit message contains a restricted name." >&2
  status=1
fi
[[ $status -eq 0 ]] && echo "restricted-names: clean ($(wc -l < "$patterns" | tr -d ' ') names checked)."
exit $status
