"""Validation for commenter overlap: temporal stability and agreement with an external benchmark.

Neither proves commenters stand in for viewers. Stability shows the signal is not noise; benchmark agreement shows
it ranks creator pairs the way follower-based industry tools do.
"""
from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from itertools import combinations


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else None


def _jaccard(sets: dict[str, set[str]]) -> dict[tuple[str, str], float]:
    out = {}
    for a, b in combinations(sorted(sets), 2):
        union = len(sets[a] | sets[b])
        out[(a, b)] = len(sets[a] & sets[b]) / union if union else 0.0
    return out


def temporal_stability(db: sqlite3.Connection, channel_ids: set[str]) -> dict:
    """Split each channel's collected videos into older and newer halves and correlate pairwise Jaccard."""
    videos = defaultdict(list)
    for row in db.execute("SELECT v.video_id, v.channel_id, v.published_at FROM videos v "
                          "WHERE EXISTS (SELECT 1 FROM video_authors a WHERE a.video_id = v.video_id)"):
        if row["channel_id"] in channel_ids:
            videos[row["channel_id"]].append((row["published_at"] or "", row["video_id"]))
    eligible = {cid: sorted(v) for cid, v in videos.items() if len(v) >= 2}
    if len(eligible) < 3:
        return {"status": "unavailable", "reason": "Needs at least 3 channels with 2+ videos that have per-video commenter records."}
    halves = {"older": defaultdict(set), "newer": defaultdict(set)}
    half_of = {}
    for cid, vids in eligible.items():
        cut = len(vids) // 2
        for n, (_, vid) in enumerate(vids):
            half_of[vid] = (cid, "older" if n < cut else "newer")
    for row in db.execute("SELECT video_id, author_key FROM video_authors"):
        if row["video_id"] in half_of:
            cid, half = half_of[row["video_id"]]
            halves[half][cid].add(row["author_key"])
    older, newer = _jaccard(dict(halves["older"])), _jaccard(dict(halves["newer"]))
    pairs = sorted(set(older) & set(newer))
    rho = spearman([older[p] for p in pairs], [newer[p] for p in pairs])
    return {"status": "computed", "channels": len(eligible), "pairs": len(pairs), "spearman": rho,
            "note": "Rank agreement of pairwise commenter Jaccard between each channel's older and newer videos. "
                    "Shows stability, not viewer validity; some commenters appear in both halves."}


def _index(creators: list[dict]) -> dict[str, str]:
    index = {}
    for c in creators:
        for key in (c["id"], c.get("handle"), c["name"]):
            if key:
                index[str(key).strip().lower().lstrip("@")] = c["id"]
    return index


def benchmark(aggregate: dict, rows: list[dict]) -> dict:
    """rows: dicts with a, b, overlap (any monotone overlap measure from an external tool)."""
    from .aggregate import pair_stats
    from collections import Counter

    index = _index(aggregate["creators"])
    sizes: Counter = Counter()
    segments: Counter = Counter()
    for seg in aggregate["audience_segments"]:
        members = frozenset(seg["creators"])
        segments[members] += seg["count"]
        for cid in members:
            sizes[cid] += seg["count"]
    ours = pair_stats(dict(sizes), segments)
    names = {c["id"]: c["name"] for c in aggregate["creators"]}
    matched, unmatched = [], []
    for row in rows:
        a = index.get(str(row["a"]).strip().lower().lstrip("@"))
        b = index.get(str(row["b"]).strip().lower().lstrip("@"))
        try:
            external = float(str(row["overlap"]).strip().rstrip("%"))
        except ValueError:
            external = None
        if not a or not b or a == b or external is None:
            unmatched.append({"a": row["a"], "b": row["b"]})
            continue
        key = (min(a, b), max(a, b))
        matched.append({"a": names[a], "b": names[b], "external_overlap": external, "commenter_jaccard": ours[key]["jaccard"]})
    rho = spearman([m["external_overlap"] for m in matched], [m["commenter_jaccard"] for m in matched])
    return {"matched_pairs": len(matched), "unmatched": unmatched, "spearman": rho, "pairs": matched,
            "note": "Rank correlation between an external follower-based overlap measure and sampled commenter Jaccard. "
                    "An industry anchor, not ground truth. Report n alongside rho; below 20 pairs treat as indicative."}


def read_benchmark_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"a", "b", "overlap"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Benchmark CSV needs columns a,b,overlap (missing: %s)" % ", ".join(sorted(missing)))
        return list(reader)
