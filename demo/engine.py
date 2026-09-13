"""Dependency-free reach planning engine; view-scaled commenter overlap is a proxy."""
import math
import random


class PlanError(ValueError):
    pass


def fixture():
    # Deterministic non-crypto fixture data only.
    rng = random.Random(72)  # nosec B311
    groups = {
        "Espresso": ["Daily Dial", "Crema Club", "Shot Theory", "Portafilter Lab", "Home Barista Notes", "Pressure Profile"],
        "Filter": ["Bloom Journal", "Pour Stories", "Paper & Water", "The Slow Cup", "Brew Geometry", "Light Roast Lab"],
        "Gear": ["Burr Bench", "Counter Culture Lab", "Grind Studies", "Small Kitchen Coffee", "Coffee Workbench", "Quiet Mornings"],
    }
    creators = []
    for gi, (group, names) in enumerate(groups.items()):
        for j, name in enumerate(names):
            idx = gi * 6 + j
            common = list(range(90))
            cluster = list(range(100 + gi * 350, 330 + gi * 350))
            own = list(range(2000 + idx * 100, 2100 + idx * 100))
            commenters = rng.sample(common, 35) + rng.sample(cluster, 200 - j * 22) + rng.sample(own, 40 + j * 10)
            views = [150000, 127000, 90000, 68000, 47000, 34000][j] + gi * 3700
            creators.append({"id": "creator-%02d" % (idx + 1), "name": name,
                             "community": group, "views": views,
                             "subscribers": [620000, 440000, 250000, 145000, 87000, 51000][j] + gi * 18000,
                             "cost": [4200, 3500, 2300, 1500, 1050, 720][j] + gi * 100,
                             "commenters": [str(x) for x in commenters]})
    return {"metadata": {"kind": "synthetic", "title": "Home coffee · fictional demonstration",
                          "source": "Deterministic synthetic fixture; all creator names, comments, views and quotes are invented.",
                          "validation": "Not validated against real audiences or campaign results."}, "creators": creators}


def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise PlanError("%s must be a finite number >= %s." % (label, minimum))
    return float(value)


class Planner:
    def __init__(self, data):
        self.metadata = data.get("metadata", {})
        if self.metadata.get("kind") not in ("synthetic", "observed"):
            raise PlanError("Dataset metadata.kind must be synthetic or observed.")
        self.creators = []
        self.masses = {}
        rows = [dict(row) for row in data.get("creators", [])]
        segments = data.get("audience_segments")
        if segments is not None:
            if not isinstance(segments, list) or not segments:
                raise PlanError("audience_segments must be a nonempty list.")
            ids = {row["id"] for row in rows}
            membership = {cid: [] for cid in ids}
            for n, segment in enumerate(segments):
                members = segment.get("creators")
                count = segment.get("count")
                if not isinstance(members, list) or not members or set(members) - ids or len(set(members)) != len(members):
                    raise PlanError("Audience segment membership must use unique known creator IDs.")
                if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                    raise PlanError("Audience segment counts must be positive integers.")
                key = "segment-%d" % n
                self.masses[key] = count
                for cid in members:
                    membership[cid].append(key)
            for row in rows:
                row["commenters"] = membership[row["id"]]
        for row in rows:
            c = dict(row)
            for key in ("id", "name", "community"):
                if not isinstance(c.get(key), str) or not c[key].strip():
                    raise PlanError("Each creator needs a nonempty %s." % key)
            for key in ("views", "subscribers", "cost"):
                c[key] = number(c.get(key), key, 0)
            ids = c.get("commenters")
            if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids):
                raise PlanError("Every creator needs a nonempty list of commenter IDs; missing evidence cannot imply no overlap.")
            c["commenters"] = set(ids)
            c["commenter_count"] = self.mass(c["commenters"])
            c["weight"] = c["views"] / c["commenter_count"]
            self.creators.append(c)
        self.by_id = {c["id"]: c for c in self.creators}
        if not self.creators or len(self.by_id) != len(self.creators):
            raise PlanError("Dataset must contain creators with unique IDs.")
        self.segment_groups = {}
        for c in self.creators:
            for sid in c["commenters"]:
                self.segment_groups.setdefault(sid, set()).add(c["community"])

    def mass(self, ids):
        return sum(self.masses.get(i, 1) for i in ids)

    def weight(self, c, ctx=None):
        return 1.0 if (ctx or {}).get("objective") == "observed_commenters" else c["weight"]

    def relevance(self, sid, ctx=None):
        scores = (ctx or {}).get("relevance", {})
        return max((scores.get(g, 1) for g in self.segment_groups[sid]), default=1) if scores else 1

    def public(self, c):
        return {k: v for k, v in c.items() if k not in ("commenters", "weight")}

    def provenance(self):
        return {**self.metadata, "estimate_type": "Uncalibrated view-scaled commenter-overlap score; not unique viewer reach",
                "validation": "No viewer-level or campaign-outcome validation supplied."}

    def context(self, request):
        if not isinstance(request, dict):
            raise PlanError("Request must be a JSON object.")
        allowed = {"budget", "must_include", "exclude", "max_per_group", "costs", "objective", "relevance", "brand_description", "creator_count"}
        unknown = set(request) - allowed
        if unknown:
            raise PlanError("Unsupported planner fields: " + ", ".join(sorted(unknown)))
        budget = number(request.get("budget", 10000), "Budget")
        objective = request.get("objective", self.metadata.get("reach_unit", "viewer_proxy"))
        if objective not in ("observed_commenters", "viewer_proxy"):
            raise PlanError("Objective must be observed_commenters or viewer_proxy.")
        relevance = request.get("relevance", {})
        if not isinstance(relevance, dict) or set(relevance) - {c["community"] for c in self.creators}:
            raise PlanError("Relevance must map known communities to weights between zero and one.")
        for value in relevance.values():
            if number(value, "Relevance") > 1:
                raise PlanError("Relevance weights cannot exceed one.")
        brand = request.get("brand_description", "")
        if not isinstance(brand, str) or len(brand) > 2000:
            raise PlanError("Brand description must be text under 2000 characters.")
        if budget > 100000000:
            raise PlanError("Budget exceeds the supported demo limit.")
        lists = {}
        for key in ("must_include", "exclude"):
            values = request.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or v not in self.by_id for v in values):
                raise PlanError("%s must contain known creator IDs." % key)
            lists[key] = list(dict.fromkeys(values))
        if set(lists["must_include"]) & set(lists["exclude"]):
            raise PlanError("A creator cannot be both required and excluded.")
        costs = request.get("costs", {})
        if not isinstance(costs, dict) or set(costs) - set(self.by_id):
            raise PlanError("Costs must map known creator IDs to nonnegative quotes.")
        costs = {c["id"]: number(costs.get(c["id"], c["cost"]), "Creator quote", 0) for c in self.creators}
        caps = request.get("max_per_group", {})
        if not isinstance(caps, dict):
            raise PlanError("max_per_group must be an object.")
        groups = {c["community"] for c in self.creators}
        for group, cap in caps.items():
            if group not in groups or isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
                raise PlanError("Group caps must be nonnegative integers for known communities.")
        required = lists["must_include"]
        count = request.get("creator_count", 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0 or count > 100:
            raise PlanError("Creator count must be a whole number from 0 (no target) to 100.")
        if count and len(required) > count:
            raise PlanError("You required %d creators but asked for %d in total." % (len(required), count))
        if sum(costs[i] for i in required) > budget + 1e-8:
            raise PlanError("Required creators cost more than the budget. Raise it or release a requirement.")
        for group, cap in caps.items():
            if sum(self.by_id[i]["community"] == group for i in required) > cap:
                raise PlanError("Required creators exceed the %s community cap." % group)
        return {"budget": budget, **lists, "costs": costs, "max_per_group": dict(caps),
                "objective": objective, "relevance": dict(relevance), "brand_description": brand, "creator_count": count}

    def coverage(self, ids, ctx=None):
        best = {}
        for cid in ids:
            c = self.by_id[cid]
            for i in c["commenters"]:
                best[i] = max(best.get(i, 0), self.weight(c, ctx))
        return best

    def gain(self, c, best, ctx=None):
        return math.fsum(max(self.weight(c, ctx) - best.get(i, 0), 0) * self.masses.get(i, 1) * self.relevance(i, ctx) for i in c["commenters"])

    def summarize(self, ids, ctx):
        best, trace = {}, []
        for cid in ids:
            c = self.by_id[cid]
            gain = self.gain(c, best, ctx)
            standalone = self.gain(c, {}, ctx)
            trace.append({"id": cid, "name": c["name"], "marginal_gain": gain,
                          "incremental_share": gain / standalone if standalone else 0,
                          "cost": ctx["costs"][cid], "required": cid in ctx["must_include"]})
            for i in c["commenters"]:
                best[i] = max(best.get(i, 0), self.weight(c, ctx))
        return {"selected": ids, "reach_est": math.fsum(w * self.masses.get(i, 1) * self.relevance(i, ctx) for i, w in best.items()),
                "naive_sum": math.fsum(self.gain(self.by_id[i], {}, ctx) for i in ids),
                "spend": math.fsum(ctx["costs"][i] for i in ids), "trace": trace}

    def run(self, ctx, mode):
        selected = list(ctx["must_include"])
        best = self.coverage(selected, ctx)
        spend = sum(ctx["costs"][i] for i in selected)
        target = ctx.get("creator_count", 0)
        while not target or len(selected) < target:
            candidates = []
            for c in self.creators:
                cid, group = c["id"], c["community"]
                if cid in selected or cid in ctx["exclude"] or spend + ctx["costs"][cid] > ctx["budget"] + 1e-8:
                    continue
                if sum(self.by_id[i]["community"] == group for i in selected) >= ctx["max_per_group"].get(group, math.inf):
                    continue
                gain = self.gain(c, best, ctx)
                if gain <= 1e-8 and mode in ("ratio", "gain") and not target:
                    continue  # with a creator-count target, zero-gain picks still fill the requested slots
                score = {"ratio": (gain / ctx["costs"][cid] if ctx["costs"][cid] else (math.inf if gain > 0 else 0)), "gain": gain,
                         "subscribers": c["subscribers"], "views": c["views"]}[mode]
                candidates.append((score, cid))
            if not candidates:
                break
            cid = max(candidates)[1]
            selected.append(cid)
            spend += ctx["costs"][cid]
            c = self.by_id[cid]
            for i in c["commenters"]:
                best[i] = max(best.get(i, 0), self.weight(c, ctx))
        return self.summarize(selected, ctx)

    def optimize(self, request):
        ctx = self.context(request)
        runs = {mode: self.run(ctx, mode) for mode in ("ratio", "gain", "subscribers", "views")}
        target = ctx.get("creator_count", 0)
        # With a creator-count target, prefer heuristics that actually reach it; fall back to the best available.
        pool = [k for k in runs if not target or len(runs[k]["selected"]) >= target] or list(runs)
        winner = max(pool, key=lambda k: (min(len(runs[k]["selected"]), target) if target else 0, runs[k]["reach_est"], -runs[k]["spend"]))
        result = dict(runs[winner])
        best = self.coverage(result["selected"], ctx)
        rejected = []
        for c in self.creators:
            cid = c["id"]
            if cid in result["selected"]:
                continue
            group_count = sum(self.by_id[i]["community"] == c["community"] for i in result["selected"])
            if cid in ctx["exclude"]:
                reason = "Excluded by your campaign constraint."
            elif group_count >= ctx["max_per_group"].get(c["community"], math.inf):
                reason = "Community cap reached."
            elif ctx["costs"][cid] > ctx["budget"] - result["spend"] + 1e-8:
                reason = "Quote exceeds the remaining budget in this plan."
            else:
                reason = "No additional objective value, or another candidate set scored higher in the heuristic search."
            overlaps = []
            for sid in result["selected"]:
                other = self.by_id[sid]
                shared = self.mass(c["commenters"] & other["commenters"])
                if shared:
                    overlaps.append({"id": sid, "name": other["name"], "shared_commenters": shared})
            gain = self.gain(c, best, ctx)
            standalone = self.gain(c, {}, ctx)
            rejected.append({"id": cid, "name": c["name"], "reason": reason,
                             "marginal_gain": gain, "represented_fraction": 1 - gain / standalone if standalone else 0,
                             "overlaps_with": sorted(overlaps, key=lambda x: -x["shared_commenters"])[:3]})
        result.update({"budget": ctx["budget"], "constraints": ctx, "rejected": rejected,
                       "baselines": {"top_subs": runs["subscribers"], "top_views": runs["views"]},
                       "method": "Best of marginal-gain-per-dollar greedy, marginal-gain greedy, and the two ranked baselines. Heuristic; no optimality certificate.",
                       "winning_strategy": winner, "provenance": self.provenance(), "reach_unit": ctx["objective"],
                       "relevance_weighted": bool(ctx["relevance"]),
                       "baseline_labels": {"top_subs": self.metadata.get("subscriber_basis", "Largest by subscribers"), "top_views": "Largest by historical views" if self.metadata["kind"] == "observed" else "Largest by views"}})
        return result

    def audit(self, request):
        if not isinstance(request, dict) or set(request) - {"roster_ids", "budget", "costs", "objective", "relevance", "brand_description"}:
            raise PlanError("Audit accepts roster_ids, optional budget, costs, objective, relevance and brand_description.")
        ids = request.get("roster_ids", [])
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in self.by_id for i in ids):
            raise PlanError("Select at least one known creator to audit.")
        ids = list(dict.fromkeys(ids))
        ctx = self.context({k: v for k, v in request.items() if k != "roster_ids"})
        summary = self.summarize(ids, ctx)
        budget = request.get("budget", summary["spend"])
        alternative = self.optimize({**ctx, "budget": budget})
        # Keep the original roster as a feasible candidate so a heuristic cannot claim an inferior improvement.
        if summary["spend"] <= budget and summary["reach_est"] > alternative["reach_est"]:
            alternative = {**alternative, **summary, "rejected": [], "winning_strategy": "original_roster"}
        return {**summary, "duplicated_fraction": 1 - summary["reach_est"] / summary["naive_sum"] if summary["naive_sum"] else 0,
                "comparison_budget": budget, "optimized_alternative": alternative, "provenance": self.provenance(), "reach_unit": ctx["objective"]}

    def graph(self):
        groups = list(dict.fromkeys(c["community"] for c in self.creators))
        nodes, edges = [], []
        ordered = sorted(self.creators, key=lambda c: (groups.index(c["community"]), c["name"].lower()))
        columns = min(7, max(1, math.ceil(math.sqrt(len(ordered) * 1.4))))
        rows = math.ceil(len(ordered) / columns)
        for index, c in enumerate(ordered):
            column, row = index % columns, index // columns
            # A readable topic-ordered grid; no geometric similarity claim.
            x = 65 + column * (710 / max(columns - 1, 1))
            y = 55 + row * (440 / max(rows - 1, 1))
            nodes.append({**self.public(c), "x": x, "y": y})
        for a, c in enumerate(self.creators):
            for other in self.creators[a + 1:]:
                shared = self.mass(c["commenters"] & other["commenters"])
                overlap = shared / self.mass(c["commenters"] | other["commenters"])
                if overlap > 0:
                    edges.append({"source": c["id"], "target": other["id"], "overlap": overlap, "shared_commenters": shared})
        return {"nodes": nodes, "edges": edges, "provenance": self.provenance(),
                "layout": "Topic-ordered grid; distances do not measure overlap. Edges show measured commenter Jaccard."}
