import json
from urllib.parse import parse_qs, urlparse

import pytest

from demo import discovery
from demo.engine import PlanError


def test_normalize_handle_accepts_urls_ids_and_bare_names():
    assert discovery.normalize_handle("https://www.youtube.com/@jameshoffmann") == "@jameshoffmann"
    assert discovery.normalize_handle("youtube.com/@jameshoffmann/videos") == "@jameshoffmann"
    assert discovery.normalize_handle("https://www.youtube.com/channel/UCMb0O2CdPBNi-QqPk5T3gsQ") == "UCMb0O2CdPBNi-QqPk5T3gsQ"
    assert discovery.normalize_handle("UCMb0O2CdPBNi-QqPk5T3gsQ") == "UCMb0O2CdPBNi-QqPk5T3gsQ"
    assert discovery.normalize_handle("jameshoffmann") == "@jameshoffmann"
    assert discovery.normalize_handle(" @Lance_Hedrick ") == "@Lance_Hedrick"
    assert discovery.normalize_handle("") is None
    assert discovery.normalize_handle("@a") is None


def test_normalize_roster_dedupes_and_defaults_topics():
    roster = discovery.normalize_roster([("@crema", "espresso"), ("youtube.com/@CREMA", ""), "@pour", ("", "x")])
    assert roster == [("@crema", "Espresso"), ("@pour", discovery.ROSTER_TOPIC)]
    with pytest.raises(PlanError):
        discovery.normalize_roster(["@handle%03d" % i for i in range(discovery.MAX_ROSTER + 1)])


def test_roster_run_skips_the_model_and_maps_exactly_the_listed_channels(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "ANALYSES", tmp_path)
    monkeypatch.setattr(discovery, "VIDEOS_PER_CHANNEL", 1)
    monkeypatch.setattr(discovery, "plan_search", lambda prompt: pytest.fail("a roster never searches YouTube"))
    monkeypatch.setattr(discovery, "plan_roster", lambda prompt, roster: {
        "campaign_name": "Coffee roster", "category": "Coffee gear", "audience": "Home baristas.", "queries": [], "planned_by": "model",
        "topics": {"pour": "Filter"}})
    channels = {"@crema": ("UC" + "1" * 22, "Crema Lab"), "@pour": ("UC" + "2" * 22, "Pour Daily"), "@shots": ("UC" + "3" * 22, "Shots")}
    by_id = {cid: (handle, title) for handle, (cid, title) in channels.items()}

    def transport(url):
        parsed = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        resource = parsed.path.rsplit("/", 1)[-1]
        if resource == "search":
            raise AssertionError("a roster run must not search")
        if resource == "channels":
            if "forHandle" in q:
                cid = channels.get(q["forHandle"], (None,))[0]
                ids = [cid] if cid else []
            else:
                ids = q["id"].split(",")
            return 200, {"items": [{"id": cid, "snippet": {"title": by_id[cid][1], "customUrl": by_id[cid][0]},
                                    "statistics": {"subscriberCount": "800", "videoCount": "12"},
                                    "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}}} for cid in ids]}
        if resource == "playlistItems":
            return 200, {"items": [{"contentDetails": {"videoId": "v" + q["playlistId"][2:]}}]}
        if resource == "videos":
            return 200, {"items": [{"id": vid, "snippet": {"title": "t", "description": "", "publishedAt": "2026-08-01T00:00:00Z"},
                                    "statistics": {"viewCount": "1000", "commentCount": "5"}} for vid in q["id"].split(",")]}
        if resource == "commentThreads":
            return 200, {"items": [{"snippet": {"topLevelComment": {"snippet": {"authorChannelId": {"value": f"UCfan{n}"}}}}} for n in range(40)]}
        raise AssertionError(resource)

    discovery._jobs["r1"] = {"id": "r1", "status": "running"}
    roster = discovery.normalize_roster([("https://www.youtube.com/@crema", "Espresso"), "@pour", "UC" + "3" * 22, "@nobodyhere"])
    discovery._run("r1", "Coffee roster", ["k"], set(), transport, roster=roster)
    job = discovery.status("r1")
    assert job["status"] == "done", job
    data = json.loads((tmp_path / (job["dataset_id"] + ".json")).read_text())
    assert {c["name"] for c in data["creators"]} == {"Crema Lab", "Pour Daily", "Shots"}  # small channels are kept: the user chose them
    roster_meta = data["metadata"]["roster"]
    assert (roster_meta["requested"], roster_meta["found"], roster_meta["missing"], roster_meta["skipped"]) == (4, 3, ["@nobodyhere"], [])
    assert data["metadata"]["min_commenters"] == 10
    assert data["metadata"]["queries"] == []
    assert data["metadata"]["campaign"]["category"] == "Coffee gear"
    topics = {c["name"]: c["community"] for c in data["creators"]}
    assert topics["Crema Lab"] == "Espresso" and topics["Pour Daily"] == "Filter" and topics["Shots"] == discovery.ROSTER_TOPIC
    assert "Not found on YouTube: @nobodyhere" in job["message"]


def test_roster_needs_two_resolvable_channels(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "ANALYSES", tmp_path)

    def transport(url):
        return 200, {"items": []}

    discovery._jobs["r2"] = {"id": "r2", "status": "running"}
    discovery._run("r2", "Coffee roster", ["k"], set(), transport, roster=[("@ghost", "X"), ("@phantom", "X")])
    job = discovery.status("r2")
    assert job["status"] == "error" and "Only 0 of the 2 creators" in job["error"]


def test_split_roster_separates_instagram_and_tiktok_rows():
    roster, externals = discovery.split_roster([("@crema", "Espresso"), ("https://www.instagram.com/latte.lab/", "Latte art"),
                                                "tiktok: @beanqueen", "https://www.tiktok.com/@beanqueen/video/123", "https://www.instagram.com/p/abc123/"])
    assert roster == [("@crema", "Espresso")]
    assert [(e["platform"], e["handle"], e["topic"]) for e in externals] == [("instagram", "latte.lab", "Latte Art"), ("tiktok", "beanqueen", discovery.ROSTER_TOPIC)]
    assert externals[0]["url"] == "https://www.instagram.com/latte.lab/" and externals[1]["url"] == "https://www.tiktok.com/@beanqueen"


def test_listed_social_creators_are_profiled_first_and_sized_from_upriver(tmp_path, monkeypatch):
    from collect.tests.test_studio import _upriver_env
    _upriver_env(tmp_path, monkeypatch, cap="1000")
    looked_up = []

    def transport(req):
        if req.full_url.endswith("/v1/categories/search"):
            return {"matches": []}
        if req.full_url.endswith("/v1/creators/search"):
            sent = json.loads(req.data)
            platform = sent["platforms"][0]
            return {"results": [{"creator_id": "s", "channels": [{"platform": platform, "handle": "latte.lab" if platform == "instagram" else "other",
                                                                   "url": "https://www.instagram.com/latte.lab/" if platform == "instagram" else "https://www.tiktok.com/@other",
                                                                   "subscriber_count": 90000}]}]}
        looked_up.append(req.full_url)
        return {"channels": [{"platform": "instagram", "handle": "latte.lab", "display_name": "Latte Lab", "url": "https://www.instagram.com/latte.lab/", "follower_count": 42000}],
                "audience": {"status": "limited_coverage", "gender": {"value": "female", "percentage": 61}}}

    discovery._jobs["cpx"] = {"id": "cpx", "status": "running"}
    _, externals = discovery.split_roster(["https://www.instagram.com/latte.lab/"])
    block = discovery._crossplatform("cpx", {"metadata": {}, "creators": [], "audience_segments": []},
                                     {"category": "Coffee", "campaign_name": "Coffee roster", "queries": []}, set(), transport, explicit=externals)
    mine = [e for e in block["external"] if e["id"] == "instagram:latte.lab"]
    assert len(mine) == 1 and mine[0]["followers"] == 42000 and mine[0]["name"] == "Latte Lab" and "audience" in mine[0]
    assert sum(1 for e in block["external"] if e["url"].rstrip("/") == "https://www.instagram.com/latte.lab") == 1  # the search duplicate was skipped
    assert any("latte.lab" in u for u in looked_up)


def test_list_runs_can_skip_vendor_lookalikes(tmp_path, monkeypatch):
    from collect.tests.test_studio import _upriver_env
    _upriver_env(tmp_path, monkeypatch, cap="1000")
    monkeypatch.setenv("ROSTER_SEARCH_LOOKALIKES", "false")
    calls = []

    def transport(req):
        calls.append(req.full_url)
        return {"channels": [{"platform": "tiktok", "handle": "beanqueen", "display_name": "Bean Queen", "url": "https://www.tiktok.com/@beanqueen", "follower_count": 9000}],
                "audience": {"status": "limited_coverage"}}

    discovery._jobs["cpn"] = {"id": "cpn", "status": "running"}
    _, externals = discovery.split_roster(["tiktok:@beanqueen"])
    block = discovery._crossplatform("cpn", {"metadata": {}, "creators": [], "audience_segments": []}, {"category": "Coffee", "campaign_name": "Coffee", "queries": []}, set(), transport, explicit=externals)
    assert not any(u.endswith("/creators/search") or u.endswith("/categories/search") for u in calls)
    assert [e["handle"] for e in block["external"]] == ["beanqueen"] and block["external"][0]["followers"] == 9000


def test_muse_evidence_carries_overlap_and_falls_back_to_the_plan_summary():
    from demo import ai_explain
    plan = {"metricLabel": "Estimated unique followers", "budget": 5_000_000, "remainingBudget": 4_000_000,
            "recommended": {"ids": ["a", "b"], "proxyReach": 1_123_456.7, "spend": 0, "observedCommenterCoverage": 900},
            "current": {"ids": ["a", "b", "c"], "proxyReach": 1_100_000, "spend": 0},
            "viewsBaseline": {"ids": ["a", "c"], "proxyReach": 1_000_000, "spend": 0},
            "steps": [{"creatorName": "A", "marginalProxyReach": 700_000.4, "cost": 1}],
            "whyNot": [{"creatorName": "C", "reason": "Adds little.", "cost": 1, "alreadyCoveredShare": 0.428, "marginalProxyReach": 12_000, "overlapsWith": []}],
            "rosterDiagnostics": {"rosters": {"recommended": {"ids": ["a", "b"], "sharedRate": 0.2014, "coverage": 1_123_456, "shared": 280_000, "standalone": 1_400_000},
                                              "current": {"ids": ["a", "b", "c"], "sharedRate": 0.317, "coverage": 1_100_000, "shared": 500_000, "standalone": 1_600_000},
                                              "viewsBaseline": {"ids": ["a", "c"], "sharedRate": 0.763, "coverage": 1_000_000, "shared": 900_000, "standalone": 1_900_000}}},
            "choice": {"headline": "Less overlap without losing reach."}}
    facts = ai_explain.evidence(plan)
    assert "budget" not in facts and "spend" not in facts["recommended"]
    assert facts["recommended"]["overlap"]["overlap_percent"] == 20.1 and facts["your_roster"]["overlap"]["overlap_percent"] == 31.7
    # The page's own roundings count as grounded: 20.1%, 1.1M, 43%.
    assert ai_explain.grounded("The recommendation overlaps 20.1% versus your roster's 31.7%, reaching 1.1M people.", facts, "how much overlap?")
    assert ai_explain.grounded("C is 43% covered already.", facts, "why not C?")
    assert not ai_explain.grounded("That saves you $4,200.", facts, "how much overlap?")
    text = ai_explain.summary(plan)
    assert text.startswith("Recommended: 2 creators, 20.1% overlap, 1,123,457 reached") and "Your roster: 3 creators, 31.7% overlap" in text and text.endswith("Less overlap without losing reach.")


def test_repeat_upload_of_the_same_list_reuses_the_saved_dataset(tmp_path):
    newer = tmp_path / "coffee-2.json"
    newer.write_text(json.dumps({"metadata": {"roster": {"listed": ["@crema", "@pour", "https://www.tiktok.com/@beanqueen"]}}, "creators": [{"id": "UC1"}, {"id": "UC2"}],
                                 "crossplatform": {"external": [{"url": "https://www.tiktok.com/@beanqueen"}]}}))
    legacy = tmp_path / "coffee-1.json"  # built before the list key was stored: matched on mapped handles plus missing ones
    legacy.write_text(json.dumps({"metadata": {"roster": {"missing": ["@ghost"]}}, "creators": [{"id": "UC1", "handle": "@crema"}, {"id": "UC2", "handle": "Pour"}]}))
    searched = tmp_path / "search.json"
    searched.write_text(json.dumps({"metadata": {"prompt": "coffee"}, "creators": [{"id": "UC1", "handle": "@crema"}, {"id": "UC2", "handle": "@pour"}]}))
    datasets = {"coffee-2": newer, "coffee-1": legacy, "search": searched}
    roster, externals = discovery.split_roster([("@Pour", "Filter"), "@crema", "tiktok:beanqueen"])
    assert discovery.find_saved(roster, externals, datasets) == ("coffee-2", 3)
    roster, externals = discovery.split_roster(["@crema", "@pour", "@ghost"])
    assert discovery.find_saved(roster, externals, datasets) == ("coffee-1", 2)
    roster, externals = discovery.split_roster(["@crema", "@pour", "@newcomer"])
    assert discovery.find_saved(roster, externals, datasets) is None


def test_start_hands_back_a_finished_job_for_a_saved_list(tmp_path, monkeypatch):
    saved = tmp_path / "coffee.json"
    saved.write_text(json.dumps({"metadata": {"roster": {"listed": ["@crema", "@pour"]}}, "creators": [{"id": "UC1"}, {"id": "UC2"}]}))
    monkeypatch.setattr(discovery._running, "is_set", lambda: False)
    job_id = discovery.start("Coffee roster", ["k"], roster=[("@crema", ""), ("@pour", "")], saved={"coffee": saved})
    job = discovery.status(job_id)
    assert job["status"] == "done" and job["dataset_id"] == "coffee" and job["reused"] and "2 creators" in job["message"]


def test_small_percentages_are_not_grounded_by_the_count_allowance():
    from demo import ai_explain
    facts = {"recommended": {"overlap": {"overlap_percent": 20.1}}, "your_roster": {"overlap": {"overlap_percent": 31.7}}}
    assert not ai_explain.grounded("Your roster overlaps 7.3% and the recommendation 4.8%.", facts, "overlap?")
    assert ai_explain.grounded("Two creators carry most of it: 20.1% overall.", facts, "overlap?")
    assert ai_explain.grounded("3 of them overlap.", facts, "overlap?")
