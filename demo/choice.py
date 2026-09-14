"""Plain-language explanation of why the recommended roster was chosen over the user's roster.

The planner's rule is: lowest overlap among rosters that reach at least as many people as yours. When the recommendation
has MORE overlap than your roster, something forced a trade-off, and the page must say what and what was gained.
"""


def _fmt(n):
    n = float(n)
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 1_000:
        return "%.0fK" % (n / 1_000)
    return "%d" % round(n)


def explain(mine, rec, *, unit, current_ids, feasible_reason, creator_count, evidence_mix=None):
    """mine/rec: roster diagnostics dicts (ids, spend, coverage, sharedRate). feasible_reason: None if your roster fits."""
    reasons = []
    n_mine, n_rec = len(mine["ids"]), len(rec["ids"])
    reach_mine, reach_rec = mine["coverage"], rec["coverage"]
    rate_mine, rate_rec = mine["sharedRate"], rec["sharedRate"]
    if not current_ids:
        kind = "no_roster"
        headline = "Tick creators in the list to compare your own roster with the recommendation."
    elif set(current_ids) == set(rec["ids"]):
        kind = "same"
        headline = "Your roster is already the best option we found at this budget."
    elif rate_rec > rate_mine + 0.0005:
        kind = "tradeoff"
        more = ("%.1f× more" % (reach_rec / reach_mine)) if reach_mine else "more"
        headline = "Chose more reach over lower overlap: reaches %s %s (%s vs %s) at %.1f%% overlap vs your %.1f%%." % (
            more, unit, _fmt(reach_rec), _fmt(reach_mine), rate_rec * 100, rate_mine * 100)
        if feasible_reason:
            reasons.append("Your roster doesn't fit the current settings (%s), so it couldn't be kept." % feasible_reason)
        if creator_count and n_mine != creator_count:
            reasons.append("You asked for %d creators; your roster has %d. More creators means more chances to overlap." % (creator_count, n_mine))
        if n_mine == 1:
            reasons.append("A single creator always shows 0% overlap, so any multi-creator roster will look higher.")
        if not reasons:
            reasons.append("No roster with less overlap reached as many %s as yours within the budget." % unit)
    elif reach_rec + 1e-6 < reach_mine:
        kind = "tradeoff_reach"
        headline = "Chose lower overlap over reach: %.1f%% overlap vs your %.1f%%, reaching %s %s vs your %s." % (
            rate_rec * 100, rate_mine * 100, _fmt(reach_rec), unit, _fmt(reach_mine))
        if feasible_reason:
            reasons.append("Your roster doesn't fit the current settings (%s)." % feasible_reason)
        if creator_count and n_rec < n_mine:
            reasons.append("You asked for %d creators, fewer than your roster's %d, so it reaches fewer people." % (creator_count, n_mine))
    elif abs(rate_rec - rate_mine) <= 0.0005:
        kind = "better"
        headline = ("Same overlap (%.1f%%), more reach: %s %s vs your %s." % (rate_rec * 100, _fmt(reach_rec), unit, _fmt(reach_mine))
                    if reach_rec > reach_mine + 1e-6 else "Same overlap and reach as your roster (%.1f%%, %s %s)." % (rate_rec * 100, _fmt(reach_rec), unit))
    else:
        kind = "better"
        headline = "Less overlap without losing reach: %.1f%% vs your %.1f%%, reaching %s %s vs %s." % (
            rate_rec * 100, rate_mine * 100, _fmt(reach_rec), unit, _fmt(reach_mine))
    if rec["spend"] > mine["spend"] and kind in ("tradeoff", "better", "tradeoff_reach") and current_ids:
        reasons.append("Uses $%s more of the budget than your roster ($%s vs $%s)." % (
            format(round(rec["spend"] - mine["spend"]), ","), format(round(rec["spend"]), ","), format(round(mine["spend"]), ",")))
    confidence = "measured" if not evidence_mix else "none"
    if evidence_mix and evidence_mix.get("pairs"):
        if evidence_mix.get("assumed") == evidence_mix["pairs"]:
            confidence = "assumed"
            reasons.append("Overlap here is assumed, not measured: Upriver had no audience data for these creators, so treat the overlap % as a placeholder.")
        elif evidence_mix.get("measured", 0) < evidence_mix["pairs"]:
            confidence = "estimated"
        else:
            confidence = "measured"
    return {"kind": kind, "headline": headline, "reasons": reasons, "overlapConfidence": confidence}


def infeasible_reason(ids, ctx, by_id, community_key="community"):
    """Why a roster can't be used under ctx, in a few words; None if it fits."""
    if not ids:
        return None
    if any(i in ctx["exclude"] for i in ids):
        return "it includes an excluded or unplannable creator"
    if not set(ctx["must_include"]) <= set(ids):
        return "it's missing a required creator"
    if sum(ctx["costs"][i] for i in ids) > ctx["budget"] + 1e-8:
        return "it costs more than the budget"
    if ctx.get("creator_count") and len(ids) > ctx["creator_count"]:
        return "it has more creators than you asked for"
    for group, cap in (ctx.get("max_per_group") or {}).items():
        if sum(by_id[i][community_key] == group for i in ids) > cap:
            return "it breaks the %s cap" % group
    return None
