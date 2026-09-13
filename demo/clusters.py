"""Deterministic creator clusters from observed commenter overlap.

Greedy weighted modularity (Clauset-Newman-Moore style) on the Jaccard graph. Small pools only
(hundreds of creators). A cluster means the channels' sampled commenters overlap more than chance
would suggest; it says nothing about viewer demographics.
"""
from collections import Counter
from statistics import median


def detect(ids, weights):
    """ids: creator ids; weights: {(a, b): w} with a < b. Returns lists of ids, largest first."""
    ids = sorted(ids)
    total = sum(w for w in weights.values() if w > 0)
    if total <= 0:
        return [[i] for i in ids]
    degree = Counter()
    between = {}
    for (a, b), w in weights.items():
        if w <= 0 or a == b:
            continue
        degree[a] += w
        degree[b] += w
    groups = {i: [i] for i in ids}
    strength = {i: degree[i] for i in ids}
    for (a, b), w in weights.items():
        if w > 0 and a != b:
            key = (min(a, b), max(a, b))
            between[key] = between.get(key, 0) + w
    m = total
    while True:
        best, best_gain = None, 1e-12
        for (a, b), w in sorted(between.items()):
            gain = w / m - strength[a] * strength[b] / (2 * m * m)
            if gain > best_gain:
                best, best_gain = (a, b), gain
        if best is None:
            break
        keep, gone = best
        groups[keep].extend(groups.pop(gone))
        strength[keep] += strength.pop(gone)
        merged = {}
        for (a, b), w in between.items():
            a2 = keep if a == gone else a
            b2 = keep if b == gone else b
            if a2 == b2:
                continue
            key = (min(a2, b2), max(a2, b2))
            merged[key] = merged.get(key, 0) + w
        between = merged
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g))


def summarize(groups, creators_by_id, jaccard):
    clusters = []
    for n, members in enumerate(groups):
        topics = Counter(creators_by_id[i]["community"] for i in members)
        ranked = sorted(members, key=lambda i: -creators_by_id[i]["commenter_count"])
        inside = [jaccard.get((min(a, b), max(a, b)), 0) for x, a in enumerate(members) for b in members[x + 1:]]
        topic_text = " + ".join(t for t, _ in topics.most_common(2))
        clusters.append({
            "id": "cluster-%d" % (n + 1),
            "members": ranked,
            "label": ("%s cluster" % topic_text) if len(members) > 1 else "%s (no strong cluster)" % creators_by_id[members[0]]["name"],
            "labelSource": "rule",
            "topics": dict(topics),
            "anchorCreators": [creators_by_id[i]["name"] for i in ranked[:3]],
            "medianInternalJaccard": median(inside) if inside else None,
        })
    return clusters
