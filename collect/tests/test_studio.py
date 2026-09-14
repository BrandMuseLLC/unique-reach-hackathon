import json
import threading
import time
from urllib.parse import parse_qs, urlparse

from collect import youtube
from demo import ai, discovery
from demo.engine import PlanError


def test_concurrent_quota_errors_do_not_skip_fresh_keys():
    barrier = threading.Barrier(4)

    def transport(url):
        key = parse_qs(urlparse(url).query)["key"][0]
        if key == "k1":
            barrier.wait(timeout=5)  # all four requests fail on k1 at the same moment
            return 403, {"error": {"errors": [{"reason": "quotaExceeded"}]}}
        return 200, {"ok": key}

    client = youtube.Client(["k1", "k2"], transport=transport, sleep=lambda _: None)
    results = []
    threads = [threading.Thread(target=lambda: results.append(client.get("videos", id="x"))) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [{"ok": "k2"}] * 4
    assert client.key_index == 1


def test_background_model_calls_wait_for_the_shared_slot(monkeypatch):
    monkeypatch.setattr(ai, "_last_call", time.monotonic())
    monkeypatch.setattr(ai, "_calls", 0)
    started = time.monotonic()
    ai.reserve_call(wait=True)
    assert time.monotonic() - started >= 1.5
    try:
        ai.reserve_call()
        raise AssertionError("interactive calls must still fail fast")
    except PlanError:
        pass


def test_discovery_skips_restricted_brand_channels(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "ANALYSES", tmp_path)
    monkeypatch.setattr(discovery, "MAX_CHANNELS", 10)
    monkeypatch.setattr(discovery, "VIDEOS_PER_CHANNEL", 1)
    monkeypatch.setattr(discovery, "plan_search", lambda prompt: {
        "campaign_name": "Blender launch", "category": "Blenders", "audience": "Home cooks.",
        "queries": [("blender recipes", "Recipes")], "planned_by": "model"})
    channels = {f"UC{i:022d}": (f"Smoothie Creator {i}", f"@smoothie{i}") for i in range(5)}
    channels["UCbrand000000000000000000"] = ("Acme Kitchen Official", "@acmekitchen")

    def transport(url):
        parsed = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        resource = parsed.path.rsplit("/", 1)[-1]
        if resource == "search":
            return 200, {"items": [{"snippet": {"channelId": cid}} for cid in channels]}
        if resource == "channels":
            return 200, {"items": [{"id": cid, "snippet": {"title": channels[cid][0], "customUrl": channels[cid][1]},
                                    "statistics": {"subscriberCount": "50000", "videoCount": "40"},
                                    "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}}} for cid in q["id"].split(",")]}
        if resource == "playlistItems":
            return 200, {"items": [{"contentDetails": {"videoId": "v" + q["playlistId"][2:]}}]}
        if resource == "videos":
            return 200, {"items": [{"id": vid, "snippet": {"title": "t", "description": "", "publishedAt": "2026-08-01T00:00:00Z"},
                                    "statistics": {"viewCount": "1000", "commentCount": "5"}} for vid in q["id"].split(",")]}
        if resource == "commentThreads":
            return 200, {"items": [{"snippet": {"topLevelComment": {"snippet": {"authorChannelId": {"value": f"UCfan{n}"}}}}} for n in range(40)]}
        raise AssertionError(resource)

    discovery._jobs["t1"] = {"id": "t1", "status": "running"}
    discovery._run("t1", "launching a blender", ["k"], {"acme"}, transport)
    job = discovery.status("t1")
    assert job["status"] == "done", job
    data = json.loads((tmp_path / (job["dataset_id"] + ".json")).read_text())
    names = {c["name"] for c in data["creators"]}
    assert "Acme Kitchen Official" not in names and len(names) == 5
    assert data["metadata"]["min_commenters"] == 25


def test_creator_count_target_fills_slots_and_explains_shortfalls(tmp_path):
    from collect import aggregate
    from collect.tests.test_collect import CHANNELS, FakeYouTube
    from demo.daniel_provider import RealDataProvider
    db = youtube.connect(str(tmp_path / "c.sqlite"))
    client = youtube.Client(["k1"], transport=FakeYouTube(), sleep=lambda _: None)
    youtube.resolve_channels(db, client, [("@crema", "Espresso"), ("@shots", "Espresso"), ("@pour", "Filter")])
    youtube.list_videos(db, client, per_channel=2)
    youtube.collect_comments(db, client)
    agg, _ = aggregate.build(db, topic_title="home coffee", cpm=None)
    provider = RealDataProvider(agg)
    roster = [CHANNELS["@crema"][0]]
    two = provider.plan_payload({"budget": 5000, "currentRoster": roster, "planningContext": {"creatorCount": 2}})
    assert len(two["recommended"]["ids"]) == 2 and two["countNote"] is None
    four = provider.plan_payload({"budget": 5000, "currentRoster": roster, "planningContext": {"creatorCount": 4}})
    assert len(four["recommended"]["ids"]) == 3 and four["countNote"].startswith("Only 3 creators in this search can be planned")
    tight = provider.plan_payload({"budget": 1500, "currentRoster": roster, "planningContext": {"creatorCount": 3}})
    assert tight["countNote"].startswith("The budget fits") and "$3,000" in tight["countNote"] and tight["countBudgetNeeded"] == 3000


def test_recommendation_never_loses_reach_or_adds_overlap_vs_your_roster(tmp_path):
    from collect import aggregate
    from collect.tests.test_collect import CHANNELS, FakeYouTube
    from demo.daniel_provider import RealDataProvider
    db = youtube.connect(str(tmp_path / "c.sqlite"))
    client = youtube.Client(["k1"], transport=FakeYouTube(), sleep=lambda _: None)
    youtube.resolve_channels(db, client, [("@crema", "Espresso"), ("@shots", "Espresso"), ("@pour", "Filter")])
    youtube.list_videos(db, client, per_channel=2)
    youtube.collect_comments(db, client)
    agg, _ = aggregate.build(db, topic_title="home coffee", cpm=None)
    provider = RealDataProvider(agg)
    for roster in ([CHANNELS["@crema"][0], CHANNELS["@shots"][0]], [CHANNELS["@shots"][0]], [CHANNELS["@pour"][0], CHANNELS["@crema"][0]]):
        plan = provider.plan_payload({"budget": 2000, "currentRoster": roster})
        mine, rec = plan["rosterDiagnostics"]["rosters"]["current"], plan["rosterDiagnostics"]["rosters"]["recommended"]
        assert rec["coverage"] >= mine["coverage"]
        assert rec["sharedRate"] <= mine["sharedRate"] + 1e-9


def _upriver_env(tmp_path, monkeypatch, cap="150"):
    from demo import upriver
    monkeypatch.setenv("UPRIVER_API_KEY", "test-key")
    monkeypatch.setenv("UPRIVER_MAX_CREDITS", cap)
    monkeypatch.setattr(upriver, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(upriver, "CACHE", tmp_path / "cache.json")
    monkeypatch.setattr(upriver, "_spent", 0)
    return upriver


SIMILAR_PAYLOAD = {"results": [
    {"creator_id": "cr_1", "name": "Latte Lab", "score": 0.91, "channels": [
        {"platform": "instagram", "handle": "lattelab", "url": "https://instagram.com/lattelab", "subscriber_count": 120000},
        {"platform": "youtube", "handle": "@lattelab", "url": "https://youtube.com/@lattelab"}]},
    {"creator_id": "cr_2", "similarity": {"score": 0.72}, "channels": [
        {"platform": "tiktok", "handle": "crema.tok", "url": "https://tiktok.com/@crema.tok", "follower_bucket": "300k_1m"}]},
], "incomplete_results": False}


def test_upriver_similar_parses_caches_and_charges_actual_rows(tmp_path, monkeypatch):
    upriver = _upriver_env(tmp_path, monkeypatch)
    sent = []
    def transport(req):
        sent.append(json.loads(req.data))
        assert req.get_header("X-api-key") == "test-key"
        return SIMILAR_PAYLOAD
    first = upriver.similar("https://www.youtube.com/channel/UCx", platforms=["instagram", "tiktok"], limit=6, transport=transport)
    assert sent == [{"channel_url": "https://www.youtube.com/channel/UCx", "platforms": ["instagram", "tiktok"], "limit": 6}]
    assert [r["platform"] for r in first["results"]] == ["instagram", "tiktok"]
    assert first["results"][1]["score"] == 0.72 and first["results"][0]["otherChannels"][0]["platform"] == "youtube"
    assert first["creditsCharged"] == 4 + 2 * 2 and upriver.status()["creditsReservedThisSession"] == 8
    again = upriver.similar("https://www.youtube.com/channel/UCx", platforms=["tiktok", "instagram"], limit=6, transport=transport)
    assert again["cached"] and again["creditsCharged"] == 0 and len(sent) == 1


def test_upriver_timeout_is_billed_and_never_retried(tmp_path, monkeypatch):
    import socket
    upriver = _upriver_env(tmp_path, monkeypatch)
    calls = []
    def transport(req):
        calls.append(1)
        raise socket.timeout("timed out")
    try:
        upriver.similar("https://www.youtube.com/channel/UCx", transport=transport)
        raise AssertionError("expected PlanError")
    except PlanError as exc:
        assert "may still have been billed" in str(exc)
    assert len(calls) == 1
    entry = json.loads((tmp_path / "ledger.jsonl").read_text().splitlines()[-1])
    assert entry["possibly_billed"] is True and entry["credits_estimate"] == 24
    assert upriver.status()["creditsReservedThisSession"] == 24


def test_upriver_5xx_retries_once_and_cap_blocks_overspend(tmp_path, monkeypatch):
    from urllib.error import HTTPError
    upriver = _upriver_env(tmp_path, monkeypatch, cap="30")
    calls = []
    def flaky(req):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError(req.full_url, 503, "busy", {}, None)
        return SIMILAR_PAYLOAD
    upriver.similar("https://www.youtube.com/channel/UCa", limit=10, transport=flaky)
    assert len(calls) == 2
    try:
        upriver.similar("https://www.youtube.com/channel/UCb", limit=10, transport=flaky)
        raise AssertionError("cap should block a 24-credit reservation after 8 spent of 30")
    except PlanError as exc:
        assert "cap" in str(exc)
