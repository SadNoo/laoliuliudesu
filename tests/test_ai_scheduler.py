"""AI response boundary and scheduler timing tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from laoliuliu.ai import validate_ai_result, validate_provider_base_url
from laoliuliu.config import Settings
from laoliuliu.errors import AiServiceError
from laoliuliu.scheduler import seconds_until_next_run


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


def test_scheduler_targets_hong_kong_2135() -> None:
    settings = Settings(env="test", timezone="Asia/Hong_Kong")
    before = datetime(2026, 8, 15, 21, 30, tzinfo=settings.zone)
    after = datetime(2026, 8, 15, 21, 40, tzinfo=settings.zone)
    assert seconds_until_next_run(before, settings) == 300
    assert seconds_until_next_run(after, settings) == 23 * 3600 + 55 * 60
