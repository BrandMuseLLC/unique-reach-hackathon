#!/usr/bin/env python3
"""Why each creator in an uploaded list did or did not make it onto the overlap map.

    python3 scripts/roster-report.py                 # newest dataset built from a list
    python3 scripts/roster-report.py data/analyses/<dataset>.json

Prints one line per creator with the sampled commenter count and the planner's verdict, then the handles that were
not found on YouTube. Use it to prune a CSV before a demo: drop the "not found" rows, and know which channels will
show as "Not measurable" (comments off or too few public commenters).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def newest_roster_dataset():
    folder = ROOT / "data" / "analyses"
    candidates = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.exists() else []
    for path in candidates:
        if path.name.endswith(".report.json"):
            continue
        try:
            if json.loads(path.read_text()).get("metadata", {}).get("roster"):
                return path
        except (OSError, ValueError):
            continue
    return None


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else newest_roster_dataset()
    if not path or not path.exists():
        sys.exit("No dataset built from a creator list yet. Upload a list in Muse first, or pass a dataset path.")
    data = json.loads(path.read_text())
    meta = data.get("metadata", {})
    roster = meta.get("roster") or {}
    floor = int(meta.get("min_commenters", 0))
    sizes = {}
    for seg in data.get("audience_segments") or []:
        for cid in seg.get("creators", []):
            sizes[cid] = sizes.get(cid, 0) + int(seg.get("count", 0))
    creators = [{**c, "commenter_count": c.get("commenter_count", sizes.get(c["id"], 0))} for c in data.get("creators", [])]
    for e in (data.get("crossplatform") or {}).get("external", []):
        creators.append({**e, "commenter_count": None, "community": e.get("topic")})
    print("%s: %d creators on the map (list had %d), measurable floor %d sampled commenters\n" % (path.name, len(creators), roster.get("requested", len(creators)), floor))
    print("%-34s %-10s %-18s %8s  %s" % ("creator", "platform", "topic", "sampled", "verdict"))
    for c in sorted(creators, key=lambda c: -(c.get("commenter_count") or 0)):
        sampled = c.get("commenter_count")
        platform = c.get("platform") or "youtube"
        if sampled is None:
            verdict = "estimated from an Upriver audience profile" if c.get("audience") else "assumed (no Upriver audience profile)"
        elif sampled == 0:
            verdict = "NOT MEASURABLE: no public comments sampled (comments off or no recent uploads)"
        elif sampled < floor:
            verdict = "NOT MEASURABLE: fewer than %d sampled commenters" % floor
        else:
            verdict = "measured"
        print("%-34s %-10s %-18s %8s  %s" % ((c.get("name") or c.get("handle") or c["id"])[:34], platform, (c.get("community") or "")[:18], "-" if sampled is None else sampled, verdict))
    missing = roster.get("missing") or []
    print("\nNot found on YouTube (%d): %s" % (len(missing), ", ".join(missing) if missing else "none"))
    thin = [c for c in creators if c.get("commenter_count") is not None and c["commenter_count"] < floor]
    print("Not measurable (%d): %s" % (len(thin), ", ".join((c.get("name") or c["id"]) for c in thin) if thin else "none"))


if __name__ == "__main__":
    main()
