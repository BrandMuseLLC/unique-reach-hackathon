from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .campaign_store import CampaignRecord, campaign_to_dict


class SnapshotWriter:
    def write_campaign(self, campaign: CampaignRecord) -> str | None:
        return None


class CloudStorageSnapshotWriter(SnapshotWriter):
    def __init__(self, bucket_name: str) -> None:
        from google.cloud import storage

        self.bucket = storage.Client().bucket(bucket_name)

    def write_campaign(self, campaign: CampaignRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        blob_name = f"campaign-snapshots/{campaign.id}/{timestamp}.json"
        blob = self.bucket.blob(blob_name)
        blob.upload_from_string(
            json.dumps(campaign_to_dict(campaign), indent=2, sort_keys=True),
            content_type="application/json",
        )
        return f"gs://{self.bucket.name}/{blob_name}"


def create_snapshot_writer() -> SnapshotWriter:
    bucket_name = os.getenv("CAMPAIGN_SNAPSHOT_BUCKET")
    if bucket_name:
        return CloudStorageSnapshotWriter(bucket_name)
    return SnapshotWriter()
