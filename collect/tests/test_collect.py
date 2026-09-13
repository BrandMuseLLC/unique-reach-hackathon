import json
from urllib.parse import parse_qs, urlparse

import pytest

from collect import aggregate, youtube
from collect.__main__ import main
from demo import ai
from demo.daniel_provider import RealDataProvider

CHANNELS = {
    "@crema": ("UCcrema0000000000000000", "Crema Lab", "Espresso", 90000),
    "@shots": ("UCshots0000000000000000", "Shot Notes", "Espresso", 60000),
    "@pour": ("UCpour00000000000000000", "Pour Journal", "Filter", 40000),
}
# author -> channels they comment on; overlap is dense inside Espresso
AUTHORS = {**{"a%d" % i: ["crema", "shots"] for i in range(30)},
           **{"b%d" % i: ["crema"] for i in range(20)},
           **{"c%d" % i: ["shots"] for i in range(10)},
           **{"d%d" % i: ["pour"] for i in range(25)},
           **{"e%d" % i: ["pour", "crema"] for i in range(3)}}


class FakeYouTube:
    def __init__(self, quota_fail_first_key=False, disabled_video=None):
        self.calls = []
        self.quota_fail_first_key = quota_fail_first_key
        self.disabled_video = disabled_video

    def __call__(self, url):
        parsed = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        resource = parsed.path.rsplit("/", 1)[-1]
        self.calls.append((resource, q))
        if self.quota_fail_first_key and q["key"] == "k1":
            return 403, {"error": {"errors": [{"reason": "quotaExceeded"}]}}
        if resource == "channels":
            row = CHANNELS.get(q["forHandle"])
            if not row:
                return 200, {"items": []}
            cid, title, _, subs = row
            return 200, {"items": [{"id": cid, "snippet": {"title": title, "customUrl": q["forHandle"]},
                                    "statistics": {"subscriberCount": str(subs)},
                                    "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}}}]}
        if resource == "playlistItems":
            slug = q["playlistId"][2:].rstrip("0")
            return 200, {"items": [{"contentDetails": {"videoId": "%s-v%d" % (slug, n)}} for n in range(2)]}
        if resource == "videos":
            items = []
            for vid in q["id"].split(","):
                slug, n = vid.split("-v")
                desc = "This video is sponsored by Burr Works. Use code CREMA10 at Bean Box." if slug == "crema" and n == "0" else "Thanks to my Patreon supporters"
                items.append({"id": vid, "snippet": {"title": "%s video %s" % (slug, n), "description": desc,
                                                     "publishedAt": "2026-08-0%sT00:00:00Z" % (int(n) + 1)},
                              "statistics": {"viewCount": str(10000 * (int(n) + 1)), "commentCount": "99"},
                              "contentDetails": {"duration": "PT10M"}})
            return 200, {"items": items}
        if resource == "commentThreads":
            if q["videoId"] == self.disabled_video:
                return 403, {"error": {"errors": [{"reason": "commentsDisabled"}]}}
            slug = q["videoId"].split("-v")[0]
            cid = next(v[0] for k, v in CHANNELS.items() if k[1:] == slug)
            authors = sorted(a for a, chans in AUTHORS.items() if slug in chans)
            page = int(q.get("pageToken", "0"))
            chunk = authors[page * 20:(page + 1) * 20]
            items = [{"snippet": {"topLevelComment": {"snippet": {"authorChannelId": {"value": "UC" + a}}}}} for a in chunk]
            if page == 0:  # creator's own comment and an anonymous row are ignored
                items.append({"snippet": {"topLevelComment": {"snippet": {"authorChannelId": {"value": cid}}}}})
                items.append({"snippet": {"topLevelComment": {"snippet": {}}}})
            body = {"items": items}
            if (page + 1) * 20 < len(authors):
                body["nextPageToken"] = str(page + 1)
            return 200, body
        raise AssertionError(resource)


@pytest.fixture
def collected(tmp_path):
    db = youtube.connect(str(tmp_path / "c.sqlite"))
    fake = FakeYouTube(disabled_video="pour-v1")
    client = youtube.Client(["k1"], transport=fake, sleep=lambda _: None)
    seeds = [("@crema", "Espresso"), ("@shots", "Espresso"), ("@pour", "Filter"), ("@missing", "Filter")]
    assert youtube.resolve_channels(db, client, seeds) == {"resolved": 3, "not_found": ["@missing"]}
    assert youtube.list_videos(db, client, per_channel=2) == 6
    youtube.collect_comments(db, client, max_per_video=500)
    return db, fake


def test_no_raw_commenter_ids_are_stored(collected):
    db, _ = collected
    keys = [r[0] for r in db.execute("SELECT author_key FROM authors")]
    assert keys and not any(k.startswith("UC") for k in keys)
    assert db.execute("SELECT COUNT(*) FROM videos WHERE status='comments_disabled'").fetchone()[0] == 1


def test_aggregate_counts_exact_memberships_and_gate(collected):
    db, _ = collected
    agg, report = aggregate.build(db, topic_title="home coffee")
    patterns = {tuple(s["creators"]): s["count"] for s in agg["audience_segments"]}
    crema, shots, pour = (CHANNELS[h][0] for h in ("@crema", "@shots", "@pour"))
    assert patterns[tuple(sorted([crema, shots]))] == 30
    assert patterns[(crema,)] == 20 and patterns[(shots,)] == 10 and patterns[(pour,)] == 25
    assert patterns[tuple(sorted([crema, pour]))] == 3
    assert report["unique_commenters"] == 88 and report["multi_channel_commenters"] == 33
    assert report["gate"]["pass"] is True
    serialized = json.dumps(agg)
    assert "UCa1" not in serialized and "author_key" not in serialized


def test_resume_does_not_double_count(collected, tmp_path):
    db, _ = collected
    before = db.execute("SELECT SUM(comments) FROM authors").fetchone()[0]
    client = youtube.Client(["k1"], transport=FakeYouTube(), sleep=lambda _: None)
    youtube.collect_comments(db, client)
    assert db.execute("SELECT SUM(comments) FROM authors").fetchone()[0] == before


def test_quota_error_rotates_to_next_key(tmp_path):
    db = youtube.connect(str(tmp_path / "q.sqlite"))
    client = youtube.Client(["k1", "k2"], transport=FakeYouTube(quota_fail_first_key=True), sleep=lambda _: None)
    youtube.resolve_channels(db, client, [("@crema", "Espresso")])
    assert client.key_index == 1
    exhausted = youtube.Client(["k1"], transport=FakeYouTube(quota_fail_first_key=True), sleep=lambda _: None)
    with pytest.raises(youtube.QuotaExhausted):
        exhausted.get("channels", forHandle="@crema")


def test_sponsor_scan_and_restricted_redaction():
    videos = [{"description": "This video is sponsored by Acme Kitchen. Thanks to everyone!", "published_at": "2026-08-02"},
              {"description": "Use code SHOT15 at Burr Works for 15% off. #ad", "published_at": "2026-08-05"}]
    found = aggregate.sponsor_mentions(videos)
    assert [b["brand"] for b in found["brands"]] == ["Acme Kitchen", "Burr Works"]
    assert found["disclosed_videos"] == 2  # "this video is sponsored" and "#ad"
    redacted = aggregate.sponsor_mentions(videos, restricted={"acme"})
    assert {b["brand"] for b in redacted["brands"]} == {aggregate.RESTRICTED, "Burr Works"}
    assert aggregate.redact("Acme Kitchen espresso review", {"acme"}) == "[brand] Kitchen espresso review"


def test_collected_aggregate_plans_through_provider_and_ai_evidence(collected, tmp_path, monkeypatch):
    db, _ = collected
    agg, _ = aggregate.build(db, topic_title="home coffee")
    path = tmp_path / "agg.json"
    path.write_text(json.dumps(agg))
    provider = RealDataProvider.from_env({"MUSE_OBSERVED_DATA": str(path)})
    assert provider.campaign["id"] == "home-coffee-case-study"
    assert provider.eligible == set(provider.planner.by_id)
    creators = provider.creators_payload()
    crema = CHANNELS["@crema"][0]
    row = next(c for c in creators["creators"] if c["id"] == crema)
    assert [b["brand"] for b in row["sponsorMentions"]["brands"]] == ["Bean Box", "Burr Works"]
    plan = provider.plan_payload({"budget": 2000, "currentRoster": [crema, CHANNELS["@shots"][0]]})
    picked = set(plan["recommended"]["ids"])
    assert CHANNELS["@pour"][0] in picked  # the low-overlap channel is chosen
    assert not {crema, CHANNELS["@shots"][0]} <= picked  # never pays twice for the shared espresso audience

    sent = {}
    def transport(req):
        sent["body"] = json.loads(req.data)
        return {"content": [{"type": "tool_use", "name": "set_reach_brief", "input": {
            "action": "plan", "reply": "Excluded the creator with a competing grinder sponsor.", "budget": 2000,
            "must_include": [], "exclude": [crema], "max_per_group": {}, "brand_description": "espresso launch",
            "relevance": {}, "relevance_reasons": []}}]}
    monkeypatch.setenv("MUSE_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("MUSE_LLM_MODEL", "claude-sonnet-5")
    monkeypatch.setattr(ai, "_last_call", None)
    result = ai.live_chat(provider.planner, {"message": "avoid anyone sponsored by Burr Works", "constraints": {"budget": 2000}}, transport=transport)
    evidence = json.loads(sent["body"]["messages"][0]["content"])["creators"]
    assert next(c for c in evidence if c["id"] == crema)["sponsor_mentions"] == ["Bean Box", "Burr Works"]
    assert crema not in result["plan"]["selected"]


def test_cli_build_writes_files(collected, tmp_path, capsys):
    db, _ = collected
    db_path = db.execute("PRAGMA database_list").fetchone()[2]
    restricted = tmp_path / "restricted.txt"
    restricted.write_text("bean box\n")
    out, report = tmp_path / "a.json", tmp_path / "r.json"
    assert main(["--db", db_path, "build", "--out", str(out), "--report", str(report), "--restricted", str(restricted)]) == 0
    assert "gate=PASS" in capsys.readouterr().out
    assert "Bean Box" not in out.read_text()


def test_headline_reports_both_baselines_and_split(collected, tmp_path, capsys):
    db, _ = collected
    agg, _ = aggregate.build(db, topic_title="home coffee")
    path = tmp_path / "agg.json"
    path.write_text(json.dumps(agg))
    assert main(["headline", "--aggregate", str(path), "--budgets", "2000", "--audit-size", "2", "--out", str(tmp_path / "h.json")]) == 0
    printed = capsys.readouterr().out
    assert "biggest-2 roster duplicates" in printed
    result = json.loads((tmp_path / "h.json").read_text())
    audit = result["audit_biggest_by_subscribers"]
    # the two biggest channels (crema, shots) share 30 commenters out of 50 + 40 memberships
    assert audit["sum_of_individual_audiences"] == 93 and audit["sampled_commenters_reached"] == 63
    for row in result["comparisons"]:
        planner_reach = row["rosters"]["planner"]["reach"]
        assert planner_reach >= row["rosters"]["top_views"]["reach"] - 1e-9
        split = row["vs_top_views"]
        base, plan = row["rosters"]["top_views"], row["rosters"]["planner"]
        assert abs((plan["reach"] - base["reach"]) - (split["from_bigger_audiences"] + split["from_less_overlap"])) < 1e-6
