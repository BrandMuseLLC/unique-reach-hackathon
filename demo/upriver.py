"""Upriver "Find similar creators" (beta) for lookalike discovery on YouTube, Instagram and TikTok.

Follows the vendor contract and BrandMuse's billing rules:
- exactly one anchor per request (channel_url here);
- a timed-out request is treated as billed and is never retried; 5xx is retried once (the work did not complete);
- credits are reserved at the worst-case estimate (4 per request + 2 per returned row) before calling, against a
  per-server-session cap, and every call that reached the vendor is written to a local attribution ledger;
- an empty result list is only "no similar creators" when incomplete_results is false.
Similarity is Upriver's modeled niche and audience fit. It is not measured audience overlap.
"""
import json
import os
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__:
    from .engine import PlanError
else:
    from engine import PlanError

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "upriver-ledger.jsonl"
CACHE = ROOT / "data" / "upriver-cache.json"
PLATFORMS = ("youtube", "instagram", "tiktok")
PER_REQUEST, PER_ROW = 4, 2

_lock = threading.Lock()
_spent = 0


def settings():
    return {"key": os.environ.get("UPRIVER_API_KEY", "").strip(),
            "url": os.environ.get("UPRIVER_API_URL", "https://api.upriver.ai").rstrip("/"),
            "cap": int(os.environ.get("UPRIVER_MAX_CREDITS", "150"))}


def status():
    cfg = settings()
    with _lock:
        spent = _spent
    return {"configured": bool(cfg["key"]), "creditsReservedThisSession": spent, "creditCap": cfg["cap"],
            "creditsRemaining": max(cfg["cap"] - spent, 0), "costPerLookup": PER_REQUEST + PER_ROW * 10}


def estimate(limit):
    return PER_REQUEST + PER_ROW * limit


def _record(entry):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}) + "\n")


def _cache_get(key):
    try:
        return json.loads(CACHE.read_text()).get(key)
    except (OSError, ValueError):
        return None


def _cache_put(key, value):
    try:
        data = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        data = {}
    data[key] = value
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data))


def _reserve(credits):
    global _spent
    cap = settings()["cap"]
    with _lock:
        if _spent + credits > cap:
            raise PlanError("Upriver credit cap for this session reached (%d of %d). Raise UPRIVER_MAX_CREDITS to continue." % (_spent, cap))
        _spent += credits


def _release(credits):
    global _spent
    with _lock:
        _spent = max(_spent - credits, 0)


def _rows(payload, anchor_platform):
    out = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        channels = [c for c in (row.get("channels") or []) if isinstance(c, dict)]
        if not channels:
            continue
        lead = channels[0]  # the vendor puts the channel that qualified the match first
        similarity = row.get("similarity") if isinstance(row.get("similarity"), dict) else {}
        score = row.get("score", similarity.get("score"))
        out.append({
            "creatorId": row.get("creator_id"),
            "name": row.get("name") or row.get("display_name") or lead.get("handle") or lead.get("url"),
            "platform": str(lead.get("platform") or "").lower(),
            "handle": lead.get("handle"),
            "url": lead.get("url"),
            "followers": lead.get("subscriber_count") or lead.get("follower_count"),
            "followerBucket": lead.get("follower_bucket"),
            "score": float(score) if isinstance(score, (int, float)) else None,
            "otherChannels": [{"platform": str(c.get("platform") or "").lower(), "handle": c.get("handle"), "url": c.get("url")} for c in channels[1:4]],
        })
    return out


def similar(channel_url, platforms=PLATFORMS, limit=10, transport=None):
    """Lookalike creators for one channel. Returns rows plus billing facts; cached so repeats cost nothing."""
    cfg = settings()
    if not cfg["key"]:
        raise PlanError("Add UPRIVER_API_KEY to the server's .env to use Upriver.")
    platforms = [p for p in platforms if p in PLATFORMS] or list(PLATFORMS)
    limit = max(1, min(int(limit), 10))
    cache_key = json.dumps([channel_url, sorted(platforms), limit])
    cached = _cache_get(cache_key)
    if cached:
        return {**cached, "cached": True, "creditsCharged": 0}
    worst = estimate(limit)
    _reserve(worst)
    body = {"channel_url": channel_url, "platforms": platforms, "limit": limit}
    req = Request(cfg["url"] + "/v1/creators/similar", data=json.dumps(body).encode(), method="POST",
                  headers={"x-api-key": cfg["key"], "Content-Type": "application/json", "Accept": "application/json"})
    payload, attempts = None, 0
    while payload is None:
        try:
            if transport:
                payload = transport(req)
            else:
                with urlopen(req, timeout=60) as response:  # nosec B310 - fixed vendor host from config
                    payload = json.load(response)
        except HTTPError as exc:
            if exc.code >= 500 and attempts == 0:
                attempts += 1  # the vendor asks for 5xx retries; the work did not complete, so it was not billed
                time.sleep(1.5)
                continue
            if exc.code >= 500:
                _release(worst)
            _record({"endpoint": "v1/creators/similar", "anchor": channel_url, "status": exc.code,
                     "possibly_billed": exc.code < 500, "credits_estimate": worst if exc.code < 500 else 0})
            raise PlanError("Upriver returned HTTP %d for similar creators." % exc.code) from None
        except (TimeoutError, OSError) as exc:
            if isinstance(exc, URLError) and not isinstance(getattr(exc, "reason", None), TimeoutError):
                _release(worst)  # never reached the vendor, so nothing was billed
                raise PlanError("Could not reach Upriver.") from None
            # A timeout is spend, not a free failure: the vendor completes and bills the work. Never retry it.
            _record({"endpoint": "v1/creators/similar", "anchor": channel_url, "status": "timeout", "possibly_billed": True, "credits_estimate": worst})
            raise PlanError("Upriver timed out. The request may still have been billed, so it was not retried.") from None
    rows = _rows(payload if isinstance(payload, dict) else {}, "youtube")
    charged = estimate(len(rows))
    _release(worst - charged)
    _record({"endpoint": "v1/creators/similar", "anchor": channel_url, "status": 200, "rows": len(rows), "credits_estimate": charged})
    result = {"anchor": channel_url, "platforms": platforms, "results": rows,
              "incomplete": bool((payload or {}).get("incomplete_results")), "creditsCharged": charged, "cached": False}
    _cache_put(cache_key, {k: v for k, v in result.items() if k not in ("creditsCharged", "cached")})
    return result
