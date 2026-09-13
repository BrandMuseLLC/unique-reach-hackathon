"""Headline numbers from an observed aggregate, computed the same way the planner computes them.

For each budget: the planner's roster versus the largest-by-subscribers and largest-by-views rosters under
identical quotes and constraints, in both units (view-scaled proxy and exact sampled commenters), plus an
accounting split of the gain into bigger audiences versus less overlap. Also audits the biggest roster.
"""
from __future__ import annotations

from demo.engine import Planner


def _split(planner: Planner, ids: list[str], ctx: dict) -> dict:
    summary = planner.summarize(ids, ctx)
    return {"reach": summary["reach_est"], "standalone": summary["naive_sum"],
            "overlap_penalty": summary["naive_sum"] - summary["reach_est"], "spend": summary["spend"]}


def compare(planner: Planner, budget: float, objective: str) -> dict:
    ctx = planner.context({"budget": budget, "objective": objective})
    plan = planner.optimize(ctx)
    rows = {"planner": plan["selected"], "top_subscribers": plan["baselines"]["top_subs"]["selected"],
            "top_views": plan["baselines"]["top_views"]["selected"]}
    scored = {name: {"ids": ids, **_split(planner, ids, ctx)} for name, ids in rows.items()}
    out = {"budget": budget, "objective": objective, "winning_strategy": plan["winning_strategy"], "rosters": scored}
    for base in ("top_subscribers", "top_views"):
        b, p = scored[base], scored["planner"]
        out["vs_" + base] = {
            "lift": (p["reach"] - b["reach"]) / b["reach"] if b["reach"] else None,
            "from_bigger_audiences": p["standalone"] - b["standalone"],
            "from_less_overlap": b["overlap_penalty"] - p["overlap_penalty"],
        }
    return out


def audit_biggest(planner: Planner, size: int) -> dict:
    ranked = sorted(planner.creators, key=lambda c: -c["subscribers"])[:size]
    ids = [c["id"] for c in ranked]
    result = planner.audit({"roster_ids": ids, "objective": "observed_commenters"})
    alt = result["optimized_alternative"]
    return {"roster": [c["name"] for c in ranked], "spend": result["spend"],
            "sampled_commenters_reached": result["reach_est"], "sum_of_individual_audiences": result["naive_sum"],
            "duplicated_fraction": result["duplicated_fraction"],
            "same_budget_alternative": [planner.by_id[i]["name"] for i in alt["selected"]],
            "alternative_commenters_reached": alt["reach_est"],
            "note": "Sampled commenter accounts, not unique viewers. Quotes are the dataset's scenario values."}


def headline(data: dict, budgets: list[float], audit_size: int = 6) -> dict:
    planner = Planner(data)
    return {
        "dataset": data["metadata"].get("title"),
        "subscriber_baseline_basis": data["metadata"].get("subscriber_basis", "Largest by subscribers"),
        "comparisons": [compare(planner, b, obj) for b in budgets for obj in ("observed_commenters", "viewer_proxy")],
        "audit_biggest_by_subscribers": audit_biggest(planner, min(audit_size, len(planner.creators))),
        "rules": ["Report both baselines; never only the weaker one.",
                  "If from_less_overlap is small relative to from_bigger_audiences, the story is audience sizing, not deduplication.",
                  "Never present these as unique viewers or campaign lift."],
    }
