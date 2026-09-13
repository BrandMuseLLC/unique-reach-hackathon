"""Build the planner's observed aggregate, the overlap gate report and sponsor mentions.

Output matches demo/engine.py: `metadata`, `creators`, `audience_segments`. Segments are exact
channel-membership patterns with integer counts; no commenter keys leave the local database.
"""
from __future__ import annotations

import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
import math

from . import validation

SPONSOR_PATTERNS = [
    ("sponsor", re.compile(r"\b(?:sponsored by|thanks to|thank you to|brought to you by|in partnership with|partnered with)\s+"
                           r"([A-Z][\w&'+-]*(?:\s+[A-Z][\w&'+-]*){0,2})")),
    ("code", re.compile(r"\bcode\s+[A-Z0-9]{3,}\b[^.\n]{0,40}?\b(?:at|on|for)\s+([A-Z][\w&'+-]*(?:\s+[A-Z][\w&'+-]*){0,2})")),
]
DISCLOSURE = re.compile(r"(#ad\b|#sponsored\b|paid promotion|this video is sponsored|sponsored video)", re.I)
NOT_BRANDS = {"patreon", "patrons", "my patrons", "youtube", "everyone", "you", "all", "our", "my", "the", "all of you",
              "channel members", "members", "instagram", "twitter", "tiktok", "discord"}


RESTRICTED = "Restricted brand"
HANDLE = re.compile(r"(?<![\w.])@([A-Za-z0-9._-]{3,30})\b")


def modeled_quote(views: float, cpm: float) -> int:
    """Same rounding as the planner app's modeled quotes: nearest $250, at least $250."""
    return max(250, math.floor(views * cpm / 1000 / 250 + 0.5) * 250)


def restricted_match(brand: str, restricted: set[str]) -> bool:
    lowered = brand.lower()
    return any(re.search(r"\b%s\b" % re.escape(name), lowered) for name in restricted)


def redact(text: str, restricted: set[str] | None) -> str:
    for name in restricted or ():
        text = re.sub(r"\b%s\b" % re.escape(name), "[brand]", text, flags=re.I)
    return text


def sponsor_mentions(videos: list[dict], restricted: set[str] | None = None) -> dict:
    """Heuristic brand mentions in public descriptions. Evidence for review, never an automatic verdict.

    Names in `restricted` (loaded from a file kept outside the repo) are replaced before output, so
    client or pipeline brands never reach a committed aggregate.
    """
    restricted = {r.lower() for r in (restricted or set())}
    brands: dict[str, dict] = {}
    disclosed = 0
    for video in videos:
        text = video.get("description") or ""
        if DISCLOSURE.search(text):
            disclosed += 1
        seen = set()
        for kind, pattern in SPONSOR_PATTERNS:
            for match in pattern.finditer(text):
                brand = match.group(1).strip(" .,'")
                if brand.lower() in NOT_BRANDS or brand.lower().split()[0] in NOT_BRANDS or brand in seen:
                    continue
                if restricted_match(brand, restricted):
                    brand = RESTRICTED
                if brand in seen:
                    continue
                seen.add(brand)
                entry = brands.setdefault(brand, {"brand": brand, "videos": 0, "last_seen": None, "signals": set()})
                entry["videos"] += 1
                entry["signals"].add(kind)
                published = video.get("published_at")
                if published and (entry["last_seen"] is None or published > entry["last_seen"]):
                    entry["last_seen"] = published
    rows = [{**b, "signals": sorted(b["signals"])} for b in brands.values()]
    return {"brands": sorted(rows, key=lambda b: (-b["videos"], b["brand"])), "disclosed_videos": disclosed,
            "basis": "Pattern matches in public video descriptions; verify before excluding a creator."}


def pair_stats(sizes: dict[str, int], segments: Counter) -> dict[tuple[str, str], dict]:
    shared: Counter = Counter()
    for members, count in segments.items():
        for a, b in combinations(sorted(members), 2):
            shared[(a, b)] += count
    out = {}
    for a, b in combinations(sorted(sizes), 2):
        s = shared.get((a, b), 0)
        union = sizes[a] + sizes[b] - s
        out[(a, b)] = {"shared": s, "jaccard": s / union if union else 0.0}
    return out


def _segments(db: sqlite3.Connection, channel_ids: set[str], max_comments_per_author: int | None):
    by_author: dict[str, set[str]] = defaultdict(set)
    totals: Counter = Counter()
    for row in db.execute("SELECT channel_id, author_key, comments FROM authors"):
        if row["channel_id"] in channel_ids:
            by_author[row["author_key"]].add(row["channel_id"])
            totals[row["author_key"]] += row["comments"]
    dropped = 0
    segments: Counter = Counter()
    for author, members in by_author.items():
        if max_comments_per_author is not None and totals[author] > max_comments_per_author:
            dropped += 1
            continue
        segments[frozenset(members)] += 1
    return segments, dropped


def build(db: sqlite3.Connection, *, topic_title: str, eligible_topics: list[str] | None = None,
          default_quote: int = 1000, cpm: float | None = 15.0, max_comments_per_author: int | None = 200, gate_threshold: float = 0.015,
          campaign: dict | None = None, restricted: set[str] | None = None) -> tuple[dict, dict]:
    channels = {r["channel_id"]: dict(r) for r in db.execute("SELECT * FROM channels")}
    videos_by_channel: dict[str, list[dict]] = defaultdict(list)
    for r in db.execute("SELECT * FROM videos WHERE status IN ('done','comments_disabled','comments_hidden')"):
        videos_by_channel[r["channel_id"]].append(dict(r))
    segments, dropped = _segments(db, set(channels), max_comments_per_author)
    sizes: Counter = Counter()
    for members, count in segments.items():
        for cid in members:
            sizes[cid] += count
    comment_totals = Counter()
    for r in db.execute("SELECT channel_id, SUM(comments) AS n FROM authors GROUP BY channel_id"):
        comment_totals[r["channel_id"]] = r["n"]

    creators, skipped = [], []
    for cid, ch in sorted(channels.items(), key=lambda kv: kv[1]["title"].lower()):
        vids = [v for v in videos_by_channel.get(cid, []) if v["views"] is not None]
        if not sizes.get(cid) or not vids:
            skipped.append({"channel": ch["handle"] or ch["title"], "reason": "no collected commenters" if vids else "no collected videos"})
            continue
        recent = sorted(vids, key=lambda v: v["published_at"] or "", reverse=True)
        views = float(statistics.median(v["views"] for v in vids))
        creators.append({
            "id": cid, "name": ch["title"], "handle": ch["handle"], "community": ch["topic"],
            "views": views,
            "subscribers": ch["subscribers"] or 0,
            "cost": modeled_quote(views, cpm) if cpm else default_quote,
            "quote_basis": ("Modeled at $%g CPM on median recent views, rounded to $250; editable, not a creator rate card." % cpm) if cpm
                           else "Uniform $%d scenario assumption; replace with real quotes before any spend decision." % default_quote,
            "video_count": len(vids), "comment_count": int(comment_totals[cid]),
            "video_titles": [redact(v["title"], restricted) for v in recent[:3] if v["title"]],
            "sponsor_mentions": sponsor_mentions(recent, restricted),
        })
    kept = {c["id"] for c in creators}
    merged: Counter = Counter()
    for members, count in segments.items():
        if members & kept:
            merged[frozenset(members & kept)] += count

    topics = sorted({c["community"] for c in creators})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    metadata = {
        "kind": "observed",
        "title": "YouTube · %s · %d channels" % (topic_title, len(creators)),
        "source": "Collected by the BrandMuse hackathon team with YouTube Data API v3 (public top-level comments, last uploads).",
        "license": "Aggregate membership counts only; no comment text or commenter identifiers. YouTube API Services terms apply.",
        "data_date": now,
        "views_basis": "Median public view count across collected recent uploads; view events, not unique viewers.",
        "quote_basis": ("Modeled at $%g CPM on median recent views; editable in the planner." % cpm) if cpm else "Uniform scenario quote; editable in the planner.",
        "group_basis": "Editorial topic assigned in the seed list, not inferred audience demographics.",
        "subscriber_basis": "Largest by public subscriber count",
        "campaign": campaign or {
            "id": "home-coffee-case-study", "name": "Home coffee · countertop espresso launch",
            "category": "Home espresso and coffee gear",
            "audience": "Illustrative brief: a countertop-appliance brand launching a sub-$500 home espresso machine. Audience geography unverified.",
            "eligibleCategories": eligible_topics or topics,
        },
    }
    aggregate = {"metadata": metadata, "creators": creators,
                 "audience_segments": [{"creators": sorted(m), "count": n} for m, n in sorted(merged.items(), key=lambda kv: (-kv[1], sorted(kv[0])))]}

    kept_sizes = {cid: sizes[cid] for cid in kept}
    pairs = pair_stats(kept_sizes, merged)
    jaccards = [p["jaccard"] for p in pairs.values()]
    median_j = statistics.median(jaccards) if jaccards else 0.0
    names = {c["id"]: c["name"] for c in creators}
    sensitivity = []
    for threshold in (50, 100, 200, None):
        segs, drop = _segments(db, kept, threshold)
        s_sizes: Counter = Counter()
        for members, count in segs.items():
            for cid in members:
                s_sizes[cid] += count
        s_pairs = pair_stats(dict(s_sizes), segs)
        values = [p["jaccard"] for p in s_pairs.values()]
        sensitivity.append({"max_comments_per_author": threshold, "dropped_authors": drop,
                            "median_jaccard": statistics.median(values) if values else 0.0})
    ratios = {c["id"]: kept_sizes[c["id"]] / c["views"] for c in creators if c["views"]}
    ratio_median = statistics.median(ratios.values()) if ratios else 0
    report = {
        "channels": len(creators), "skipped_channels": skipped,
        "videos": sum(c["video_count"] for c in creators),
        "top_level_comments": sum(c["comment_count"] for c in creators),
        "unique_commenters": sum(merged.values()),
        "multi_channel_commenters": sum(n for m, n in merged.items() if len(m) > 1),
        "dropped_high_volume_authors": dropped,
        "pairs": len(pairs), "nonzero_pairs": sum(1 for p in pairs.values() if p["shared"]),
        "median_pair_jaccard": median_j,
        "gate": {"threshold": gate_threshold, "median_pair_jaccard": median_j, "pass": median_j >= gate_threshold,
                 "rule": "Below threshold: widen the seed list to adjacent coffee gear before switching verticals."},
        "top_pairs": [{"a": names[a], "b": names[b], **p} for (a, b), p in sorted(pairs.items(), key=lambda kv: -kv[1]["jaccard"])[:10]],
        "cleaning_sensitivity": sensitivity,
        "commenter_to_view_outliers": [{"creator": names[cid], "ratio_vs_median": r / ratio_median}
                                       for cid, r in sorted(ratios.items(), key=lambda kv: -kv[1])
                                       if ratio_median and (r / ratio_median > 4 or r / ratio_median < 0.25)],
        "temporal_stability": validation.temporal_stability(db, kept),
        "sponsor_brands": sorted({b["brand"] for c in creators for b in c["sponsor_mentions"]["brands"]}),
        "caveats": ["Commenters are a selected subset of viewers; overlap is sampled commenter overlap, not unique viewers.",
                    "High-volume author filtering is a spam heuristic, not bot detection.",
                    "Delete or refresh the local collection database within 30 days."],
    }
    return aggregate, report


def suggest_handles(db: sqlite3.Connection, min_channels: int = 1) -> list[dict]:
    """@handles mentioned in collected descriptions that are not yet in the pool. Costs no API quota."""
    known = {(r["handle"] or "").lower().lstrip("@") for r in db.execute("SELECT handle FROM channels")}
    mentions: dict[str, set[str]] = defaultdict(set)
    spelling: dict[str, str] = {}
    for row in db.execute("SELECT channel_id, description FROM videos ORDER BY video_id"):
        for match in HANDLE.finditer(row["description"] or ""):
            handle = match.group(1).rstrip("._-")
            if handle.lower() not in known:
                spelling.setdefault(handle.lower(), handle)
                mentions[handle.lower()].add(row["channel_id"])
    rows = [{"handle": "@" + spelling[h], "mentioned_by_channels": len(chans)} for h, chans in mentions.items() if len(chans) >= min_channels]
    return sorted(rows, key=lambda r: (-r["mentioned_by_channels"], r["handle"]))
