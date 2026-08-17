"""Confirmed source parsing and idempotency tests."""

from __future__ import annotations

from datetime import date

import httpx
from sqlalchemy import select

from laoliuliu.config import Settings
from laoliuliu.db import SessionLocal
from laoliuliu.ingestion import synchronize_history
from laoliuliu.models import RawSourceSnapshot
from laoliuliu.source import SourceClient, parse_source_document
from laoliuliu.zodiac import ZodiacAnimal


def history_document() -> dict[str, object]:
    return {
        "code": 0,
        "message": "Success",
        "data": [
            {
                "lotteryId": 2032,
                "issue": "2026049",
                "openCode": "01, 11, 29, 38, 04, 33, 17",
                "openTime": "2026-02-18 21:35:30",
                "pet": "蛇",
            },
            {
                "lotteryId": 2032,
                "issue": "2026047",
                "openCode": "02, 12, 30, 39, 05, 34, 18",
                "openTime": "2026-02-16 21:35:33",
                "pet": "蛇",
            },
            {
                "lotteryId": 2032,
                "issue": "2026048",
                "openCode": "27, 08, 43, 33, 42, 11, 29",
                "openTime": "2026-02-17 21:35:33",
                "pet": "蛇",
            },
        ],
    }


def test_history_parser_orders_rows_and_splits_six_plus_one() -> None:
    settings = Settings(env="test")
    records = parse_source_document(
        history_document(), settings=settings, require_history_fields=True
    )
    assert [record.issue for record in records] == ["2026048", "2026049"]
    assert records[0].regular_numbers == (27, 8, 43, 33, 42, 11)
    assert records[0].special_number == 29
    assert records[0].zodiac_anchor is ZodiacAnimal.SNAKE
    assert records[0].open_time.tzinfo == settings.zone


def test_history_sync_is_idempotent() -> None:
    settings = Settings(env="test")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["lotteryId"] == "2032"
        return httpx.Response(200, json=history_document())

    client = SourceClient(settings, transport=httpx.MockTransport(handler))
    with SessionLocal() as db:
        first = synchronize_history(db, client, settings, as_of=date(2026, 2, 18))
        second = synchronize_history(db, client, settings, as_of=date(2026, 2, 18))
        snapshots = list(db.scalars(select(RawSourceSnapshot)))
    assert first.inserted == 2
    assert first.skipped == 0
    assert second.inserted == 0
    assert second.skipped == 2
    assert all(
        [row["issue"] for row in snapshot.payload["data"]] == ["2026049", "2026048"]
        for snapshot in snapshots
    )
