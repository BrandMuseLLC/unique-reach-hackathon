"""Collect a YouTube vertical and build the planner aggregate.

    export YOUTUBE_API_KEYS=key1,key2          # server-side only; never commit or paste in chat
    python3 -m collect resolve  --seeds collect/seeds/home-coffee.csv
    python3 -m collect videos   --per-channel 10
    python3 -m collect comments --max-per-video 500
    python3 -m collect build    --out data/home-coffee-aggregate.json --report data/home-coffee-report.json \
                                --restricted ~/.config/brandmuse/restricted-names.txt

Every step resumes from data/collection.sqlite. Quota errors rotate keys, then stop cleanly.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import aggregate, youtube


def load_restricted(path: str | None) -> set[str]:
    if not path:
        return set()
    lines = Path(path).expanduser().read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m collect")
    parser.add_argument("--db", default="data/collection.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--seeds", required=True)
    videos = sub.add_parser("videos")
    videos.add_argument("--per-channel", type=int, default=10)
    comments = sub.add_parser("comments")
    comments.add_argument("--max-per-video", type=int, default=500)
    build = sub.add_parser("build")
    build.add_argument("--out", required=True)
    build.add_argument("--report", required=True)
    build.add_argument("--title", default="home coffee")
    build.add_argument("--eligible", default="", help="Comma-separated topics eligible for the case study (default: all)")
    build.add_argument("--max-comments-per-author", type=int, default=200)
    build.add_argument("--gate-threshold", type=float, default=0.015)
    build.add_argument("--restricted", help="Newline-separated brand names to redact; keep this file outside the repo")
    args = parser.parse_args(argv)

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    db = youtube.connect(args.db)
    if args.command == "build":
        agg, report = aggregate.build(db, topic_title=args.title,
                                      eligible_topics=[t.strip() for t in args.eligible.split(",") if t.strip()] or None,
                                      max_comments_per_author=args.max_comments_per_author,
                                      gate_threshold=args.gate_threshold, restricted=load_restricted(args.restricted))
        for path, payload in ((args.out, agg), (args.report, report)):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        gate = report["gate"]
        print("channels=%d commenters=%d multi-channel=%d median-jaccard=%.4f gate=%s" % (
            report["channels"], report["unique_commenters"], report["multi_channel_commenters"],
            gate["median_pair_jaccard"], "PASS" if gate["pass"] else "FAIL"))
        return 0

    client = youtube.Client(os.environ.get("YOUTUBE_API_KEYS", "").split(","))
    try:
        if args.command == "resolve":
            result = youtube.resolve_channels(db, client, youtube.read_seeds(args.seeds))
        elif args.command == "videos":
            result = {"videos_added": youtube.list_videos(db, client, args.per_channel)}
        else:
            result = youtube.collect_comments(db, client, args.max_per_video)
    except youtube.QuotaExhausted as exc:
        print(str(exc), file=sys.stderr)
        result = {"stopped": "quota"}
    print(json.dumps({**result, "quota_units_by_key": client.units}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
