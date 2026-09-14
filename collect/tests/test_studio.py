import pytest
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


def test_audience_profile_match_scores_parts_and_handles_missing_data():
    from demo import audience_match as am
    us_women = am.profile({"status": "full_coverage", "gender": {"value": "female", "percentage": 70},
                           "age": {"min_age": 18, "max_age": 34}, "geography": {"countries": [{"country": "US", "percentage": 70}, {"country": "CA", "percentage": 10}]}})
    also = am.profile({"status": "full_coverage", "gender": {"value": "female", "percentage": 66},
                       "age": {"min_age": 18, "max_age": 30}, "geography": {"countries": [{"country": "US", "percentage": 64}, {"country": "UK", "percentage": 12}]}})
    india_men = am.profile({"status": "partial_coverage", "gender": {"value": "male", "percentage": 80},
                            "age": {"min_age": 13, "max_age": 17}, "geography": {"countries": [{"country": "IN", "percentage": 75}]}})
    close, far = am.match(us_women, also), am.match(us_women, india_men)
    assert not close["complete"] and close["match"] == pytest.approx((0.4 * 0.64 + 0.2 * 0.96 + 0.2 * 0.75) / 0.8)  # no language on either
    assert far["match"] < 0.2 and far["parts"]["geography"] == 0 and far["parts"]["age"] == 0
    assert am.profile({"status": "no_coverage"}) is None and am.match(us_women, None) is None
    geo_only = am.profile({"status": "partial_coverage", "geography": {"countries": [{"country": "US", "percentage": 50}]}})
    partial = am.match(us_women, geo_only)
    assert partial["basis"] == ["geography"] and not partial["complete"]
    assert am.summary(us_women) == "US 70% · CA 10%, 70% female, ages 18–34"


def test_upriver_audience_lookup_costs_eight_credits_and_caches(tmp_path, monkeypatch):
    upriver = _upriver_env(tmp_path, monkeypatch)
    seen = []
    def transport(req):
        seen.append(req.full_url)
        assert req.get_method() == "GET" and "include=audience" in req.full_url
        return {"creator_id": "cr_9", "channels": [{"platform": "tiktok", "url": "https://www.tiktok.com/@crema.tok", "display_name": "Crema Tok", "follower_count": 90000}],
                "audience": {"status": "full_coverage", "gender": {"value": "female", "percentage": 60}}}
    first = upriver.audience("https://www.tiktok.com/@crema.tok", transport=transport)
    assert first["platform"] == "tiktok" and first["name"] == "Crema Tok" and first["creditsCharged"] == 8
    again = upriver.audience("https://www.tiktok.com/@crema.tok", transport=transport)
    assert again["cached"] and again["creditsCharged"] == 0 and len(seen) == 1
    assert upriver.status()["creditsReservedThisSession"] == 8


def _cross_dataset(tmp_path):
    from collect import aggregate
    from collect.tests.test_collect import CHANNELS, FakeYouTube
    db = youtube.connect(str(tmp_path / "x.sqlite"))
    client = youtube.Client(["k1"], transport=FakeYouTube(), sleep=lambda _: None)
    youtube.resolve_channels(db, client, [("@crema", "Espresso"), ("@shots", "Espresso"), ("@pour", "Filter")])
    youtube.list_videos(db, client, per_channel=2)
    youtube.collect_comments(db, client)
    agg, _ = aggregate.build(db, topic_title="home coffee", cpm=None)
    us = {"status": "full_coverage", "gender": {"value": "male", "percentage": 70}, "age": {"min_age": 25, "max_age": 44},
          "geography": {"countries": [{"country": "US", "percentage": 60}]}}
    uk_teens = {"status": "full_coverage", "gender": {"value": "female", "percentage": 75}, "age": {"min_age": 13, "max_age": 17},
                "geography": {"countries": [{"country": "GB", "percentage": 70}]}}
    agg["metadata"]["prompt"] = "coffee launch"
    agg["crossplatform"] = {
        "profiles": {CHANNELS["@crema"][0]: us, CHANNELS["@shots"][0]: us, CHANNELS["@pour"][0]: us},
        "external": [
            {"id": "instagram:espressogram", "name": "Espresso Gram", "platform": "instagram", "handle": "espressogram", "url": "https://www.instagram.com/espressogram", "followers": 80000, "audience": us},
            {"id": "tiktok:teencafe", "name": "Teen Cafe", "platform": "tiktok", "handle": "teencafe", "url": "https://www.tiktok.com/@teencafe", "followers": 60000, "audience": uk_teens},
            {"id": "tiktok:nodata", "name": "No Data", "platform": "tiktok", "handle": "nodata", "url": "https://www.tiktok.com/@nodata", "followers": 40000, "audience": {"status": "no_coverage"}},
        ],
    }
    return agg, CHANNELS


def test_crossplatform_blends_measured_and_estimated_overlap(tmp_path):
    from demo.crossplatform import CrossPlatformProvider, DEFAULT_KAPPA, load_provider
    agg, CHANNELS = _cross_dataset(tmp_path)
    provider = load_provider(agg)
    assert isinstance(provider, CrossPlatformProvider)
    crema, shots, pour = (CHANNELS[h][0] for h in ("@crema", "@shots", "@pour"))
    assert provider.pair_source(crema, shots) == "measured"
    assert provider.shared_fraction(crema, shots) == pytest.approx(30 / 40)  # 30 shared of shots' 40 commenters
    assert provider.pair_source(crema, "instagram:espressogram") == "estimated"
    assert provider.pair_source("tiktok:nodata", crema) == "assumed"
    same = provider.shared_fraction("instagram:espressogram", crema)
    different = provider.shared_fraction("tiktok:teencafe", crema)
    assert same > different  # identical audience profiles are estimated to overlap more than US adults vs UK teens
    assert provider.calibration_pairs == 3 and provider.kappa != DEFAULT_KAPPA

    payload = provider.creators_payload()
    platforms = {c["platform"] for c in payload["creators"]}
    assert platforms == {"youtube", "instagram", "tiktok"}
    request = {"budget": payload["defaultBudget"], "currentRoster": payload["defaultCurrentRoster"]}
    plan = provider.plan_payload(request)
    mine, rec = plan["rosterDiagnostics"]["rosters"]["current"], plan["rosterDiagnostics"]["rosters"]["recommended"]
    assert rec["coverage"] >= mine["coverage"] and rec["sharedRate"] <= mine["sharedRate"] + 1e-9
    assert set(plan["evidenceMix"]) >= {"measured", "estimated", "assumed", "measuredShare"}
    assert {"steps", "whyNot", "countNote", "method"} <= set(plan)

    capped = provider.plan_payload({**request, "budget": 1_000_000, "planningContext": {"maxPerGroup": {"TikTok": 0}, "creatorCount": 3}})
    assert all(provider.planner.by_id[i]["platform"] != "tiktok" for i in capped["recommended"]["ids"])
    assert len(capped["recommended"]["ids"]) == 3


def test_crossplatform_discovery_step_respects_credit_budget(tmp_path, monkeypatch):
    from demo import discovery
    upriver = _upriver_env(tmp_path, monkeypatch, cap="1000")
    calls = []
    def transport(req):
        calls.append(req.full_url)
        if req.full_url.endswith("/v1/categories/search"):
            return {"matches": [{"category_id": "dining_beverage", "level": 2, "confidence": 0.95}, {"category_id": "food_drink", "level": 1, "confidence": 0.7}]}
        if req.full_url.endswith("/v1/creators/search"):
            sent = json.loads(req.data)
            assert sent["category_ids"] == ["dining_beverage", "food_drink"] and sent["content_query"] == "home espresso" and "categories" not in sent
            platform = sent["platforms"][0]
            return {"results": [{"creator_id": "c%d" % n, "channels": [{"platform": platform, "handle": "%s%d" % (platform, n), "url": "https://www.%s.com/%s%d" % (platform, platform, n), "subscriber_count": 50000 + n}]} for n in range(5)]}
        return {"channels": [], "audience": {"status": "full_coverage", "gender": {"value": "female", "percentage": 55}}}
    discovery._jobs["cp"] = {"id": "cp", "status": "running"}
    agg = {"creators": [{"id": "UC%022d" % n, "subscribers": 1000 * n} for n in range(8)]}
    block = discovery._crossplatform("cp", agg, {"category": "Home coffee", "campaign_name": "Coffee", "queries": [("home espresso", "Espresso")]}, {"instagram3"}, transport)
    assert len([u for u in calls if u.endswith("/creators/search")]) == 2
    assert block["credits"] <= discovery.SEARCH_CREDIT_BUDGET
    assert all(e["handle"] != "instagram3" for e in block["external"])  # restricted handle filtered
    assert all("audience" in e for e in block["external"][:2])



def test_audience_match_reads_the_live_upriver_shape():
    from demo import audience_match as am
    live = {"status": "limited_coverage", "description": "Specialty coffee fans.",
            "gender": {"value": "male", "percentage": 72, "confidence": "high"},
            "age": {"min_age": 25, "max_age": 44, "segments": [{"min_age": 25, "max_age": 34, "percentage": 75}], "confidence": "high"},
            "geography": {"countries": [{"country": "GB", "country_name": "United Kingdom"}], "international": True, "confidence": "low"},
            "languages": {"value": "English", "confidence": "high"}}
    p = am.profile(live)
    assert p and p["countries"] == {"GB": 1.0} and p["countries_estimated"] and p["confidence"]["geography"] == 0.4
    assert am.summary(p) == "mainly United Kingdom, 72% male, ages 25–44, English"
    twin = am.match(p, am.profile(live))
    assert twin["complete"] and twin["match"] == pytest.approx(1.0)
    us_teen_spanish = am.profile({"status": "full_coverage", "gender": {"value": "female", "percentage": 80, "confidence": "high"},
                                  "age": {"min_age": 13, "max_age": 17, "confidence": "high"},
                                  "geography": {"countries": [{"country": "US", "percentage": 90}], "confidence": "high"},
                                  "languages": {"value": "Spanish", "confidence": "high"}})
    far = am.match(p, us_teen_spanish)
    assert far["match"] < 0.15
    # low geography confidence means the country mismatch counts for less than language/gender/age mismatches
    assert far["parts"]["geography"] == 0.0 and far["parts"]["language"] == 0.0


def test_crossplatform_lookups_continue_past_failures_and_skip_thin_youtube(tmp_path, monkeypatch):
    from urllib.error import HTTPError
    from demo import discovery
    upriver = _upriver_env(tmp_path, monkeypatch, cap="1000")
    looked_up = []
    def transport(req):
        url = req.full_url
        if url.endswith("/v1/categories/search"):
            return {"matches": []}
        if url.endswith("/v1/creators/search"):
            platform = json.loads(req.data)["platforms"][0]
            return {"results": [{"channels": [{"platform": platform, "handle": "%s%d" % (platform, n), "url": "https://www.%s.com/%s%d" % (platform, platform, n), "subscriber_count": 60000}]} for n in range(3)]}
        looked_up.append(url)
        if "instagram0" in url:
            raise HTTPError(url, 404, "not found", {}, None)  # one creator Upriver can't resolve
        return {"channels": [], "audience": {"status": "limited_coverage", "gender": {"value": "male", "percentage": 60, "confidence": "high"}}}
    discovery._jobs["cp2"] = {"id": "cp2", "status": "running"}
    agg = {"metadata": {"min_commenters": 25},
           "creators": [{"id": "UCthin000000000000000000", "subscribers": 9_000_000}, {"id": "UCgood000000000000000000", "subscribers": 100_000}],
           "audience_segments": [{"creators": ["UCthin000000000000000000"], "count": 3}, {"creators": ["UCgood000000000000000000"], "count": 400}]}
    block = discovery._crossplatform("cp2", agg, {"category": "Toys", "campaign_name": "Toys", "queries": [("football toy", "Toys")]}, set(), transport)
    assert not any("UCthin" in u for u in looked_up)            # set-aside channel is never profiled
    assert any("UCgood" in u for u in looked_up)
    assert sum("tiktok" in u for u in looked_up) == 3            # lookups after the failed Instagram one still ran
    assert "UCgood000000000000000000" in block["profiles"]
    assert any("unavailable" in n for n in block["notes"])
    assert discovery.status("cp2")["message"].startswith("Reading audience profiles (7 of 7, 1 unavailable")


def test_crossplatform_lookups_stop_at_search_budget(tmp_path, monkeypatch):
    from demo import discovery
    _upriver_env(tmp_path, monkeypatch, cap="1000")
    monkeypatch.setattr(discovery, "SEARCH_CREDIT_BUDGET", 60)  # 2 searches x 10 credits = 20, leaving room for 5 lookups
    looked_up = []
    def transport(req):
        if req.full_url.endswith("/v1/categories/search"):
            return {"matches": []}
        if req.full_url.endswith("/v1/creators/search"):
            platform = json.loads(req.data)["platforms"][0]
            return {"results": [{"channels": [{"platform": platform, "handle": "%s%d" % (platform, n), "url": "https://www.%s.com/%s%d" % (platform, platform, n), "subscriber_count": 60000}]} for n in range(3)]}
        looked_up.append(req.full_url)
        return {"channels": [], "audience": {"status": "no_coverage"}}
    discovery._jobs["cp3"] = {"id": "cp3", "status": "running"}
    block = discovery._crossplatform("cp3", {"metadata": {}, "creators": [], "audience_segments": []}, {"category": "Toys", "campaign_name": "Toys"}, set(), transport)
    assert len(looked_up) == 5 and block["credits"] <= 60
    assert any("search budget" in n for n in block["notes"])


def test_choice_explains_tradeoffs_and_flags_assumed_overlap():
    from demo import choice
    mine = {"ids": ["a"], "spend": 500, "coverage": 72_000, "sharedRate": 0.0}
    rec = {"ids": ["b", "c", "d"], "spend": 4250, "coverage": 522_096, "sharedRate": 0.001}
    why = choice.explain(mine, rec, unit="followers", current_ids=["a"], feasible_reason=None, creator_count=3,
                         evidence_mix={"measured": 0, "estimated": 0, "assumed": 3, "pairs": 3})
    assert why["kind"] == "tradeoff" and "7.3× more followers" in why["headline"]
    assert any("asked for 3 creators" in r for r in why["reasons"]) and any("single creator" in r for r in why["reasons"])
    assert why["overlapConfidence"] == "assumed" and any("assumed, not measured" in r for r in why["reasons"])
    same = choice.explain(mine, {"ids": ["b"], "spend": 3500, "coverage": 461_000, "sharedRate": 0.0}, unit="followers",
                          current_ids=["a"], feasible_reason=None, creator_count=0, evidence_mix={"measured": 0, "estimated": 0, "assumed": 0, "pairs": 0})
    assert same["headline"].startswith("Same overlap (0.0%), more reach") and same["overlapConfidence"] == "none"
    over = choice.explain({"ids": ["a", "b"], "spend": 9000, "coverage": 10_000, "sharedRate": 0.02}, rec, unit="commenters",
                          current_ids=["a", "b"], feasible_reason="it costs more than the budget", creator_count=0)
    assert over["kind"] == "better"
    worse = choice.explain({"ids": ["a", "b"], "spend": 9000, "coverage": 600_000, "sharedRate": 0.0}, rec, unit="commenters",
                           current_ids=["a", "b"], feasible_reason="it costs more than the budget", creator_count=0)
    assert worse["kind"] == "tradeoff" and any("costs more than the budget" in r for r in worse["reasons"])
