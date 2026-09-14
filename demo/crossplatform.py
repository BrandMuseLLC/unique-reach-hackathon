"""Cross-platform planning: YouTube, Instagram and TikTok creators in one pool.

Audience size is followers on every platform so creators are comparable. Pairwise overlap blends two kinds of evidence:
- measured: both creators are YouTube channels with sampled commenters, so shared fraction = shared commenters / the
  smaller channel's commenters (from the observed aggregate);
- estimated: any pair involving Instagram or TikTok uses the audience profile match (countries, gender mix, age range from
  Upriver) scaled by a factor calibrated on YouTube pairs that have both a measured overlap and a profile match.

Estimated unique reach of a roster uses a pairwise approximation:
    unique = sum(size) - sum over pairs(shared fraction x smaller size), never below the largest single audience.
Every number the planner reports carries how much of it rests on measured versus estimated pairs.
"""
import hashlib
import json
import math

if __package__:
    from . import audience_match, choice
    from .daniel_provider import RealDataProvider
    from .engine import PlanError
else:
    import audience_match
    import choice
    from daniel_provider import RealDataProvider
    from engine import PlanError

PLATFORM_LABEL = {"youtube": "YouTube", "instagram": "Instagram", "tiktok": "TikTok"}
DEFAULT_KAPPA = 0.15      # used when too few YouTube pairs exist to calibrate
UNKNOWN_MATCH = 0.35      # assumed profile match when a creator has no audience data
# Rough sponsorship rates per 1,000 followers so platforms are priced on the same basis; every quote stays editable.
QUOTE_PER_1K = {"youtube": 20.0, "instagram": 10.0, "tiktok": 7.5}


def modeled_quote(platform, followers):
    per_1k = QUOTE_PER_1K.get(platform, 10.0)
    return max(250, int(math.floor(followers / 1000 * per_1k / 250 + 0.5) * 250))


def is_crossplatform(data):
    return bool((data.get("crossplatform") or {}).get("external"))


class _Pool:
    """Planner-shaped view used by the assistant and routes: by_id, creators, metadata."""

    def __init__(self, creators, metadata):
        self.creators = creators
        self.by_id = {c["id"]: c for c in creators}
        self.metadata = metadata


class CrossPlatformProvider:
    def __init__(self, data):
        self.youtube = RealDataProvider(data)
        self.metadata = data["metadata"]
        block = data["crossplatform"]
        yt_planner = self.youtube.planner
        profiles_raw = block.get("profiles") or {}
        creators = []
        for c in yt_planner.creators:
            followers = c.get("subscribers") or c.get("views") or 0
            creators.append({**c, "platform": "youtube", "topic": c["community"], "community": "YouTube", "followers": float(followers),
                             "cost": float(modeled_quote("youtube", followers)),
                             "url": "https://www.youtube.com/channel/%s" % c["id"] if c["id"].startswith("UC") else None,
                             "profile": audience_match.profile(profiles_raw.get(c["id"]))})
        for e in block["external"]:
            platform = str(e.get("platform") or "").lower()
            if platform not in ("instagram", "tiktok") or not e.get("followers"):
                continue
            followers = float(e["followers"])
            creators.append({"id": e["id"], "name": e.get("name") or e.get("handle") or e["id"], "handle": e.get("handle"), "url": e.get("url"),
                             "platform": platform, "topic": e.get("topic") or PLATFORM_LABEL[platform], "community": PLATFORM_LABEL[platform],
                             "followers": followers, "views": followers, "subscribers": followers, "cost": float(e.get("cost") or modeled_quote(platform, followers)),
                             "commenter_count": 0, "video_titles": [], "sponsor_mentions": None, "commenters": set(),
                             "profile": audience_match.profile(e.get("audience"))})
        self.planner = _Pool(creators, self.metadata)
        self.thin = set(self.youtube.thin)
        self.eligible = {c["id"] for c in creators if c["platform"] != "youtube" or c["id"] in self.youtube.eligible}
        campaign = dict(self.youtube.campaign)
        campaign["eligibleCategories"] = sorted({c["community"] for c in creators})
        self.campaign = campaign
        fingerprint = json.dumps({"data": data, "mode": "crossplatform"}, sort_keys=True, separators=(",", ":")).encode()
        self.dataset_version = "crossplatform-" + hashlib.sha256(fingerprint).hexdigest()[:16]
        self._shared = {}
        self._source = {}
        self.kappa, self.calibration_pairs = self._calibrate()
        self._overlap_cache = None
        self.default_roster_basis = "Biggest creators by followers across platforms that fit the budget: the roster a brand might pick without overlap data."

    # ---- pairwise evidence -------------------------------------------------------------------------------------
    def _measured(self, a, b):
        if a["platform"] != "youtube" or b["platform"] != "youtube" or not a["commenters"] or not b["commenters"]:
            return None
        mass = self.youtube.planner.mass
        shared = mass(a["commenters"] & b["commenters"])
        smaller = min(mass(a["commenters"]), mass(b["commenters"]))
        return shared / smaller if smaller else 0.0

    def _calibrate(self):
        yt = [c for c in self.planner.creators if c["platform"] == "youtube" and c["profile"] and c["commenters"]]
        num = den = 0.0
        pairs = 0
        for i, a in enumerate(yt):
            for b in yt[i + 1:]:
                scored = audience_match.match(a["profile"], b["profile"])
                measured = self._measured(a, b)
                if scored and measured is not None:
                    num += measured * scored["match"]
                    den += scored["match"] ** 2
                    pairs += 1
        if pairs < 3 or den <= 0:
            return DEFAULT_KAPPA, pairs
        return min(max(num / den, 0.02), 0.6), pairs

    def shared_fraction(self, a_id, b_id):
        key = (a_id, b_id) if a_id < b_id else (b_id, a_id)
        if key not in self._shared:
            a, b = self.planner.by_id[key[0]], self.planner.by_id[key[1]]
            measured = self._measured(a, b)
            if measured is not None:
                value, source = measured, "measured"
            else:
                scored = audience_match.match(a["profile"], b["profile"])
                value, source = self.kappa * (scored["match"] if scored else UNKNOWN_MATCH), "estimated" if scored else "assumed"
            self._shared[key], self._source[key] = min(max(value, 0.0), 1.0), source
        return self._shared[key]

    def pair_source(self, a_id, b_id):
        self.shared_fraction(a_id, b_id)
        return self._source[(a_id, b_id) if a_id < b_id else (b_id, a_id)]

    # ---- roster math -------------------------------------------------------------------------------------------
    def _size(self, cid, ctx):
        c = self.planner.by_id[cid]
        return c["followers"] * float((ctx.get("relevance") or {}).get(c["community"], 1.0))

    def stats(self, ids, ctx):
        ids = list(dict.fromkeys(ids))
        sizes = {i: self._size(i, ctx) for i in ids}
        standalone = sum(sizes.values())
        duplicated = 0.0
        for n, a in enumerate(ids):
            for b in ids[n + 1:]:
                duplicated += self.shared_fraction(a, b) * min(sizes[a], sizes[b])
        unique = max(standalone - duplicated, max(sizes.values(), default=0.0))
        return {"reach": unique, "standalone": standalone, "shared": standalone - unique,
                "rate": (standalone - unique) / standalone if standalone else 0.0,
                "spend": sum(ctx["costs"][i] for i in ids)}

    def marginal(self, cid, ids, ctx):
        return self.stats(list(ids) + [cid], ctx)["reach"] - self.stats(ids, ctx)["reach"] if ids else self._size(cid, ctx)

    def evidence_mix(self, ids):
        ids = list(dict.fromkeys(ids))
        counts = {"measured": 0, "estimated": 0, "assumed": 0}
        for n, a in enumerate(ids):
            for b in ids[n + 1:]:
                counts[self.pair_source(a, b)] += 1
        total = sum(counts.values())
        return {**counts, "pairs": total, "measuredShare": counts["measured"] / total if total else None}

    # ---- constraints -------------------------------------------------------------------------------------------
    def context(self, request):
        budget = request.get("budget")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            raise PlanError("Budget must be a nonnegative whole-dollar amount.")
        planning = request.get("planningContext") or {}
        if not isinstance(planning, dict) or set(planning) - {"brandDescription", "relevance", "maxPerGroup", "creatorCount"}:
            raise PlanError("Unsupported planning context.")
        ids = set(self.planner.by_id)
        for key in ("currentRoster", "include", "exclude"):
            values = request.get(key, [])
            if not isinstance(values, list) or any(v not in ids for v in values):
                raise PlanError("Some creators in %s aren't in the active search (it may have changed in another tab). Refresh the page." % key)
        include, exclude = list(dict.fromkeys(request.get("include", []))), list(dict.fromkeys(request.get("exclude", [])))
        if set(include) & set(exclude):
            raise PlanError("A creator cannot be both required and excluded.")
        blocked = [i for i in include if i not in self.eligible]
        if blocked:
            raise PlanError("Required creator can't be planned: " + ", ".join(self.planner.by_id[i]["name"] for i in blocked))
        costs = request.get("costs", {})
        if not isinstance(costs, dict) or set(costs) - ids or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in costs.values()):
            raise PlanError("Costs must map known creator IDs to nonnegative whole dollars.")
        groups = {c["community"] for c in self.planner.creators}
        caps = planning.get("maxPerGroup") or {}
        if not isinstance(caps, dict) or any(g not in groups or isinstance(v, bool) or not isinstance(v, int) or v < 0 for g, v in caps.items()):
            raise PlanError("Caps must be nonnegative whole numbers per platform.")
        relevance = planning.get("relevance") or {}
        if not isinstance(relevance, dict) or any(g not in groups or not isinstance(v, (int, float)) or not 0 <= v <= 1 for g, v in relevance.items()):
            raise PlanError("Relevance must map platforms to weights between zero and one.")
        count = planning.get("creatorCount", 0)
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 100:
            raise PlanError("Creator count must be a whole number from 0 to 100.")
        full_costs = {c["id"]: float(costs.get(c["id"], c["cost"])) for c in self.planner.creators}
        if sum(full_costs[i] for i in include) > budget:
            raise PlanError("Required creators cost more than the budget. Raise it or release a requirement.")
        return {"budget": float(budget), "must_include": include, "exclude": sorted(set(exclude) | (ids - self.eligible)), "costs": full_costs,
                "max_per_group": dict(caps), "relevance": dict(relevance), "creator_count": count,
                "brand_description": planning.get("brandDescription", "")}

    def feasible(self, ids, ctx):
        if not ids or len(set(ids)) != len(ids) or any(i in ctx["exclude"] for i in ids):
            return False
        if not set(ctx["must_include"]) <= set(ids) or sum(ctx["costs"][i] for i in ids) > ctx["budget"] + 1e-8:
            return False
        if ctx["creator_count"] and len(ids) > ctx["creator_count"]:
            return False
        return all(sum(self.planner.by_id[i]["community"] == g for i in ids) <= cap for g, cap in ctx["max_per_group"].items())

    # ---- search ------------------------------------------------------------------------------------------------
    def _greedy(self, ctx, mode):
        selected = list(ctx["must_include"])
        target = ctx["creator_count"]
        pool = [c["id"] for c in self.planner.creators if c["id"] not in ctx["exclude"]]
        while not target or len(selected) < target:
            best = None
            for cid in pool:
                if cid in selected or not self.feasible(selected + [cid], ctx):
                    continue
                gain = self.marginal(cid, selected, ctx)
                if gain <= 1e-9 and not target:
                    continue
                score = {"ratio": gain / ctx["costs"][cid] if ctx["costs"][cid] else math.inf, "gain": gain,
                         "followers": self.planner.by_id[cid]["followers"]}[mode]
                if best is None or score > best[0]:
                    best = (score, cid)
            if best is None:
                break
            selected.append(best[1])
        return selected

    def _choose(self, ctx, current):
        candidates = {m: self._greedy(ctx, m) for m in ("ratio", "gain", "followers")}
        runs = [ids for ids in candidates.values() if ids]
        if current and self.feasible(current, ctx):
            runs.append(list(current))
        target = ctx["creator_count"]
        def reach_key(ids):
            return (min(len(ids), target) if target else 0, self.stats(ids, ctx)["reach"])
        max_reach = max(runs, key=reach_key, default=[])
        floor_ids = current if current and self.feasible(current, ctx) else max_reach
        if not floor_ids:
            return max_reach, candidates
        floor = self.stats(floor_ids, ctx)["reach"] - 1e-6
        min_size = min(target, len(max_reach)) if target else 1
        pool = [c["id"] for c in self.planner.creators if c["id"] not in ctx["exclude"]]
        def ok(ids):
            return len(ids) >= min_size and self.feasible(ids, ctx) and self.stats(ids, ctx)["reach"] >= floor
        def key(ids):
            s = self.stats(ids, ctx)
            return (round(s["rate"], 9), -s["reach"], s["spend"])
        best = None
        for seed in {frozenset(r): r for r in runs + [floor_ids]}.values():
            if not ok(seed):
                continue
            roster = list(seed)
            for _ in range(3):
                fixed = set(ctx["must_include"])
                moves = [[x for x in roster if x != m] for m in roster if m not in fixed]
                moves += [roster + [c] for c in pool if c not in roster]
                moves += [[x for x in roster if x != m] + [c] for m in roster if m not in fixed for c in pool if c not in roster]
                step = min((ids for ids in moves if ok(ids)), key=key, default=None)
                if step is None or key(step) >= key(roster):
                    break
                roster = step
            if best is None or key(roster) < key(best):
                best = roster
        if best is None and max_reach:
            # No roster at the requested size can match your reach: find the highest-reach roster of that size instead.
            def reach_ok(ids):
                return len(ids) >= min_size and self.feasible(ids, ctx)
            best = list(max_reach)
            for _ in range(4):
                fixed = set(ctx["must_include"])
                moves = [[x for x in best if x != m] + [c] for m in best if m not in fixed for c in pool if c not in best]
                moves += [best + [c] for c in pool if c not in best]
                step = max((ids for ids in moves if reach_ok(ids)), key=lambda ids: (self.stats(ids, ctx)["reach"], -self.stats(ids, ctx)["rate"]), default=None)
                if step is None or self.stats(step, ctx)["reach"] <= self.stats(best, ctx)["reach"] + 1e-6:
                    break
                best = step
        return (best or max_reach), candidates

    # ---- payloads ----------------------------------------------------------------------------------------------
    def _score(self, ids, ctx):
        s = self.stats(ids, ctx)
        return {"ids": list(ids), "spend": s["spend"], "proxyReach": round(s["reach"], 2), "rawViews": s["standalone"],
                "overlappingCommenters": round(s["shared"]), "observedCommenterCoverage": round(s["reach"]),
                "evidenceNote": "Estimated unique followers; overlap blends measured YouTube comments with Upriver audience-profile estimates.",
                "flaggedIds": [], "notes": [], "metricUnit": "estimated_unique_followers", "observedUnit": "estimated_unique_followers"}

    def _diag(self, ids, ctx):
        s = self.stats(ids, ctx)
        return {"ids": list(ids), "spend": round(s["spend"]), "coverage": round(s["reach"]), "standalone": round(s["standalone"]),
                "shared": round(s["shared"]), "sharedRate": round(s["rate"], 4), "topics": [], "evidence": [], "evidenceMix": self.evidence_mix(ids)}

    def _trace(self, ids, ctx):
        steps, chosen = [], []
        remaining = list(ids)
        while remaining:
            cid = max(remaining, key=lambda i: self.marginal(i, chosen, ctx))
            gain = self.marginal(cid, chosen, ctx)
            c = self.planner.by_id[cid]
            steps.append({"creatorId": cid, "creatorName": c["name"], "marginalProxyReach": round(gain, 2), "cost": ctx["costs"][cid],
                          "reason": "%s (%s) adds about %s new followers after estimated overlap." % (c["name"], PLATFORM_LABEL[c["platform"]], format(round(gain), ","))})
            chosen.append(cid)
            remaining.remove(cid)
        return steps

    def _why_not(self, selected, ctx):
        rows = []
        spend = sum(ctx["costs"][i] for i in selected)
        for c in self.planner.creators:
            cid = c["id"]
            if cid in selected or cid not in self.eligible:
                continue
            if cid in ctx["exclude"]:
                reason = "Excluded by your campaign constraint."
            elif sum(self.planner.by_id[i]["community"] == c["community"] for i in selected) >= ctx["max_per_group"].get(c["community"], math.inf):
                reason = "Community cap reached."
            elif ctx["costs"][cid] > ctx["budget"] - spend + 1e-8:
                reason = "Quote exceeds the remaining budget in this plan."
            else:
                reason = "Adds too few new followers for its quote after overlap."
            gain = self.marginal(cid, selected, ctx) if selected else self._size(cid, ctx)
            size = self._size(cid, ctx)
            overlaps = sorted(({"creatorId": o, "creatorName": self.planner.by_id[o]["name"],
                                "sharedCommenters": round(self.shared_fraction(cid, o) * min(size, self._size(o, ctx))),
                                "source": self.pair_source(cid, o)} for o in selected), key=lambda x: -x["sharedCommenters"])[:3]
            rows.append({"creatorId": cid, "creatorName": c["name"], "reason": reason, "cost": ctx["costs"][cid],
                         "marginalProxyReach": round(gain, 2), "alreadyCoveredShare": round(1 - gain / size, 4) if size else 0,
                         "overlapsWith": [o for o in overlaps if o["sharedCommenters"] > 0], "platform": c["platform"]})
        rows.sort(key=lambda r: (-r["alreadyCoveredShare"], r["creatorName"]))
        return rows

    def plan_payload(self, request):
        if not isinstance(request, dict) or set(request) - {"budget", "currentRoster", "include", "exclude", "costs", "planningContext"}:
            raise PlanError("Plan requires budget/currentRoster and accepts include/exclude/costs/planningContext only.")
        ctx = self.context(request)
        current = [i for i in dict.fromkeys(request.get("currentRoster", [])) if i in self.planner.by_id]
        selected, runs = self._choose(ctx, current)
        baseline = runs["followers"]
        pool = [c for c in self.planner.creators if c["id"] not in ctx["exclude"]]
        target = ctx["creator_count"]
        count_note, needed = None, None
        if target and len(selected) < target:
            reachable = min(target, len(pool))
            parts = []
            if len(pool) < target:
                parts.append("Only %d creators can be planned, so %d is the most possible." % (len(pool), len(pool)))
            if len(selected) < reachable:
                cheapest = sum(sorted(ctx["costs"][c["id"]] for c in pool)[:reachable])
                if cheapest > ctx["budget"]:
                    needed = int(-(-cheapest // 250) * 250)
                    parts.append("The budget fits %d. %d creators need at least $%s." % (len(selected), reachable, format(needed, ",")))
                else:
                    parts.append("Platform caps or required creators leave room for only %d." % len(selected))
            count_note = " ".join(parts) or None
        mix = self.evidence_mix(selected)
        mine_diag, rec_diag = self._diag(current, ctx), self._diag(selected, ctx)
        why = choice.explain(mine_diag, rec_diag, unit="followers", current_ids=current,
                             feasible_reason=choice.infeasible_reason(current, ctx, self.planner.by_id), creator_count=target, evidence_mix=mix)
        return {"campaign": self.campaign, "datasetLabel": self.dataset_label(), "datasetKind": "crossplatform", "datasetVersion": self.dataset_version,
                "metricLabel": "Estimated unique followers; overlap blends measured YouTube comments with Upriver audience-profile estimates",
                "planningContext": {"brandDescription": ctx["brand_description"], "relevance": ctx["relevance"], "maxPerGroup": ctx["max_per_group"], "creatorCount": target},
                "creatorMetricLabels": {"views": "Followers", "price": "Quote (USD)", "rawViews": "Total followers"}, "budget": int(ctx["budget"]),
                "current": self._score(current, ctx), "recommended": self._score(selected, ctx), "viewsBaseline": self._score(baseline, ctx),
                "rosterDiagnostics": {"unitLabel": "estimated followers", "rosters": {"current": mine_diag, "recommended": rec_diag, "viewsBaseline": self._diag(baseline, ctx)}, "pairOverlaps": {}},
                "choice": why,
                "steps": self._trace(selected, ctx), "whyNot": self._why_not(selected, ctx), "countNote": count_note, "countBudgetNeeded": needed,
                "currentFlags": [], "remainingBudget": int(ctx["budget"] - sum(ctx["costs"][i] for i in selected)),
                "planningMethod": "Lowest estimated overlap among rosters that reach at least as many estimated unique followers as yours.",
                "evidenceMix": mix, "method": self.method(), "metricUnit": "followers"}

    def dataset_label(self):
        counts = {}
        for c in self.planner.creators:
            if c["id"] in self.eligible:
                counts[PLATFORM_LABEL[c["platform"]]] = counts.get(PLATFORM_LABEL[c["platform"]], 0) + 1
        return "Cross-platform pool · " + " · ".join("%d %s" % (n, p) for p, n in sorted(counts.items()))

    def method(self):
        return {"kappa": round(self.kappa, 4), "calibrationPairs": self.calibration_pairs, "defaultKappa": DEFAULT_KAPPA,
                "unknownMatch": UNKNOWN_MATCH, "weights": audience_match.WEIGHTS, "quotePer1k": QUOTE_PER_1K}

    def creators_payload(self):
        youtube = {r["id"]: r for r in self.youtube.creators_payload()["creators"]}
        rows = []
        for c in self.planner.creators:
            base = youtube.get(c["id"], {})
            rows.append({**base, "id": c["id"], "name": c["name"], "vertical": c["topic"], "category": "%s · %s" % (PLATFORM_LABEL[c["platform"]], c["topic"]),
                         "platform": c["platform"], "url": c.get("url"), "followers": round(c["followers"]),
                         "eligibilityStatus": "eligible" if c["id"] in self.eligible else "ineligible",
                         "eligibilityReason": base.get("eligibilityReason") or "Instagram/TikTok creator from Upriver search.",
                         "estimatedViews": c["followers"], "baseCost": int(c["cost"]), "commenterCount": c.get("commenter_count", 0),
                         "source": "observed-public", "audienceSummary": audience_match.summary(c["profile"]), "hasAudienceData": c["profile"] is not None,
                         "audienceDescription": (c["profile"] or {}).get("description"),
                         "overlapEvidence": "measured + estimated" if c["platform"] == "youtube" else "estimated"})
        pool = [c for c in self.planner.creators if c["id"] in self.eligible]
        total = sum(c["cost"] for c in pool)
        budget = int(max(min((c["cost"] for c in pool), default=250) * 3, round(total * 0.4 / 250) * 250)) if pool else 1000
        roster, spend = [], 0
        for c in sorted(pool, key=lambda c: (-c["followers"], c["name"])):
            if spend + c["cost"] <= budget:
                roster.append(c["id"])
                spend += c["cost"]
        samples = sorted(c["commenter_count"] for c in pool if c["platform"] == "youtube")
        median = samples[len(samples) // 2] if samples else 0
        return {"campaign": self.campaign, "datasetLabel": self.dataset_label(), "datasetKind": "crossplatform", "datasetVersion": self.dataset_version,
                "metricLabel": "Estimated unique followers", "creatorMetricLabels": {"views": "Followers", "price": "Quote (USD)", "rawViews": "Total followers"},
                "creators": rows, "defaultCurrentRoster": roster, "defaultBudget": budget, "defaultRosterBasis": self.default_roster_basis,
                "provenance": {"kind": "crossplatform"}, "method": self.method(),
                "evidence": {"medianSampledCommenters": median, "eligibleCreators": len(self.eligible), "thinCreators": len(self.thin),
                             "strength": "moderate"}}

    def overlap_payload(self):
        if self._overlap_cache is None:
            ctx = {"relevance": {}}
            nodes = [{"id": c["id"], "name": c["name"], "sampledCommenters": round(c["followers"]), "platform": c["platform"]}
                     for c in self.planner.creators if c["id"] in self.eligible]
            pairs = []
            for n, a in enumerate(nodes):
                for b in nodes[n + 1:]:
                    frac = self.shared_fraction(a["id"], b["id"])
                    shared = frac * min(self._size(a["id"], ctx), self._size(b["id"], ctx))
                    union = a["sampledCommenters"] + b["sampledCommenters"] - shared
                    pairs.append({"a": a["id"], "b": b["id"], "sharedCommenters": round(shared), "jaccard": shared / union if union else 0,
                                  "source": self.pair_source(a["id"], b["id"])})
            self._overlap_cache = {"datasetVersion": self.dataset_version, "nodes": nodes, "pairs": pairs, "clusters": [], "unit": "estimated_followers",
                                   "metric": "Estimated shared followers: measured for YouTube pairs, estimated from audience profiles otherwise."}
        return self._overlap_cache


def load_provider(data):
    return CrossPlatformProvider(data) if is_crossplatform(data) else RealDataProvider(data)
