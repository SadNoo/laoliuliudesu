"""AI response boundary and scheduler timing tests."""

from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from laoliuliu.ai import (
    AiProviderConfig,
    request_ai_explanation,
    validate_ai_result,
    validate_provider_base_url,
)
from laoliuliu.analysis import TransitionAnalysis
from laoliuliu.config import Settings
from laoliuliu.errors import AiServiceError
from laoliuliu.scheduler import seconds_until_next_run
from laoliuliu.zodiac import ZodiacAnimal


def test_ai_result_accepts_only_bounded_explanation() -> None:
    assert validate_ai_result(
        {"summary": "只解释统计结果。", "observations": ["样本内虎出现最多。"]}
    ) == {"summary": "只解释统计结果。", "observations": ["样本内虎出现最多。"]}
    with pytest.raises(AiServiceError):
        validate_ai_result({"summary": "缺少观察项", "observations": []})


def test_provider_requires_https_without_credentials() -> None:
    assert validate_provider_base_url("https://api.openai.com/v1/") == (
        "https://api.openai.com/v1"
    )
    with pytest.raises(ValueError):
        validate_provider_base_url("http://127.0.0.1:8000/v1")


def test_deepseek_requests_disable_thinking_by_default() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"summary": "统计摘要", "observations": ["观察项"]},
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    analysis = TransitionAnalysis(
        latest_issue="2026226",
        latest_regular_numbers=(1, 2, 3, 4, 5, 6),
        latest_special_number=17,
        latest_special_zodiac=ZodiacAnimal.TIGER,
        sample_count=1,
        total_regular_occurrences=6,
        matched_transitions=(("2026200", "2026201"),),
        ranking=(),
    )
    result = request_ai_explanation(
        AiProviderConfig(
            display_name="DeepSeek",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-v4-flash",
            api_key="test-key",
        ),
        analysis,
        Settings(env="test"),
        transport=httpx.MockTransport(handler),
    )

    assert captured_payload["thinking"] == {"type": "disabled"}
    assert result == {"summary": "统计摘要", "observations": ["观察项"]}


def test_scheduler_targets_hong_kong_2135() -> None:
    settings = Settings(env="test", timezone="Asia/Hong_Kong")
    before = datetime(2026, 8, 15, 21, 30, tzinfo=settings.zone)
    after = datetime(2026, 8, 15, 21, 40, tzinfo=settings.zone)
    assert seconds_until_next_run(before, settings) == 300
    assert seconds_until_next_run(after, settings) == 23 * 3600 + 55 * 60
