"""Explicit, bounded data-scope maintenance operations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from laoliuliu.config import APPROVED_DATA_START_ISSUE_ID, APPROVED_DATA_YEAR
from laoliuliu.models import AnalysisRun, DrawRecord, RawSourceSnapshot


@dataclass(frozen=True)
class PruneResult:
    """Counts from one approved pre-start data deletion."""

    deleted_draws: int
    deleted_analysis_runs: int
    pruned_snapshot_records: int
    updated_snapshots: int


def prune_before_approved_start(db: Session) -> PruneResult:
    """Physically remove 2026 issue 001-047 and results derived from them."""

    early_draws = list(
        db.scalars(
            select(DrawRecord).where(
                DrawRecord.issue >= f"{APPROVED_DATA_YEAR}001",
                DrawRecord.issue < APPROVED_DATA_START_ISSUE_ID,
            )
        )
    )
    for draw in early_draws:
        db.delete(draw)

    stale_runs = [
        run
        for run in db.scalars(select(AnalysisRun))
        if run.deterministic_result.get("data_start_issue")
        != APPROVED_DATA_START_ISSUE_ID
    ]
    for run in stale_runs:
        db.delete(run)

    pruned_snapshot_records = 0
    updated_snapshots = 0
    for snapshot in db.scalars(select(RawSourceSnapshot)):
        document, removed = _remove_early_snapshot_records(snapshot.payload)
        if removed == 0:
            continue
        snapshot.payload = document
        snapshot.content_sha256 = _document_sha256(document)
        pruned_snapshot_records += removed
        updated_snapshots += 1

    db.commit()
    return PruneResult(
        deleted_draws=len(early_draws),
        deleted_analysis_runs=len(stale_runs),
        pruned_snapshot_records=pruned_snapshot_records,
        updated_snapshots=updated_snapshots,
    )


def _remove_early_snapshot_records(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    document = dict(payload)
    raw_records = document.get("data")
    if not isinstance(raw_records, list):
        return document, 0

    retained: list[object] = []
    removed = 0
    for raw_record in raw_records:
        if isinstance(raw_record, Mapping):
            issue = raw_record.get("issue")
            if (
                isinstance(issue, str)
                and f"{APPROVED_DATA_YEAR}001" <= issue
                and issue < APPROVED_DATA_START_ISSUE_ID
            ):
                removed += 1
                continue
        retained.append(raw_record)
    if removed:
        document["data"] = retained
    return document, removed


def _document_sha256(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
