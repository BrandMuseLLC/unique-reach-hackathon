"""Make one real model call per AI feature and report pass/fail. Never prints credentials.

    MUSE_LLM_PROVIDER=gemini MUSE_LLM_MODEL=<model> GEMINI_API_KEY=... \
      python3 scripts/verify_live_ai.py --aggregate data/home-coffee-aggregate.json

Uses at most three calls. Exit code 0 only when every feature returned a validated result.
"""
import argparse
import json
import sys
import os
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo import ai, ai_explain, ai_labels  # noqa: E402
from demo.daniel_provider import RealDataProvider  # noqa: E402
from demo.engine import PlanError  # noqa: E402


def app_gate(provider):
    """Mirror backend.main.canonical_ai_status's billing gate, which the app enforces on top of credentials."""
    if provider in ("gemini", "gemini_vertex"):
        return os.environ.get("MUSE_LLM_COVERAGE_CONFIRMED") == "true", "set MUSE_LLM_COVERAGE_CONFIRMED=true once sponsor coverage is confirmed"
    if provider == "anthropic":
        try:
            expires = datetime.fromisoformat(os.environ.get("MUSE_LLM_BRIDGE_EXPIRES_AT", ""))
            ok = os.environ.get("MUSE_LLM_APP_BRIDGE_AUTHORIZED") == "true" and expires.tzinfo is not None and datetime.now(timezone.utc) < expires
        except ValueError:
            ok = False
        return ok, "the app needs MUSE_LLM_APP_BRIDGE_AUTHORIZED=true and a future timezone-aware MUSE_LLM_BRIDGE_EXPIRES_AT"
    return False, "unsupported provider"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate", help="Observed aggregate (default: bundled sample)")
    parser.add_argument("--brief", default="Launching a sub-$500 home espresso machine. Weight topics by relevance to home espresso buyers.")
    args = parser.parse_args()
    status = ai.status()
    print("provider=%s model=%s configured=%s" % (status["provider"], status["model"], status["configured"]))
    if not status["configured"]:
        print("Set MUSE_LLM_PROVIDER, MUSE_LLM_MODEL and the matching API key in this shell.")
        return 2
    data = json.loads(Path(args.aggregate).read_text()) if args.aggregate else None
    provider = RealDataProvider(data) if data else RealDataProvider.bundled()
    inputs = {"budget": 10000, "currentRoster": provider.creators_payload()["defaultCurrentRoster"]}
    results = {}

    def run(name, fn):
        started = time.monotonic()
        try:
            detail = fn()
            results[name] = True
            print("PASS %-8s %.1fs  %s" % (name, time.monotonic() - started, detail))
        except PlanError as exc:
            results[name] = False
            print("FAIL %-8s %.1fs  %s" % (name, time.monotonic() - started, exc))
        time.sleep(2.1)  # the adapters enforce two seconds between calls

    def brief():
        constraints = {"budget": 10000, "exclude": sorted(set(provider.planner.by_id) - provider.eligible)}
        response = ai.live_chat(provider.planner, {"message": args.brief, "constraints": constraints})
        if response["plan"] is None:
            return "clarification: " + response["reply"]
        return "%d creators, relevance on %d topics" % (len(response["plan"]["selected"]), len(response["plan"]["constraints"]["relevance"]))

    def labels():
        named = ai_labels.label_clusters(provider.overlap_payload()["clusters"], provider.planner.by_id)
        model = [c["label"] for c in named if c["labelSource"] == "model"]
        if not model:
            raise PlanError("no multi-creator clusters to name")
        return "; ".join(model[:3])

    def explain():
        plan = provider.plan_payload(inputs)
        target = plan["whyNot"][0]["creatorName"] if plan["whyNot"] else "the top pick"
        return ai_explain.explain(plan, "Why is %s not in the plan?" % target)["answer"][:160]

    run("brief", brief)
    run("labels", labels)
    run("explain", explain)
    enabled, hint = app_gate(status["provider"])
    print("app gate: %s%s" % ("enabled" if enabled else "DISABLED", "" if enabled else " (%s; also run with MUSE_DATASET=observed)" % hint))
    if not all(results.values()):
        return 1
    return 0 if enabled else 3


if __name__ == "__main__":
    raise SystemExit(main())
