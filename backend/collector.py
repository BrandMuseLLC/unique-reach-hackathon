from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Literal


CollectionState = Literal[
    "not_collected",
    "observed",
    "observed_zero",
    "unavailable_api",
    "quota_limited",
    "permission_limited",
    "parse_failed",
]


@dataclass(frozen=True)
class CollectionCursor:
    dataset_version: str
    channel_ids: tuple[str, ...]
    next_index: int = 0
    consumed_quota_units: int = 0
    max_quota_units: int = 5_000


@dataclass(frozen=True)
class CollectionBatch:
    channel_ids: tuple[str, ...]
    next_index: int
    consumed_quota_units: int
    state: CollectionState
    note: str


def next_quota_bounded_batch(cursor: CollectionCursor, batch_size: int, cost_per_channel: int = 1) -> CollectionBatch:
    if batch_size <= 0:
        return CollectionBatch((), cursor.next_index, cursor.consumed_quota_units, "not_collected", "Batch size must be positive.")
    if cursor.consumed_quota_units >= cursor.max_quota_units:
        return CollectionBatch((), cursor.next_index, cursor.consumed_quota_units, "quota_limited", "Quota budget exhausted for this project.")

    remaining_quota = cursor.max_quota_units - cursor.consumed_quota_units
    quota_limited_size = min(batch_size, remaining_quota // max(cost_per_channel, 1))
    channel_ids = cursor.channel_ids[cursor.next_index : cursor.next_index + quota_limited_size]
    consumed = cursor.consumed_quota_units + len(channel_ids) * cost_per_channel
    next_index = cursor.next_index + len(channel_ids)
    state: CollectionState = "observed" if channel_ids else "not_collected"
    note = "Prepared resumable collection batch; no live API request is made by this prototype helper."
    return CollectionBatch(channel_ids, next_index, consumed, state, note)


def main() -> None:
    max_units = int(os.getenv("MAX_DAILY_QUOTA_UNITS", "5000"))
    dry_run = os.getenv("COLLECTOR_DRY_RUN", "true").lower() != "false"
    cursor = CollectionCursor(
        dataset_version=os.getenv("DATASET_VERSION", "synthetic-youtube-beauty-v2"),
        channel_ids=tuple(filter(None, os.getenv("COLLECTOR_CHANNEL_IDS", "").split(","))),
        max_quota_units=max_units,
    )
    batch = next_quota_bounded_batch(cursor, batch_size=int(os.getenv("COLLECTOR_BATCH_SIZE", "25")))
    print(json.dumps({**batch.__dict__, "dryRun": dry_run}, sort_keys=True))


if __name__ == "__main__":
    main()
