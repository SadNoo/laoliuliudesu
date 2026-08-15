"""Transactional history and incremental draw synchronization."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from laoliuliu.config import Settings
from laoliuliu.errors import SourceError
from laoliuliu.models import (
    DrawRecord,
    RawSourceSnapshot,
    SourceSyncRun,
    utc_now,
)
from laoliuliu.source import SourceBatch, SourceClient, SourceDraw
from laoliuliu.zodiac import ZodiacAnimal


@dataclass(frozen=True)
class SyncResult:
    """Safe synchronization summary."""

    run_id: str
    kind: str
    fetched: int
    inserted: int
    skipped: int


def synchronize_history(
    db: Session, client: SourceClient, settings: Settings, *, as_of: date | None = None
) -> SyncResult:
    """Import the approved full-year history response idempotently."""

    local_date = as_of or datetime.now(settings.zone).date()
    return _synchronize(db, client.fetch_history(local_date), settings)


def synchronize_current(
    db: Session, client: SourceClient, settings: Settings
) -> SyncResult:
    """Import the current five rows and carry forward the last confirmed anchor."""

    return _synchronize(db, client.fetch_current(), settings)


def _synchronize(db: Session, batch: SourceBatch, settings: Settings) -> SyncResult:
    run = SourceSyncRun(sync_kind=batch.source_kind, status="running")
    db.add(run)
    db.commit()
    try:
        snapshot = _create_snapshot(batch)
        db.add(snapshot)
        db.flush()

        latest_anchor = db.scalar(
            select(DrawRecord.zodiac_anchor)
            .order_by(DrawRecord.open_time.desc(), DrawRecord.issue.desc())
            .limit(1)
        )
        inserted = 0
        skipped = 0
        for source_draw in batch.records:
            anchor = source_draw.zodiac_anchor
            if anchor is None:
                if latest_anchor is None:
                    raise SourceError(
                        "ZODIAC_ANCHOR_UNAVAILABLE",
                        "增量数据缺少可继承的生肖锚点，请先导入历史数据",
                        409,
                    )
                anchor = ZodiacAnimal(latest_anchor)
            existing = db.get(DrawRecord, source_draw.issue)
            if existing is not None:
                _assert_same_draw(existing, source_draw, anchor)
                skipped += 1
                continue
            db.add(
                DrawRecord(
                    issue=source_draw.issue,
                    open_time=source_draw.open_time.astimezone(UTC),
                    regular_numbers=list(source_draw.regular_numbers),
                    special_number=source_draw.special_number,
                    zodiac_anchor=anchor.value,
                    snapshot_id=snapshot.id,
                    source_kind=batch.source_kind,
                )
            )
            latest_anchor = anchor.value
            inserted += 1

        run.status = "succeeded"
        run.fetched_count = len(batch.records)
        run.inserted_count = inserted
        run.skipped_count = skipped
        run.finished_at = utc_now()
        db.commit()
        return SyncResult(
            run_id=run.id,
            kind=batch.source_kind,
            fetched=len(batch.records),
            inserted=inserted,
            skipped=skipped,
        )
    except Exception as error:
        db.rollback()
        persisted_run = db.get(SourceSyncRun, run.id)
        if persisted_run is not None:
            persisted_run.status = "failed"
            persisted_run.error_code = (
                error.code if isinstance(error, SourceError) else "SYNC_FAILED"
            )
            persisted_run.finished_at = utc_now()
            db.commit()
        raise


def _create_snapshot(batch: SourceBatch) -> RawSourceSnapshot:
    encoded = json.dumps(
        batch.document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return RawSourceSnapshot(
        source_kind=batch.source_kind,
        source_url=batch.source_url,
        content_sha256=hashlib.sha256(encoded).hexdigest(),
        payload=batch.document,
    )


def _assert_same_draw(
    existing: DrawRecord, source: SourceDraw, anchor: ZodiacAnimal
) -> None:
    existing_time = existing.open_time
    if existing_time.tzinfo is None:
        existing_time = existing_time.replace(tzinfo=UTC)
    expected_time = source.open_time.astimezone(UTC)
    if (
        tuple(existing.regular_numbers) != source.regular_numbers
        or existing.special_number != source.special_number
        or existing.zodiac_anchor != anchor.value
        or existing_time.astimezone(UTC) != expected_time
    ):
        raise SourceError(
            "DRAW_CONFLICT",
            f"期号 {source.issue} 与数据库现有记录冲突",
            409,
        )
