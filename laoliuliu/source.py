"""Confirmed 00853 history and current draw API client."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from laoliuliu.config import Settings
from laoliuliu.errors import SourceError
from laoliuliu.zodiac import ZodiacAnimal

_ISSUE_PATTERN = re.compile(r"^[0-9]{7}$")


@dataclass(frozen=True)
class SourceDraw:
    """One validated source draw before persistence."""

    issue: str
    open_time: datetime
    regular_numbers: tuple[int, ...]
    special_number: int
    zodiac_anchor: ZodiacAnimal | None


@dataclass(frozen=True)
class SourceBatch:
    """Validated source document and parsed records."""

    source_kind: str
    source_url: str
    document: dict[str, Any]
    records: tuple[SourceDraw, ...]


def parse_source_document(
    document: object,
    *,
    settings: Settings,
    require_history_fields: bool,
) -> tuple[SourceDraw, ...]:
    """Parse the confirmed source response and return in-scope records in order."""

    if not isinstance(document, Mapping):
        raise SourceError("SOURCE_SCHEMA_INVALID", "数据源返回格式无效", 502)
    if document.get("code") != 0 or document.get("message") != "Success":
        raise SourceError("SOURCE_REJECTED", "数据源未返回成功状态", 502)
    raw_records = document.get("data")
    if not isinstance(raw_records, list):
        raise SourceError("SOURCE_SCHEMA_INVALID", "数据源缺少开奖记录", 502)

    records: list[SourceDraw] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, Mapping):
            raise SourceError("SOURCE_RECORD_INVALID", "开奖记录格式无效", 502)
        issue = raw_record.get("issue")
        if not isinstance(issue, str) or not _ISSUE_PATTERN.fullmatch(issue):
            raise SourceError("SOURCE_RECORD_INVALID", "期号格式无效", 502)
        if not issue.startswith(str(settings.data_year)):
            continue
        if issue < settings.data_start_issue_id:
            continue

        if require_history_fields:
            lottery_id = raw_record.get("lotteryId")
            if lottery_id != settings.lottery_id:
                raise SourceError("SOURCE_RECORD_INVALID", "彩种编号不匹配", 502)
            pet = raw_record.get("pet")
            if not isinstance(pet, str):
                raise SourceError("SOURCE_RECORD_INVALID", "开奖记录缺少生肖锚点", 502)
            try:
                zodiac_anchor: ZodiacAnimal | None = ZodiacAnimal.from_source_label(pet)
            except ValueError as error:
                raise SourceError(
                    "SOURCE_RECORD_INVALID", "生肖锚点无法识别", 502
                ) from error
        else:
            zodiac_anchor = None

        open_code = raw_record.get("openCode")
        if not isinstance(open_code, str):
            raise SourceError("SOURCE_RECORD_INVALID", "开奖号码格式无效", 502)
        numbers = _parse_numbers(open_code)

        open_time_raw = raw_record.get("openTime")
        if not isinstance(open_time_raw, str):
            raise SourceError("SOURCE_RECORD_INVALID", "开奖时间格式无效", 502)
        try:
            open_time = datetime.strptime(
                open_time_raw.strip(), "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=settings.zone)
        except ValueError as error:
            raise SourceError(
                "SOURCE_RECORD_INVALID", "开奖时间无法解析", 502
            ) from error
        if open_time.year != settings.data_year:
            raise SourceError("SOURCE_RECORD_INVALID", "期号与开奖年份不一致", 502)

        records.append(
            SourceDraw(
                issue=issue,
                open_time=open_time,
                regular_numbers=tuple(numbers[:6]),
                special_number=numbers[6],
                zodiac_anchor=zodiac_anchor,
            )
        )

    records.sort(key=lambda record: (record.open_time, record.issue))
    if len({record.issue for record in records}) != len(records):
        raise SourceError("SOURCE_RECORD_CONFLICT", "数据源包含重复期号", 502)
    return tuple(records)


def _parse_numbers(value: str) -> list[int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 7:
        raise SourceError(
            "SOURCE_RECORD_INVALID", "每期必须包含六个平码和一个特码", 502
        )
    try:
        numbers = [int(part) for part in parts]
    except ValueError as error:
        raise SourceError("SOURCE_RECORD_INVALID", "开奖号码必须为整数", 502) from error
    if any(number < 1 or number > 49 for number in numbers):
        raise SourceError("SOURCE_RECORD_INVALID", "开奖号码超出1至49", 502)
    if len(set(numbers)) != 7:
        raise SourceError("SOURCE_RECORD_INVALID", "同期开奖号不可重复", 502)
    return numbers


class SourceClient:
    """HTTP client with bounded retries and response validation."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def fetch_history(self, as_of: date) -> SourceBatch:
        """Fetch available in-scope history through the approved history API."""

        url = self._settings.history_source_url
        document = self._fetch_json(
            url,
            params={
                "issueNum": as_of.isoformat(),
                "lotteryId": self._settings.lottery_id,
            },
        )
        records = parse_source_document(
            document,
            settings=self._settings,
            require_history_fields=True,
        )
        return SourceBatch("history", url, document, records)

    def fetch_current(self) -> SourceBatch:
        """Fetch the current five-row incremental API response."""

        url = self._settings.source_url
        document = self._fetch_json(url, params=None)
        records = parse_source_document(
            document,
            settings=self._settings,
            require_history_fields=False,
        )
        return SourceBatch("current", url, document, records)

    def _fetch_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | bool | None] | None,
    ) -> dict[str, Any]:
        timeout = httpx.Timeout(
            connect=5.0,
            read=self._settings.request_timeout_seconds,
            write=5.0,
            pool=5.0,
        )
        headers = {"User-Agent": "laoliuliu/0.1 (+private historical analysis)"}
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                with httpx.Client(
                    timeout=timeout,
                    follow_redirects=False,
                    transport=self._transport,
                ) as client:
                    response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                if len(response.content) > self._settings.source_max_bytes:
                    raise SourceError(
                        "SOURCE_RESPONSE_TOO_LARGE", "数据源响应超过安全上限", 502
                    )
                parsed = response.json()
                if not isinstance(parsed, dict):
                    raise SourceError(
                        "SOURCE_SCHEMA_INVALID", "数据源返回格式无效", 502
                    )
                json.dumps(parsed, ensure_ascii=False)
                return parsed
            except SourceError:
                raise
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
                last_error = error
                if attempt == 0:
                    time.sleep(0.5)
        raise SourceError(
            "SOURCE_UNAVAILABLE", "暂时无法读取开奖数据", 502
        ) from last_error
