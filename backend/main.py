from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import os
from pathlib import Path

from demo.daniel_provider import RealDataProvider
from demo.engine import PlanError
from demo import ai
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from .auth import AuthError, AuthenticatedUser, auth_settings, user_from_request, validate_auth_configuration
from .campaign_store import DATASET_VERSION, CampaignRecord, create_campaign_store
from .optimizer import PlanningError, campaign_brief, greedy_plan, synthetic_creators
from .snapshots import create_snapshot_writer


settings = auth_settings()
real_provider = RealDataProvider.from_env(os.environ) if os.environ.get("MUSE_DATASET") == "observed" else None
CREATOR_METRIC_LABELS = {
    "views": "Expected video views",
    "price": "Sponsorship fee (USD)",
    "rawViews": "Total expected views",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_auth_configuration(app.state.auth_settings)
    yield


app = FastAPI(
    title="Unique Reach Prototype API",
    docs_url="/docs" if settings.mode == "local" else None,
    redoc_url="/redoc" if settings.mode == "local" else None,
    openapi_url="/openapi.json" if settings.mode == "local" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:5174", "http://localhost:5174"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.campaign_store = create_campaign_store()
app.state.snapshot_writer = create_snapshot_writer()
app.state.auth_settings = settings


class PlanningContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    brandDescription: str = Field(default="", max_length=2000)
    relevance: dict[str, float] = Field(default_factory=dict, max_length=30)
    maxPerGroup: dict[str, int] = Field(default_factory=dict, max_length=30)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    budget: int = Field(ge=0, le=5_000_000)
    currentRoster: list[str] = Field(default_factory=list, max_length=50)
    include: list[str] = Field(default_factory=list, max_length=50)
    exclude: list[str] = Field(default_factory=list, max_length=50)
    costs: dict[str, int] = Field(default_factory=dict, max_length=100)
    planningContext: PlanningContext = Field(default_factory=PlanningContext)


class CampaignInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=80)
    budget: int = Field(ge=0, le=5_000_000)
    currentRoster: list[str] = Field(default_factory=list, max_length=50)
    include: list[str] = Field(default_factory=list, max_length=50)
    exclude: list[str] = Field(default_factory=list, max_length=50)
    costs: dict[str, int] = Field(default_factory=dict, max_length=100)
    planningContext: PlanningContext = Field(default_factory=PlanningContext)
    campaignBrief: dict[str, object] | None = None
    datasetVersion: str | None = None
    sharedDemo: bool = True


@app.exception_handler(AuthError)
def auth_error_handler(_: Request, exc: AuthError):
    return JSONResponse(status_code=401, content={"error": str(exc)})


def user_dependency(request: Request) -> AuthenticatedUser:
    user = user_from_request(request)
    return user


def serialize_score(score):
    data = asdict(score)
    data["proxyReach"] = data.pop("proxy_reach")
    data["rawViews"] = data.pop("raw_views")
    data["overlappingCommenters"] = data.pop("overlapping_commenters")
    data["evidenceNote"] = data.pop("evidence_note")
    data["flaggedIds"] = data.pop("flagged_ids")
    return data


def serialize_campaign(brief):
    data = asdict(brief)
    data["eligibleCategories"] = data.pop("eligible_categories")
    return data


def serialize_campaign_record(campaign: CampaignRecord) -> dict[str, object]:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "budget": campaign.budget,
        "currentRoster": campaign.current_roster,
        "include": campaign.include,
        "exclude": campaign.exclude,
        "costs": campaign.costs,
        "campaignBrief": campaign.campaign_brief,
        "datasetVersion": campaign.dataset_version,
        "sharedDemo": campaign.shared_demo,
        "createdAt": campaign.created_at,
        "updatedAt": campaign.updated_at,
        "planningContext": campaign.planning_context,
    }


def active_dataset_version() -> str:
    return real_provider.dataset_version if real_provider is not None else DATASET_VERSION


def active_campaign_brief() -> dict[str, object]:
    return real_provider.campaign if real_provider is not None else serialize_campaign(campaign_brief())


def validate_campaign(request: CampaignInput) -> None:
    if request.datasetVersion not in (None, active_dataset_version()):
        raise PlanningError("Saved campaign dataset does not match the active dataset; reload the matching dataset first.")
    if request.campaignBrief is not None and request.campaignBrief != active_campaign_brief():
        raise PlanningError("Campaign brief does not match the active eligibility scope.")
    if real_provider is not None:
        real_provider.plan_payload(request.model_dump(include={"budget", "currentRoster", "include", "exclude", "costs", "planningContext"}))
    else:
        reject_synthetic_context(request.planningContext)
        greedy_plan(
            creators=synthetic_creators(),
            budget=request.budget,
            current_ids=request.currentRoster,
            include_ids=request.include,
            exclude_ids=request.exclude,
            cost_overrides=request.costs,
        )


def campaign_payload(request: CampaignInput) -> dict[str, object]:
    brief = active_campaign_brief()
    return {
        "name": request.name.strip() or "Untitled demo campaign",
        "budget": request.budget,
        "current_roster": request.currentRoster,
        "include": request.include,
        "exclude": request.exclude,
        "costs": request.costs,
        "campaign_brief": brief,
        "dataset_version": active_dataset_version(),
        "shared_demo": True,
        "planning_context": request.planningContext.model_dump(),
    }


@app.get("/api/auth/session")
def auth_session(user: AuthenticatedUser = Depends(user_dependency)):
    return {"email": user.email, "mode": app.state.auth_settings.mode}


@app.get("/api/creators")
def creators(_: AuthenticatedUser = Depends(user_dependency)):
    if real_provider is not None:
        return real_provider.creators_payload()
    return {
        "campaign": serialize_campaign(campaign_brief()),
        "datasetVersion": DATASET_VERSION,
        "datasetLabel": "Deterministic synthetic YouTube roster dataset; fictional creators and commenter ids.",
        "creatorMetricLabels": CREATOR_METRIC_LABELS,
        "creators": [
            {
                "id": creator.id,
                "name": creator.name,
                "vertical": creator.vertical,
                "audienceNote": creator.features.audience_note,
                "category": creator.features.category,
                "categorySource": creator.features.category_source,
                "eligibilityStatus": creator.eligibility.status,
                "eligibilityReason": creator.eligibility.reason,
                "evidenceState": creator.observations.state,
                "sampleSize": creator.observations.sample_size,
                "source": creator.observations.source,
                "estimatedViews": creator.estimated_views,
                "baseCost": creator.base_cost,
                "commenterCount": len(creator.commenters),
            }
            for creator in synthetic_creators()
        ],
    }


@app.get('/api/overlap')
def explore_overlap(_: AuthenticatedUser = Depends(user_dependency)):
    if real_provider is None:
        return JSONResponse(status_code=404, content={'error':'Observed overlap is unavailable for this dataset.'})
    return real_provider.overlap_payload()


@app.post("/api/plan")
def plan(request: PlanRequest, _: AuthenticatedUser = Depends(user_dependency)):
    try:
        if real_provider is not None:
            return real_provider.plan_payload(request.model_dump())
        reject_synthetic_context(request.planningContext)
        result = greedy_plan(
            creators=synthetic_creators(),
            budget=request.budget,
            current_ids=request.currentRoster,
            include_ids=request.include,
            exclude_ids=request.exclude,
            cost_overrides=request.costs,
        )
        return {
            **result,
            "campaign": serialize_campaign(result["campaign"]),
            "current": serialize_score(result["current"]),
            "recommended": serialize_score(result["recommended"]),
            "viewsBaseline": serialize_score(result["viewsBaseline"]),
        }
    except (PlanningError, PlanError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


def reject_synthetic_context(context: PlanningContext):
    if context.brandDescription or context.relevance or context.maxPerGroup:
        raise PlanningError("AI planning context requires the observed dataset.")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=2000)
    inputs: PlanRequest


def canonical_ai_status():
    configured = ai.status()
    covered = (configured['provider'] in ('gemini', 'gemini_vertex')
               and os.environ.get('MUSE_LLM_COVERAGE_CONFIRMED') == 'true')
    bridge = False
    try:
        expires = datetime.fromisoformat(os.environ.get('MUSE_LLM_BRIDGE_EXPIRES_AT', ''))
        bridge = (configured['provider'] == 'anthropic'
                  and os.environ.get('MUSE_LLM_APP_BRIDGE_AUTHORIZED') == 'true'
                  and expires.tzinfo is not None and datetime.now(timezone.utc) < expires)
    except ValueError:
        pass
    enabled = real_provider is not None and configured['configured'] and (covered or bridge)
    return {'enabled': enabled, 'provider': configured['provider'] if enabled else None,
            'model': configured['model'] if enabled else None,
            'billingSource': ('existing_app_bridge' if bridge else 'sponsored_google') if enabled else None,
            'message': ('Temporary existing-app inference bridge is ready.' if bridge else 'Sponsored Google inference is ready.') if enabled
            else 'Live AI is unavailable until an authorized endpoint is configured. Manual planning remains available.'}


@app.get('/api/ai/status')
def ai_status(_: AuthenticatedUser = Depends(user_dependency)):
    return canonical_ai_status()


@app.post('/api/chat')
def chat(request: ChatRequest, _: AuthenticatedUser = Depends(user_dependency)):
    if not canonical_ai_status()['enabled']:
        return JSONResponse(status_code=503, content={'error': canonical_ai_status()['message']})
    try:
        inputs=request.inputs.model_dump()
        real_provider.plan_payload(inputs)  # Reject invalid/infeasible state before any model call.
        context=request.inputs.planningContext
        constraints={'budget':request.inputs.budget,'must_include':request.inputs.include,
                     'exclude':sorted(set(request.inputs.exclude) | (set(real_provider.planner.by_id)-real_provider.eligible)),
                     'costs':request.inputs.costs,'objective':'viewer_proxy',
                     'brand_description':context.brandDescription,'relevance':context.relevance,'max_per_group':context.maxPerGroup}
        response=ai.live_chat(real_provider.planner, {'message':request.message,'constraints':constraints})
        if response['plan'] is None:
            return {'reply':response['reply'],'inputs':None,'plan':None,'mode':'live_model'}
        proposed=response['plan']['constraints']
        budget=proposed['budget']
        if budget != int(budget):
            raise PlanError('Use whole-dollar budgets.')
        updated={**inputs,'budget':int(budget),'include':proposed['must_include'],
                 'exclude':sorted(set(proposed['exclude']) & (real_provider.eligible | set(request.inputs.exclude))),
                 'planningContext':{'brandDescription':proposed['brand_description'],'relevance':proposed['relevance'],
                                    'maxPerGroup':proposed['max_per_group']}}
        # Host limits, fixed eligibility and costs remain authoritative after inference.
        updated=PlanRequest.model_validate(updated).model_dump()
        result=real_provider.plan_payload(updated)
        return {'reply':response['reply'],'inputs':updated,'plan':result,'mode':'live_model',
                'provider':response['provider'],'model':response['model'],
                'relevanceReasons':response['plan']['ai_assessment']['relevance_reasons']}
    except (PlanningError, PlanError, ValueError):
        return JSONResponse(status_code=400, content={'error':'The model could not produce a valid plan. Your inputs are unchanged; check the request, access or quota.'})


@app.get("/api/campaigns")
def list_campaigns(user: AuthenticatedUser = Depends(user_dependency)):
    return {
        "campaigns": [
            serialize_campaign_record(campaign)
            for campaign in app.state.campaign_store.list_campaigns(user.email)
            if campaign.dataset_version == active_dataset_version()
        ]
    }


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, user: AuthenticatedUser = Depends(user_dependency)):
    campaign = app.state.campaign_store.get_campaign(campaign_id, user.email)
    if not campaign or campaign.dataset_version != active_dataset_version():
        return JSONResponse(status_code=404, content={"error": "Campaign not found."})
    return serialize_campaign_record(campaign)


@app.post("/api/campaigns")
def create_campaign(request: CampaignInput, user: AuthenticatedUser = Depends(user_dependency)):
    try:
        validate_campaign(request)
        campaign = app.state.campaign_store.save_campaign(campaign_payload(request), user.email)
        snapshot_uri = app.state.snapshot_writer.write_campaign(campaign)
        return {"campaign": serialize_campaign_record(campaign), "snapshotUri": snapshot_uri}
    except (PlanningError, PlanError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.put("/api/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, request: CampaignInput, user: AuthenticatedUser = Depends(user_dependency)):
    try:
        existing = app.state.campaign_store.get_campaign(campaign_id, user.email)
        if not existing or existing.dataset_version != active_dataset_version():
            return JSONResponse(status_code=404, content={"error": "Campaign not found."})
        validate_campaign(request)
        campaign = app.state.campaign_store.save_campaign(campaign_payload(request), user.email, campaign_id=campaign_id)
        snapshot_uri = app.state.snapshot_writer.write_campaign(campaign)
        return {"campaign": serialize_campaign_record(campaign), "snapshotUri": snapshot_uri}
    except (PlanningError, PlanError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.delete("/api/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, user: AuthenticatedUser = Depends(user_dependency)):
    existing = app.state.campaign_store.get_campaign(campaign_id, user.email)
    if not existing or existing.dataset_version != active_dataset_version():
        return JSONResponse(status_code=404, content={"error": "Campaign not found for the active dataset."})
    deleted = app.state.campaign_store.delete_campaign(campaign_id, user.email)
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Campaign not found."})
    return {"deleted": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


dist_dir = Path(__file__).resolve().parents[1] / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
