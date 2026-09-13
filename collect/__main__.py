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

from . import aggregate, headline as headline_mod, youtube


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
    build.add_argument("--cpm", type=float, default=15.0, help="Modeled quote CPM; 0 uses a uniform --default-quote")
    build.add_argument("--default-quote", type=int, default=1000)
    build.add_argument("--restricted", help="Newline-separated brand names to redact; keep this file outside the repo")
    suggest = sub.add_parser("suggest", help="List @handles mentioned in collected descriptions (no quota)")
    suggest.add_argument("--min-channels", type=int, default=2)
    head = sub.add_parser("headline")
    head.add_argument("--aggregate", required=True)
    head.add_argument("--budgets", default="3000,6000,10000")
    head.add_argument("--audit-size", type=int, default=6)
    head.add_argument("--out")
    args = parser.parse_args(argv)

    if args.command == "headline":
        data = json.loads(Path(args.aggregate).read_text(encoding="utf-8"))
        result = headline_mod.headline(data, [float(b) for b in args.budgets.split(",")], args.audit_size)
        text = json.dumps(result, indent=1, ensure_ascii=False)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        audit = result["audit_biggest_by_subscribers"]
        print("biggest-%d roster duplicates %.1f%% of sampled commenters" % (len(audit["roster"]), 100 * audit["duplicated_fraction"]))
        for row in result["comparisons"]:
            vs = row["vs_top_subscribers"], row["vs_top_views"]
            print("$%-7g %-19s lift vs subs %6s  vs views %6s  (overlap share of gain vs views: %s)" % (
                row["budget"], row["objective"],
                "n/a" if vs[0]["lift"] is None else "%.1f%%" % (100 * vs[0]["lift"]),
                "n/a" if vs[1]["lift"] is None else "%.1f%%" % (100 * vs[1]["lift"]),
                "%.0f of %.0f" % (vs[1]["from_less_overlap"], vs[1]["from_less_overlap"] + vs[1]["from_bigger_audiences"])))
        return 0

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    db = youtube.connect(args.db)
    if args.command == "suggest":
        for row in aggregate.suggest_handles(db, args.min_channels):
            print("%s,?  # mentioned by %d channels; set a topic after checking the channel" % (row["handle"], row["mentioned_by_channels"]))
        return 0
    if args.command == "build":
        agg, report = aggregate.build(db, topic_title=args.title,
                                      eligible_topics=[t.strip() for t in args.eligible.split(",") if t.strip()] or None,
                                      max_comments_per_author=args.max_comments_per_author,
                                      gate_threshold=args.gate_threshold, restricted=load_restricted(args.restricted),
                                      cpm=args.cpm or None, default_quote=args.default_quote)
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
