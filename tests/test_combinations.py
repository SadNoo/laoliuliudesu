"""Approved top-ten number comparison and 3-of-3 combination tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from laoliuliu.analysis import (
    RankedNumber,
    RankedZodiac,
    TransitionAnalysis,
)
from laoliuliu.combinations import (
    build_number_combinations,
    calculate_latest_number_combinations,
)
from laoliuliu.db import SessionLocal
from laoliuliu.errors import AnalysisError
from laoliuliu.main import app
from laoliuliu.models import DrawRecord, RawSourceSnapshot
from laoliuliu.zodiac import ZodiacAnimal


def _transition_with_twelve_numbers() -> TransitionAnalysis:
    ranking: list[RankedZodiac] = []
    for index, animal in enumerate(ZodiacAnimal, start=1):
        first_number = (index - 1) * 2 + 1
        number_occurrences = (
            (
                RankedNumber(first_number, 13 - first_number),
                RankedNumber(first_number + 1, 12 - first_number),
            )
            if index <= 6
            else ()
        )
        occurrences = sum(item.occurrences for item in number_occurrences)
        ranking.append(
            RankedZodiac(
                rank=index,
                zodiac=animal,
                occurrences=occurrences,
                frequency=round(occurrences / 78, 6),
                number_occurrences=number_occurrences,
            )
        )
    return TransitionAnalysis(
        latest_issue="2026100",
        latest_regular_numbers=(1, 2, 3, 4, 5, 6),
        latest_special_number=17,
        latest_special_zodiac=ZodiacAnimal.TIGER,
        sample_count=13,
        total_regular_occurrences=78,
        matched_transitions=(("2026098", "2026099"),),
        ranking=tuple(ranking),
    )


def test_top_ten_candidates_produce_ten_ranked_three_number_groups() -> None:
    transition = _transition_with_twelve_numbers()
    recent_issues = tuple(f"2026{issue:03d}" for issue in range(80, 100))
    recent_numbers = tuple(
        (1, 2, 3, 4, 5, 6) if index % 2 == 0 else (7, 8, 9, 10, 11, 12)
        for index in range(20)
    )

    result = build_number_combinations(
        transition,
        recent_issues=recent_issues,
        recent_regular_numbers=recent_numbers,
    )
    payload = result.to_dict()

    assert [candidate.number for candidate in result.candidates] == list(range(1, 11))
    assert all(candidate.recent_occurrences == 10 for candidate in result.candidates)
    assert len(result.combinations) == 10
    assert result.combinations[0].numbers == (1, 2, 3)
    assert result.combinations[0].historical_occurrences == 33
    assert result.combinations[0].recent_occurrences == 30
    assert result.combinations[0].combined_score == 63
    assert all(len(set(item.numbers)) == 3 for item in result.combinations)
    assert payload["recent_issue_start"] == "2026080"
    assert payload["recent_issue_end"] == "2026099"
    assert payload["candidate_count"] == 10
    assert payload["combination_count"] == 10


def test_combinations_require_twenty_draws_and_ten_comparable_numbers() -> None:
    with SessionLocal() as db, pytest.raises(AnalysisError) as captured:
        calculate_latest_number_combinations(db)
    assert captured.value.code == "INSUFFICIENT_RECENT_HISTORY"

    transition = _transition_with_twelve_numbers()
    with pytest.raises(AnalysisError) as captured:
        build_number_combinations(
            transition,
            recent_issues=tuple(f"2026{issue:03d}" for issue in range(80, 100)),
            recent_regular_numbers=tuple((1, 2, 3, 4, 5, 6) for _ in range(20)),
        )
    assert captured.value.code == "INSUFFICIENT_COMBINATION_CANDIDATES"


def test_latest_combination_uses_exactly_twenty_draws_before_latest() -> None:
    with SessionLocal() as db:
        snapshot = RawSourceSnapshot(
            source_kind="history",
            source_url="https://example.invalid/history",
            content_sha256="1" * 64,
            payload={"code": 0, "message": "Success", "data": []},
        )
        db.add(snapshot)
        db.flush()
        base_time = datetime(2026, 2, 17, 13, 35, tzinfo=UTC)
        for index in range(30):
            special = 17 if index % 3 == 0 or index == 29 else 48
            pool = [number for number in range(1, 50) if number != special]
            start = (index * 7) % len(pool)
            regular = [pool[(start + offset) % len(pool)] for offset in range(6)]
            db.add(
                DrawRecord(
                    issue=f"2026{48 + index:03d}",
                    open_time=base_time + timedelta(days=index),
                    regular_numbers=regular,
                    special_number=special,
                    zodiac_anchor=ZodiacAnimal.HORSE.value,
                    snapshot_id=snapshot.id,
                    source_kind="history",
                )
            )
        db.commit()

        result = calculate_latest_number_combinations(db)

    assert result.latest_issue == "2026077"
    assert result.recent_issue_start == "2026057"
    assert result.recent_issue_end == "2026076"
    assert len(result.candidates) == 10
    assert len(result.combinations) == 10


def test_combination_endpoint_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/analysis/combinations/latest")
    assert response.status_code == 401
