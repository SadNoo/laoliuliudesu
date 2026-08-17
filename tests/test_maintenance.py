"""Approved physical cleanup of records before issue 048."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, text

from laoliuliu.db import SessionLocal
from laoliuliu.maintenance import prune_before_approved_start
from laoliuliu.models import AnalysisRun, DrawRecord, RawSourceSnapshot, User
from laoliuliu.security import hash_password
from laoliuliu.zodiac import ZodiacAnimal


def test_prune_physically_removes_early_draws_snapshots_and_derived_runs() -> None:
    with SessionLocal() as db:
        snapshot = RawSourceSnapshot(
            source_kind="history",
            source_url="https://example.invalid/history",
            content_sha256="0" * 64,
            payload={
                "code": 0,
                "message": "Success",
                "data": [
                    {"issue": "2026047", "openCode": "early"},
                    {"issue": "2026048", "openCode": "kept"},
                ],
            },
        )
        user = User(
            username="maintenance_admin",
            password_hash=hash_password("Maintenance-admin-12345"),
            role="admin",
            status="active",
            must_change_password=False,
        )
        db.add_all([snapshot, user])
        db.flush()
        db.execute(text("PRAGMA ignore_check_constraints = ON"))
        for issue, day in (("2026047", 16), ("2026048", 17)):
            db.add(
                DrawRecord(
                    issue=issue,
                    open_time=datetime(2026, 2, day, 13, 35, tzinfo=UTC),
                    regular_numbers=[1, 2, 3, 4, 5, 6],
                    special_number=7,
                    zodiac_anchor=ZodiacAnimal.HORSE.value,
                    snapshot_id=snapshot.id,
                    source_kind="history",
                )
            )
        db.add_all(
            [
                AnalysisRun(
                    user_id=user.id,
                    latest_issue="2026227",
                    special_zodiac=ZodiacAnimal.TIGER.value,
                    prompt_version="old",
                    deterministic_result={
                        "algorithm_version": "zodiac-transition-2026-v2"
                    },
                    status="succeeded",
                ),
                AnalysisRun(
                    user_id=user.id,
                    latest_issue="2026227",
                    special_zodiac=ZodiacAnimal.TIGER.value,
                    prompt_version="current",
                    deterministic_result={
                        "algorithm_version": "zodiac-transition-2026-v3",
                        "data_start_issue": "2026048",
                    },
                    status="succeeded",
                ),
            ]
        )
        db.commit()
        db.execute(text("PRAGMA ignore_check_constraints = OFF"))

        result = prune_before_approved_start(db)

        assert result.deleted_draws == 1
        assert result.deleted_analysis_runs == 1
        assert result.pruned_snapshot_records == 1
        assert result.updated_snapshots == 1
        assert list(db.scalars(select(DrawRecord.issue))) == ["2026048"]
        runs = list(db.scalars(select(AnalysisRun)))
        assert len(runs) == 1
        assert runs[0].prompt_version == "current"
        db.refresh(snapshot)
        assert snapshot.payload["data"] == [{"issue": "2026048", "openCode": "kept"}]
