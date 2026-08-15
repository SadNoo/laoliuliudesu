"""Zodiac mapping and approved transition rule tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from laoliuliu.analysis import calculate_latest_transition
from laoliuliu.db import SessionLocal
from laoliuliu.models import DrawRecord, RawSourceSnapshot
from laoliuliu.zodiac import ZodiacAnimal, zodiac_for_number


def test_horse_anchor_maps_number_17_to_tiger() -> None:
    assert zodiac_for_number(17, ZodiacAnimal.HORSE) is ZodiacAnimal.TIGER


def test_transition_counts_every_regular_occurrence() -> None:
    with SessionLocal() as db:
        snapshot = RawSourceSnapshot(
            source_kind="history",
            source_url="https://example.invalid/history",
            content_sha256="0" * 64,
            payload={"code": 0, "message": "Success", "data": []},
        )
        db.add(snapshot)
        db.flush()
        base_time = datetime(2026, 1, 1, 13, 35, tzinfo=UTC)
        rows = [
            ("2026001", [5, 17, 1, 2, 3, 4], 17),
            ("2026002", [9, 10, 11, 12, 13, 14], 1),
            ("2026003", [29, 41, 5, 17, 6, 7], 5),
            ("2026004", [15, 16, 18, 19, 20, 21], 8),
            ("2026005", [22, 23, 24, 25, 26, 27], 17),
        ]
        for index, (issue, regular, special) in enumerate(rows):
            db.add(
                DrawRecord(
                    issue=issue,
                    open_time=base_time + timedelta(days=index),
                    regular_numbers=regular,
                    special_number=special,
                    zodiac_anchor=ZodiacAnimal.HORSE.value,
                    snapshot_id=snapshot.id,
                    source_kind="history",
                )
            )
        db.commit()

        result = calculate_latest_transition(db)

    assert result.latest_issue == "2026005"
    assert result.latest_special_zodiac is ZodiacAnimal.TIGER
    assert result.sample_count == 2
    assert result.total_regular_occurrences == 12
    assert result.matched_transitions == (
        ("2026001", "2026002"),
        ("2026003", "2026004"),
    )
    assert len(result.ranking) == 12
    assert len(result.to_dict()["top_six"]) == 6
    assert sum(entry.occurrences for entry in result.ranking) == 12
