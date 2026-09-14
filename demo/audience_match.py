"""Audience profile match: how alike two creators' audiences look, from Upriver's audience demographics.

This is an estimate of *possible* overlap, not shared followers: two audiences with the same countries, gender mix
and age range could overlap; two very different profiles almost certainly don't overlap much.

Upriver's audience block (GET /v1/creators?include=audience), as observed live on 2026-09-14:
  {"status": "limited_coverage", "description": "...",
   "gender": {"value": "male", "percentage": 72, "confidence": "high"},
   "age": {"min_age": 25, "max_age": 44, "segments": [{"min_age": 25, "max_age": 34, "percentage": 75}], "confidence": "high"},
   "geography": {"countries": [{"country": "GB", "country_name": "United Kingdom"}], "international": true, "confidence": "low"},
   "languages": {"value": "English", "confidence": "high"}}
Countries may come without percentages; then listed countries share the audience equally. Each part's weight is scaled by
Upriver's confidence for it.
"""

WEIGHTS = {"geography": 0.4, "gender": 0.2, "age": 0.2, "language": 0.2}
CONFIDENCE = {"high": 1.0, "medium": 0.7, "low": 0.4}
COVERED = {"full_coverage", "partial_coverage", "limited_coverage"}


def _confidence(part):
    return CONFIDENCE.get(str((part or {}).get("confidence") or "").lower(), 1.0) if isinstance(part, dict) else 1.0


def profile(block):
    """Normalize an Upriver audience block into comparable parts; None when there is no usable coverage."""
    if not isinstance(block, dict) or block.get("status") not in COVERED:
        return None
    out = {"status": block.get("status"), "confidence": {}}
    if isinstance(block.get("description"), str) and block["description"].strip():
        out["description"] = block["description"].strip()[:600]
    geography = block.get("geography") if isinstance(block.get("geography"), dict) else {}
    countries = [r for r in (geography.get("countries") or []) if isinstance(r, dict) and r.get("country")]
    shares = {}
    with_pct = [r for r in countries if isinstance(r.get("percentage"), (int, float))]
    if with_pct:
        for row in with_pct:
            shares[str(row["country"]).upper()] = shares.get(str(row["country"]).upper(), 0.0) + max(float(row["percentage"]), 0.0) / 100
    elif countries:
        for row in countries:  # no percentages: listed countries split the audience equally
            shares[str(row["country"]).upper()] = 1.0 / len(countries)
    if shares:
        total = sum(shares.values())
        out["countries"] = {k: v / total for k, v in shares.items()} if total > 1 else shares
        out["country_names"] = {str(r["country"]).upper(): r.get("country_name") or str(r["country"]).upper() for r in countries}
        out["confidence"]["geography"] = _confidence(geography)
        out["countries_estimated"] = not with_pct
    gender = block.get("gender") if isinstance(block.get("gender"), dict) else {}
    if gender.get("value") in ("female", "male") and isinstance(gender.get("percentage"), (int, float)):
        share = max(min(float(gender["percentage"]), 100.0), 0.0) / 100
        out["female_share"] = share if gender["value"] == "female" else 1 - share
        out["confidence"]["gender"] = _confidence(gender)
    age = block.get("age") if isinstance(block.get("age"), dict) else {}
    if isinstance(age.get("min_age"), (int, float)) and isinstance(age.get("max_age"), (int, float)) and age["max_age"] >= age["min_age"]:
        out["age"] = (float(age["min_age"]), float(age["max_age"]))
        out["confidence"]["age"] = _confidence(age)
    languages = block.get("languages") if isinstance(block.get("languages"), dict) else {}
    if isinstance(languages.get("value"), str) and languages["value"].strip():
        out["language"] = languages["value"].strip().lower()
        out["confidence"]["language"] = _confidence(languages)
    return out if any(k in out for k in ("countries", "female_share", "age", "language")) else None


def summary(p):
    if not p:
        return "No audience data from Upriver"
    parts = []
    if p.get("countries"):
        top = sorted(p["countries"].items(), key=lambda kv: -kv[1])[:2]
        if p.get("countries_estimated"):
            parts.append("mainly " + " / ".join(p.get("country_names", {}).get(c, c) for c, _ in top))
        else:
            parts.append(" · ".join("%s %d%%" % (c, round(s * 100)) for c, s in top))
    if "female_share" in p:
        f = p["female_share"]
        parts.append("%d%% %s" % (round(max(f, 1 - f) * 100), "female" if f >= 0.5 else "male"))
    if p.get("age"):
        parts.append("ages %d–%d" % p["age"])
    if p.get("language"):
        parts.append(p["language"].title())
    return ", ".join(parts)


def match(a, b):
    """0-1 similarity of two normalized profiles, using only the parts both have; None when nothing is comparable."""
    if not a or not b:
        return None
    parts = {}
    if a.get("countries") and b.get("countries"):
        # Histogram intersection: countries a creator's top list doesn't mention count as no shared share.
        parts["geography"] = sum(min(a["countries"].get(c, 0.0), b["countries"].get(c, 0.0)) for c in set(a["countries"]) | set(b["countries"]))
    if "female_share" in a and "female_share" in b:
        parts["gender"] = 1 - abs(a["female_share"] - b["female_share"])
    if a.get("age") and b.get("age"):
        (a0, a1), (b0, b1) = a["age"], b["age"]
        inter = max(0.0, min(a1, b1) - max(a0, b0))
        union = max(a1, b1) - min(a0, b0)
        parts["age"] = inter / union if union > 0 else (1.0 if a0 == b0 else 0.0)
    if a.get("language") and b.get("language"):
        parts["language"] = 1.0 if a["language"] == b["language"] else 0.0
    if not parts:
        return None
    # Each part counts in proportion to its weight and the lower of the two creators' confidence for it.
    weights = {k: WEIGHTS[k] * min(a.get("confidence", {}).get(k, 1.0), b.get("confidence", {}).get(k, 1.0)) for k in parts}
    weight = sum(weights.values())
    score = sum(weights[k] * v for k, v in parts.items()) / weight
    return {"match": round(min(max(score, 0.0), 1.0), 4), "parts": {k: round(v, 4) for k, v in parts.items()},
            "basis": sorted(parts), "complete": len(parts) == len(WEIGHTS)}
