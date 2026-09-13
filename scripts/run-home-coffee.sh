#!/usr/bin/env bash
# One command from API keys to a served home-coffee dataset. Safe to rerun: every step resumes.
#   export YOUTUBE_API_KEYS=key1,key2
#   scripts/run-home-coffee.sh            # collect, build, gate, headline
#   scripts/run-home-coffee.sh --serve    # ...then start the app on the collected data
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

: "${YOUTUBE_API_KEYS:?Set YOUTUBE_API_KEYS (comma-separated) in this shell; never commit or paste keys.}"
restricted="${RESTRICTED_NAMES_FILE:-$HOME/.config/brandmuse/restricted-names.txt}"
[[ -f "$restricted" ]] || { echo "Create $restricted (one restricted brand per line) before building." >&2; exit 1; }
py="${PYTHON:-python3}"
seeds="${SEEDS:-collect/seeds/home-coffee.csv}"
out=data

"$py" -m collect resolve --seeds "$seeds"
"$py" -m collect videos --per-channel "${VIDEOS_PER_CHANNEL:-10}"
"$py" -m collect comments --max-per-video "${COMMENTS_PER_VIDEO:-500}" || echo "Comment collection stopped early (see above); building from what was collected. Rerun later to resume." >&2
"$py" -m collect build --out "$out/home-coffee-aggregate.json" --report "$out/home-coffee-report.json" --restricted "$restricted"
"$py" -m collect headline --aggregate "$out/home-coffee-aggregate.json" --out "$out/home-coffee-headline.json"
echo
echo "Channels worth adding (mentioned by 2+ collected channels):"
"$py" -m collect suggest --min-channels 2 | head -15

if [[ "${1:-}" == "--serve" ]]; then
  [[ -d dist ]] || npm run build
  MUSE_DATASET=observed MUSE_OBSERVED_DATA="$out/home-coffee-aggregate.json" AUTH_MODE=local CAMPAIGN_STORE=local \
    exec "$py" -m uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8033}"
fi
