"""Zodiac mapping and approved transition rule tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from laoliuliu.analysis import (
    calculate_latest_transition,
    calculate_transition_for_issue,
    list_historical_analysis_issues,
)
from laoliuliu.db import SessionLocal
from laoliuliu.errors import AnalysisError
from laoliuliu.main import app
from laoliuliu.models import DrawRecord, RawSourceSnapshot, User
from laoliuliu.security import hash_password
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
            ("2026004", [9, 16, 18, 19, 20, 21], 8),
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
        historical = calculate_transition_for_issue(db, "2026003")
        issues = list_historical_analysis_issues(db)

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
    dog = next(entry for entry in result.ranking if entry.zodiac is ZodiacAnimal.DOG)
    assert dog.occurrences == 3
    assert [(item.number, item.occurrences) for item in dog.number_occurrences] == [
        (9, 2),
        (21, 1),
    ]
    dog_payload = next(
        entry for entry in result.to_dict()["ranking"] if entry["zodiac"] == "dog"
    )
    assert dog_payload["number_occurrences"] == [
        {"number": 9, "occurrences": 2},
        {"number": 21, "occurrences": 1},
    ]

    assert historical.latest_issue == "2026003"
    assert historical.sample_count == 1
    assert historical.matched_transitions == (("2026001", "2026002"),)
    assert [item["issue"] for item in issues] == ["2026003"]

    with SessionLocal() as db:
        db.add(
            User(
                username="analysis_admin",
                password_hash=hash_password("Analysis-admin-12345"),
                role="admin",
                status="active",
                must_change_password=False,
            )
        )
        db.commit()
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "username": "analysis_admin",
                "password": "Analysis-admin-12345",
            },
        )
        assert login.status_code == 200
        issue_response = client.get("/api/v1/analysis/history/issues")
        assert issue_response.status_code == 200
        assert [item["issue"] for item in issue_response.json()["data"]["items"]] == [
            "2026003"
        ]
        analysis_response = client.get("/api/v1/analysis/history/2026003")
        assert analysis_response.status_code == 200
        assert analysis_response.json()["data"]["sample_count"] == 1


def test_historical_analysis_rejects_an_unknown_issue() -> None:
    with SessionLocal() as db, pytest.raises(AnalysisError) as captured:
        calculate_transition_for_issue(db, "2026999")

    assert captured.value.code == "ANALYSIS_ISSUE_NOT_FOUND"
