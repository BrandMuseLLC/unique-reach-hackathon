from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


DATASET_VERSION = "synthetic-youtube-beauty-v2"


@dataclass(frozen=True)
class CampaignRecord:
    id: str
    owner_email: str
    name: str
    budget: int
    current_roster: list[str]
    include: list[str]
    exclude: list[str]
    costs: dict[str, int]
    campaign_brief: dict[str, object]
    dataset_version: str
    shared_demo: bool
    created_at: str
    updated_at: str
    planning_context: dict[str, object] = field(default_factory=dict)


class CampaignStore(Protocol):
    def list_campaigns(self, owner_email: str) -> list[CampaignRecord]:
        ...

    def get_campaign(self, campaign_id: str, owner_email: str) -> CampaignRecord | None:
        ...

    def save_campaign(self, payload: dict[str, object], owner_email: str, campaign_id: str | None = None) -> CampaignRecord:
        ...

    def delete_campaign(self, campaign_id: str, owner_email: str) -> bool:
        ...


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def campaign_to_dict(campaign: CampaignRecord) -> dict[str, object]:
    return asdict(campaign)


def campaign_from_dict(data: dict[str, object]) -> CampaignRecord:
    return CampaignRecord(
        id=str(data["id"]),
        owner_email=str(data.get("owner_email", "local-dev@example.test")).lower(),
        name=str(data["name"]),
        budget=int(data["budget"]),
        current_roster=list(data.get("current_roster", [])),
        include=list(data.get("include", [])),
        exclude=list(data.get("exclude", [])),
        costs={str(key): int(value) for key, value in dict(data.get("costs", {})).items()},
        campaign_brief=dict(data.get("campaign_brief", {})),
        dataset_version=str(data.get("dataset_version", DATASET_VERSION)),
        shared_demo=bool(data.get("shared_demo", True)),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        planning_context=dict(data.get("planning_context", {})),
    )


class LocalJsonCampaignStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def _write(self, records: dict[str, dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(records, indent=2, sort_keys=True))
        tmp_path.replace(self.path)

    def list_campaigns(self, owner_email: str) -> list[CampaignRecord]:
        records = [
            campaign
            for campaign in (campaign_from_dict(data) for data in self._read().values())
            if campaign.owner_email == owner_email.lower()
        ]
        return sorted(records, key=lambda campaign: campaign.updated_at, reverse=True)

    def get_campaign(self, campaign_id: str, owner_email: str) -> CampaignRecord | None:
        data = self._read().get(campaign_id)
        campaign = campaign_from_dict(data) if data else None
        return campaign if campaign and campaign.owner_email == owner_email.lower() else None

    def save_campaign(self, payload: dict[str, object], owner_email: str, campaign_id: str | None = None) -> CampaignRecord:
        records = self._read()
        now = utc_now()
        existing = records.get(campaign_id or "")
        if existing and campaign_from_dict(existing).owner_email != owner_email.lower():
            raise PermissionError("Campaign belongs to a different invited user.")
        record_id = campaign_id or str(uuid.uuid4())
        record = CampaignRecord(
            id=record_id,
            owner_email=owner_email.lower(),
            name=str(payload["name"]),
            budget=int(payload["budget"]),
            current_roster=list(payload["current_roster"]),
            include=list(payload["include"]),
            exclude=list(payload["exclude"]),
            costs={str(key): int(value) for key, value in dict(payload["costs"]).items()},
            campaign_brief=dict(payload["campaign_brief"]),
            dataset_version=str(payload.get("dataset_version", DATASET_VERSION)),
            shared_demo=bool(payload.get("shared_demo", True)),
            created_at=str(existing["created_at"]) if existing else now,
            updated_at=now,
            planning_context=dict(payload.get("planning_context", {})),
        )
        records[record.id] = campaign_to_dict(record)
        self._write(records)
        return record

    def delete_campaign(self, campaign_id: str, owner_email: str) -> bool:
        records = self._read()
        existing = records.get(campaign_id)
        existed = existing is not None and campaign_from_dict(existing).owner_email == owner_email.lower()
        if existed:
            records.pop(campaign_id)
            self._write(records)
        return existed


class FirestoreCampaignStore:
    def __init__(self, project: str, collection: str, database: str = "(default)") -> None:
        from google.cloud import firestore

        self.client = firestore.Client(project=project, database=database)
        self.collection = self.client.collection(collection)

    def list_campaigns(self, owner_email: str) -> list[CampaignRecord]:
        docs = self.collection.where("owner_email", "==", owner_email.lower()).stream()
        records = [campaign_from_dict(doc.to_dict()) for doc in docs]
        return sorted(records, key=lambda campaign: campaign.updated_at, reverse=True)

    def get_campaign(self, campaign_id: str, owner_email: str) -> CampaignRecord | None:
        doc = self.collection.document(campaign_id).get()
        campaign = campaign_from_dict(doc.to_dict()) if doc.exists else None
        return campaign if campaign and campaign.owner_email == owner_email.lower() else None

    def save_campaign(self, payload: dict[str, object], owner_email: str, campaign_id: str | None = None) -> CampaignRecord:
        now = utc_now()
        record_id = campaign_id or str(uuid.uuid4())
        existing = self.get_campaign(record_id, owner_email)
        if campaign_id and existing is None:
            existing_doc = self.collection.document(record_id).get()
            if existing_doc.exists:
                raise PermissionError("Campaign belongs to a different invited user.")
        record = CampaignRecord(
            id=record_id,
            owner_email=owner_email.lower(),
            name=str(payload["name"]),
            budget=int(payload["budget"]),
            current_roster=list(payload["current_roster"]),
            include=list(payload["include"]),
            exclude=list(payload["exclude"]),
            costs={str(key): int(value) for key, value in dict(payload["costs"]).items()},
            campaign_brief=dict(payload["campaign_brief"]),
            dataset_version=str(payload.get("dataset_version", DATASET_VERSION)),
            shared_demo=bool(payload.get("shared_demo", True)),
            created_at=existing.created_at if existing else now,
            updated_at=now,
            planning_context=dict(payload.get("planning_context", {})),
        )
        self.collection.document(record.id).set(campaign_to_dict(record))
        return record

    def delete_campaign(self, campaign_id: str, owner_email: str) -> bool:
        existed = self.get_campaign(campaign_id, owner_email) is not None
        if existed:
            self.collection.document(campaign_id).delete()
        return existed


def create_campaign_store() -> CampaignStore:
    store_kind = os.getenv("CAMPAIGN_STORE", "local").lower()
    if store_kind == "firestore":
        project = os.environ["GCP_PROJECT"]
        collection = os.getenv("FIRESTORE_CAMPAIGN_COLLECTION", "campaigns")
        database = os.getenv("FIRESTORE_DATABASE", "(default)")
        return FirestoreCampaignStore(project=project, collection=collection, database=database)
    path = Path(os.getenv("LOCAL_CAMPAIGN_DB", "data/campaigns.json"))
    return LocalJsonCampaignStore(path)
