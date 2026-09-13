from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

import numpy as np


EligibilityStatus = Literal["eligible", "ineligible", "unknown"]
EvidenceState = Literal[
    "observed",
    "observed_zero",
    "not_collected",
    "unavailable_api",
    "quota_limited",
    "permission_limited",
    "parse_failed",
]


@dataclass(frozen=True)
class CampaignBrief:
    id: str
    name: str
    category: str
    audience: str
    eligible_categories: tuple[str, ...]


@dataclass(frozen=True)
class ObservationEvidence:
    state: EvidenceState
    sample_size: int
    source: Literal["synthetic"]
    provenance: str
    derived_feature_links: tuple[str, ...]


@dataclass(frozen=True)
class DerivedFeatures:
    category: str
    category_source: Literal["synthetic-observed", "synthetic-inferred", "unknown"]
    audience_note: str


@dataclass(frozen=True)
class CampaignEligibility:
    status: EligibilityStatus
    reason: str


@dataclass(frozen=True)
class Creator:
    id: str
    name: str
    vertical: str
    estimated_views: int
    base_cost: int
    commenters: frozenset[str]
    observations: ObservationEvidence
    features: DerivedFeatures
    eligibility: CampaignEligibility


@dataclass(frozen=True)
class ScoredRoster:
    ids: tuple[str, ...]
    spend: int
    proxy_reach: float
    raw_views: int
    overlapping_commenters: int
    evidence_note: str
    flagged_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class PlanningError(ValueError):
    pass


def campaign_brief() -> CampaignBrief:
    return CampaignBrief(
        id="sensitive-spf-launch",
        name="Sensitive-skin SPF launch",
        category="Beauty and skincare",
        audience="ingredient-curious skincare buyers comparing daily SPF routines",
        eligible_categories=("skincare", "beauty", "beauty-lifestyle"),
    )


def synthetic_creators() -> list[Creator]:
    clusters = {
        "spf_nerds": range(1, 24),
        "sensitive_skin": range(18, 44),
        "ingredient_readers": range(39, 66),
        "makeup_prep": range(60, 84),
        "derm_qna": range(79, 105),
        "budget_beauty": range(100, 124),
        "clean_beauty": range(118, 145),
        "luxury_beauty": range(140, 164),
        "travel_beauty": range(160, 181),
        "home_reset": range(176, 196),
        "wellness_adjacent": range(190, 211),
    }

    def commenters(*names: str) -> frozenset[str]:
        values: set[str] = set()
        for name in names:
            values.update(f"synthetic-viewer-{idx:03d}" for idx in clusters[name])
        return frozenset(values)

    def creator(
        creator_id: str,
        name: str,
        vertical: str,
        views: int,
        cost: int,
        cluster_names: tuple[str, ...],
        category: str,
        category_source: Literal["synthetic-observed", "synthetic-inferred", "unknown"],
        audience_note: str,
        eligibility: EligibilityStatus,
        eligibility_reason: str,
        sample_size: int,
        evidence_state: EvidenceState = "observed",
    ) -> Creator:
        return Creator(
            id=creator_id,
            name=name,
            vertical=vertical,
            estimated_views=views,
            base_cost=cost,
            commenters=commenters(*cluster_names) if evidence_state in {"observed", "observed_zero"} else frozenset(),
            observations=ObservationEvidence(
                state=evidence_state,
                sample_size=sample_size,
                source="synthetic",
                provenance="Synthetic public-comment sample generated for the hackathon demo; no live API collection.",
                derived_feature_links=("category", "audience_note", "overlap_proxy"),
            ),
            features=DerivedFeatures(category, category_source, audience_note),
            eligibility=CampaignEligibility(eligibility, eligibility_reason),
        )

    return [
        creator("lena-labs", "Lena Labs", "Skincare explainers", 420_000, 42_000, ("spf_nerds", "sensitive_skin"), "skincare", "synthetic-observed", "ingredient-curious skincare shoppers", "eligible", "Observed skincare/SPF content matches the sensitive-skin beauty brief.", 112),
        creator("maya-mirror", "Maya Mirror", "Makeup prep", 310_000, 27_000, ("makeup_prep", "budget_beauty"), "beauty", "synthetic-observed", "routine-led beauty buyers", "eligible", "Beauty routine audience is relevant to SPF-as-prep positioning.", 84),
        creator("glow-and-go", "Glow & Go", "Beauty lifestyle", 610_000, 70_000, ("spf_nerds", "sensitive_skin", "makeup_prep"), "beauty-lifestyle", "synthetic-observed", "beauty, wellness, and morning routine overlap", "eligible", "Large beauty-lifestyle channel with observed skincare routine overlap.", 136),
        creator("derm-desk", "Derm Desk", "Dermatology Q&A", 355_000, 39_000, ("derm_qna", "ingredient_readers"), "skincare", "synthetic-observed", "evidence-seeking skincare buyers", "eligible", "Derm Q&A topics directly match sensitive-skin SPF education.", 98),
        creator("spf-simplified", "SPF Simplified", "Sunscreen tests", 280_000, 25_000, ("spf_nerds", "ingredient_readers"), "skincare", "synthetic-observed", "sunscreen comparison shoppers", "eligible", "Observed sunscreen testing content is directly in-brief.", 76),
        creator("vanity-lab", "Vanity Lab", "Beauty science", 335_000, 33_000, ("ingredient_readers", "clean_beauty"), "skincare", "synthetic-observed", "ingredient readers and clean-beauty skeptics", "eligible", "Beauty science category is a direct campaign fit.", 91),
        creator("budget-glow", "Budget Glow", "Drugstore beauty", 300_000, 21_000, ("budget_beauty", "makeup_prep"), "beauty", "synthetic-observed", "value-focused beauty shoppers", "eligible", "Beauty buyer relevance is observed, with lower sponsor cost.", 72),
        creator("clean-shelf", "Clean Shelf", "Clean beauty", 260_000, 24_000, ("clean_beauty", "sensitive_skin"), "skincare", "synthetic-observed", "low-irritation skincare buyers", "eligible", "Sensitive-skin and clean-beauty overlap supports eligibility.", 69),
        creator("lux-lather", "Lux Lather", "Luxury beauty", 390_000, 44_000, ("luxury_beauty", "clean_beauty"), "beauty", "synthetic-observed", "premium beauty shoppers", "eligible", "Premium beauty audience is relevant but less efficiency-led.", 80),
        creator("skin-cycle-sage", "Skin Cycle Sage", "Barrier repair", 240_000, 18_000, ("sensitive_skin", "derm_qna"), "skincare", "synthetic-observed", "barrier-care routine planners", "eligible", "Barrier-care content aligns with sensitive-skin positioning.", 61),
        creator("serum-scout", "Serum Scout", "Skincare reviews", 295_000, 26_000, ("ingredient_readers", "budget_beauty"), "skincare", "synthetic-observed", "review-led skincare shoppers", "eligible", "Skincare review content and audience are directly relevant.", 73),
        creator("shade-match-nia", "Shade Match Nia", "Foundation matching", 270_000, 23_000, ("makeup_prep", "luxury_beauty"), "beauty", "synthetic-observed", "complexion-product buyers", "eligible", "Complexion routine audience can credibly evaluate SPF prep.", 66),
        creator("tiny-vanity", "Tiny Vanity", "Bathroom organization", 250_000, 20_000, ("home_reset", "clean_beauty"), "home", "synthetic-observed", "small-space organizers with some beauty shelf overlap", "ineligible", "Home organization adjacency is not enough evidence for a skincare campaign.", 58),
        creator("carry-on-cosmetics", "Carry-On Cosmetics", "Travel beauty", 305_000, 28_000, ("travel_beauty", "luxury_beauty"), "travel-beauty", "synthetic-inferred", "travel routine and cosmetics viewers", "unknown", "Category is adjacent, but the sampled evidence does not establish campaign relevance.", 22),
        creator("morning-mindful", "Morning Mindful", "Wellness routines", 375_000, 31_000, ("wellness_adjacent", "home_reset"), "wellness", "synthetic-observed", "self-care and wellness planners", "ineligible", "Wellness routine relevance is too broad for this beauty brief.", 64),
        creator("new-beauty-file", "New Beauty File", "Unclassified beauty lead", 180_000, 15_000, (), "unknown", "unknown", "lead imported without enough observed category evidence", "unknown", "Relevance is unknown because the synthetic sample was not collected, so it cannot enter recommendations.", 0, "not_collected"),
    ]


def normalize_costs(creators: Iterable[Creator], overrides: dict[str, int] | None = None) -> dict[str, int]:
    costs = {creator.id: creator.base_cost for creator in creators}
    for creator_id, cost in (overrides or {}).items():
        if not isinstance(cost, int) or cost < 0:
            raise PlanningError(f"Invalid cost for {creator_id}. Costs must be non-negative whole dollars.")
        if creator_id in costs:
            costs[creator_id] = cost
    return costs


def eligible_ids(creators: Iterable[Creator]) -> set[str]:
    return {creator.id for creator in creators if creator.eligibility.status == "eligible"}


def _viewer_weights(creators: Iterable[Creator]) -> dict[str, dict[str, float]]:
    weights: dict[str, dict[str, float]] = {}
    for creator in creators:
        if not creator.commenters:
            continue
        weight = creator.estimated_views / len(creator.commenters)
        for viewer_id in creator.commenters:
            weights.setdefault(viewer_id, {})[creator.id] = weight
    return weights


def evidence_note_for(ids: Iterable[str], creator_by_id: dict[str, Creator]) -> str:
    ordered_ids = tuple(dict.fromkeys(ids))
    if not ordered_ids:
        return "No creators selected."

    non_observed = [creator_by_id[creator_id] for creator_id in ordered_ids if creator_by_id[creator_id].observations.state != "observed"]
    if not non_observed:
        return "All selected creators have synthetic observed commenter samples for this demo."

    names = ", ".join(creator.name for creator in non_observed)
    states = ", ".join(sorted({creator.observations.state.replace("_", " ") for creator in non_observed}))
    return f"Overlap evidence is {states} for {names}; numeric absence is unknown, and observed zero is only zero within the sample."


def score_roster(ids: Iterable[str], creators: list[Creator], costs: dict[str, int]) -> ScoredRoster:
    creator_by_id = {creator.id: creator for creator in creators}
    ordered_ids = tuple(dict.fromkeys(ids))
    unknown = [creator_id for creator_id in ordered_ids if creator_id not in creator_by_id]
    if unknown:
        raise PlanningError(f"Unknown creator id: {', '.join(unknown)}")

    if not ordered_ids:
        return ScoredRoster((), 0, 0.0, 0, 0, "No creators selected.")

    viewer_weights = _viewer_weights(creators)
    selected = set(ordered_ids)
    proxy_reach = float(
        np.sum([
            max(weights[creator_id] for creator_id in selected if creator_id in weights)
            for weights in viewer_weights.values()
            if selected.intersection(weights)
        ])
    )
    raw_views = sum(creator_by_id[creator_id].estimated_views for creator_id in selected)
    all_commenters = [viewer for creator_id in selected for viewer in creator_by_id[creator_id].commenters]
    overlapping_commenters = len(all_commenters) - len(set(all_commenters))
    spend = sum(costs[creator_id] for creator_id in selected)
    flagged_ids = tuple(
        creator_id
        for creator_id in ordered_ids
        if creator_by_id[creator_id].eligibility.status != "eligible"
    )
    return ScoredRoster(
        ordered_ids,
        spend,
        round(proxy_reach, 2),
        raw_views,
        overlapping_commenters,
        evidence_note_for(ordered_ids, creator_by_id),
        flagged_ids,
    )


def _commenter_coverage(ids: Iterable[str], creator_by_id: dict[str, Creator]) -> int:
    commenters: set[str] = set()
    for creator_id in ids:
        commenters.update(creator_by_id[creator_id].commenters)
    return len(commenters)


def _topic_distribution(ids: Iterable[str], creator_by_id: dict[str, Creator], costs: dict[str, int]) -> list[dict[str, object]]:
    topics: dict[str, dict[str, object]] = {}
    for creator_id in ids:
        creator = creator_by_id[creator_id]
        topic = topics.setdefault(creator.features.category, {"name": creator.features.category, "count": 0, "spend": 0, "views": 0})
        topic["count"] = int(topic["count"]) + 1
        topic["spend"] = int(topic["spend"]) + costs[creator_id]
        topic["views"] = int(topic["views"]) + creator.estimated_views
    return sorted(topics.values(), key=lambda item: (-int(item["count"]), str(item["name"])))


def _evidence_distribution(ids: Iterable[str], creator_by_id: dict[str, Creator]) -> list[dict[str, object]]:
    states: dict[str, int] = {}
    for creator_id in ids:
        state = creator_by_id[creator_id].observations.state
        states[state] = states.get(state, 0) + 1
    return [{"state": state, "count": count} for state, count in sorted(states.items())]


def _pair_overlaps(ids: Iterable[str], creator_by_id: dict[str, Creator]) -> list[dict[str, object]]:
    ordered_ids = list(dict.fromkeys(ids))
    pairs = []
    for left_index, left_id in enumerate(ordered_ids):
        for right_id in ordered_ids[left_index + 1 :]:
            pairs.append({
                "a": left_id,
                "b": right_id,
                "count": len(creator_by_id[left_id].commenters & creator_by_id[right_id].commenters),
            })
    return pairs


def roster_diagnostics(rosters: dict[str, ScoredRoster], creators: list[Creator], costs: dict[str, int]) -> dict[str, object]:
    creator_by_id = {creator.id: creator for creator in creators}
    pair_sets = {name: _pair_overlaps(score.ids, creator_by_id) for name, score in rosters.items()}
    max_pair_overlap = max((int(pair["count"]) for pairs in pair_sets.values() for pair in pairs), default=0)
    summaries = {}
    for name, score in rosters.items():
        standalone = sum(len(creator_by_id[creator_id].commenters) for creator_id in score.ids)
        coverage = _commenter_coverage(score.ids, creator_by_id)
        shared = max(standalone - coverage, 0)
        summaries[name] = {
            "ids": list(score.ids),
            "spend": score.spend,
            "coverage": coverage,
            "standalone": standalone,
            "shared": shared,
            "sharedRate": round(shared / standalone, 4) if standalone else 0,
            "topics": _topic_distribution(score.ids, creator_by_id, costs),
            "evidence": _evidence_distribution(score.ids, creator_by_id),
        }
    return {
        "unitLabel": "synthetic commenters",
        "caveat": "Synthetic commenter sets are fictional demo evidence; this is not validated viewer reach.",
        "comparisonNote": "Recommended and views-ranked rosters use the same budget, required creators, exclusions, and eligible categories.",
        "maxPairOverlap": max_pair_overlap,
        "rosters": summaries,
        "pairOverlaps": pair_sets,
    }


def _validate_selected_ids(ids: Iterable[str], creator_by_id: dict[str, Creator]) -> None:
    unknown = [creator_id for creator_id in ids if creator_id not in creator_by_id]
    if unknown:
        raise PlanningError(f"Unknown creator id: {', '.join(sorted(set(unknown)))}")


def _blocked_required_creators(included: Iterable[str], creator_by_id: dict[str, Creator]) -> list[str]:
    blocked = []
    for creator_id in included:
        creator = creator_by_id[creator_id]
        if creator.eligibility.status != "eligible":
            blocked.append(f"{creator.name} is {creator.eligibility.status}: {creator.eligibility.reason}")
    return blocked


def greedy_plan(
    *,
    creators: list[Creator],
    budget: int,
    current_ids: Iterable[str],
    include_ids: Iterable[str] = (),
    exclude_ids: Iterable[str] = (),
    cost_overrides: dict[str, int] | None = None,
) -> dict[str, object]:
    if not isinstance(budget, int) or budget < 0:
        raise PlanningError("Budget must be a non-negative whole dollar amount.")

    costs = normalize_costs(creators, cost_overrides)
    creator_by_id = {creator.id: creator for creator in creators}
    current = tuple(dict.fromkeys(current_ids))
    included = tuple(dict.fromkeys(include_ids))
    excluded = set(exclude_ids)
    _validate_selected_ids((*current, *included, *excluded), creator_by_id)

    conflict = set(included).intersection(excluded)
    if conflict:
        raise PlanningError(f"Creator cannot be both included and excluded: {', '.join(sorted(conflict))}")

    blocked_required = _blocked_required_creators(included, creator_by_id)
    if blocked_required:
        raise PlanningError("Required creator is not eligible for this campaign. " + " ".join(blocked_required))

    included_spend = sum(costs[creator_id] for creator_id in included)
    if included_spend > budget:
        raise PlanningError("Required included creators exceed the budget.")

    selected = list(included)
    steps: list[dict[str, object]] = []
    allowed_ids = eligible_ids(creators) - excluded

    while True:
        base = score_roster(selected, creators, costs)
        candidates = [
            creator
            for creator in creators
            if creator.id in allowed_ids and creator.id not in selected and costs[creator.id] + base.spend <= budget
        ]
        if not candidates:
            break

        scored_candidates = []
        for creator in candidates:
            next_score = score_roster([*selected, creator.id], creators, costs)
            marginal = next_score.proxy_reach - base.proxy_reach
            efficiency = marginal / max(costs[creator.id], 1)
            scored_candidates.append((efficiency, marginal, creator.estimated_views, creator.name, creator, next_score))

        scored_candidates.sort(reverse=True, key=lambda item: item[:4])
        _, marginal, _, _, creator, next_score = scored_candidates[0]
        if marginal <= 0 and costs[creator.id] > 0:
            break
        selected.append(creator.id)
        overlap_note = "based on observed nonredundant commenters" if next_score.overlapping_commenters == base.overlapping_commenters else "overlapping commenters were discounted"
        steps.append(
            {
                "creatorId": creator.id,
                "creatorName": creator.name,
                "marginalProxyReach": round(marginal, 2),
                "cost": costs[creator.id],
                "reason": f"{creator.name} adds {round(marginal):,} overlap-adjusted proxy reach for ${costs[creator.id]:,}; {overlap_note}.",
            }
        )

    recommended = score_roster(selected, creators, costs)
    current_score = score_roster(current, creators, costs)
    baseline = views_ranked_baseline(creators, costs, budget, allowed_ids, included)
    current_flags = [
        f"{creator_by_id[creator_id].name}: {creator_by_id[creator_id].eligibility.reason}"
        for creator_id in current_score.flagged_ids
    ]

    return {
        "campaign": campaign_brief(),
        "datasetLabel": "Deterministic synthetic YouTube roster dataset; fictional creators and commenter ids.",
        "metricLabel": "Overlap-adjusted reach proxy, not validated unique viewers",
        "creatorMetricLabels": {
            "views": "Expected video views",
            "price": "Sponsorship fee (USD)",
            "rawViews": "Total expected views",
        },
        "budget": budget,
        "current": current_score,
        "recommended": ScoredRoster(recommended.ids, recommended.spend, recommended.proxy_reach, recommended.raw_views, recommended.overlapping_commenters, recommended.evidence_note, recommended.flagged_ids, tuple(step["reason"] for step in steps)),
        "viewsBaseline": baseline,
        "rosterDiagnostics": roster_diagnostics(
            {"current": current_score, "recommended": recommended, "viewsBaseline": baseline},
            creators,
            costs,
        ),
        "steps": steps,
        "currentFlags": current_flags,
        "remainingBudget": budget - recommended.spend,
    }


def views_ranked_baseline(creators: list[Creator], costs: dict[str, int], budget: int, allowed_ids: set[str], required_ids: Iterable[str] = ()) -> ScoredRoster:
    selected = list(dict.fromkeys(required_ids))
    spend = sum(costs[creator_id] for creator_id in selected)
    for creator in sorted(creators, key=lambda item: item.estimated_views, reverse=True):
        if creator.id not in allowed_ids or creator.id in selected:
            continue
        cost = costs[creator.id]
        if spend + cost <= budget:
            selected.append(creator.id)
            spend += cost
    return score_roster(selected, creators, costs)
