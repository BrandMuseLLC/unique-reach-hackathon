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
