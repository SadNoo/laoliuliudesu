"""OpenAI-compatible explanation client for deterministic results."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from laoliuliu.analysis import TransitionAnalysis
from laoliuliu.config import Settings
from laoliuliu.errors import AiServiceError

PROMPT_VERSION = "zodiac-transition-explanation-v1"
logger = logging.getLogger("laoliuliu.ai")


@dataclass(frozen=True)
class AiProviderConfig:
    """Decrypted provider inputs used for one request."""

    display_name: str
    base_url: str
    model: str
    api_key: str


def validate_provider_base_url(value: str) -> str:
    """Accept an HTTPS API base URL without credentials, query, or fragment."""

    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("AI Base URL 必须是无凭据、查询或片段的 HTTPS 地址")
    return normalized


def request_ai_explanation(
    provider: AiProviderConfig,
    analysis: TransitionAnalysis,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Ask an OpenAI-compatible endpoint to explain, not alter, the ranking."""

    normalized_base_url = validate_provider_base_url(provider.base_url)
    endpoint = f"{normalized_base_url}/chat/completions"
    source_result = analysis.to_dict()
    system_prompt = (
        "你是历史开奖数据解释助手。只解释后端已经计算完成的2026年生肖条件频率。"
        "不得改变排名、补造样本、输出具体号码、声称能够保证命中，或引用其他分析方法。"
        "必须返回JSON对象，字段仅包含summary字符串与observations字符串数组。"
    )
    user_prompt = json.dumps(
        {
            "judgement_rule": (
                "以最新特码生肖为条件，查找2026年内相同特码生肖的历史期数，"
                "逐次统计其下一期六个平码生肖；出现几次计算几次。"
            ),
            "deterministic_result": source_result,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
    }
    if urlsplit(normalized_base_url).hostname == "api.deepseek.com":
        # DeepSeek V4 enables thinking by default. This short, structured explanation
        # needs the final JSON body rather than a reasoning trace consuming the limit.
        payload["thinking"] = {"type": "disabled"}
    timeout = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=10.0)
    try:
        with httpx.Client(
            timeout=timeout, follow_redirects=False, transport=transport
        ) as client:
            response = client.post(
                endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {provider.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "laoliuliu/0.1",
                },
            )
        response.raise_for_status()
    except httpx.HTTPError as error:
        response_status = (
            error.response.status_code
            if isinstance(error, httpx.HTTPStatusError)
            else None
        )
        logger.warning(
            "AI provider request failed host=%s model=%s status=%s error_type=%s",
            urlsplit(normalized_base_url).hostname,
            provider.model,
            response_status,
            type(error).__name__,
        )
        raise AiServiceError(
            "AI_PROVIDER_UNAVAILABLE", "AI服务暂时不可用", 502
        ) from error
    if len(response.content) > settings.ai_max_response_bytes:
        raise AiServiceError("AI_RESPONSE_TOO_LARGE", "AI响应超过安全上限", 502)
    try:
        document = response.json()
        content = document["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        logger.warning(
            "AI provider response invalid host=%s model=%s bytes=%s error_type=%s",
            urlsplit(normalized_base_url).hostname,
            provider.model,
            len(response.content),
            type(error).__name__,
        )
        raise AiServiceError("AI_RESPONSE_INVALID", "AI返回格式无效", 502) from error
    return validate_ai_result(parsed)


def validate_ai_result(value: object) -> dict[str, Any]:
    """Validate and bound the model-authored explanation."""

    if not isinstance(value, dict):
        raise AiServiceError("AI_RESPONSE_INVALID", "AI返回格式无效", 502)
    summary = value.get("summary")
    observations = value.get("observations")
    if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 1000:
        raise AiServiceError("AI_RESPONSE_INVALID", "AI摘要格式无效", 502)
    if not isinstance(observations, list) or not 1 <= len(observations) <= 8:
        raise AiServiceError("AI_RESPONSE_INVALID", "AI观察项格式无效", 502)
    normalized: list[str] = []
    for observation in observations:
        if not isinstance(observation, str) or not 1 <= len(observation.strip()) <= 500:
            raise AiServiceError("AI_RESPONSE_INVALID", "AI观察项格式无效", 502)
        normalized.append(observation.strip())
    return {"summary": summary.strip(), "observations": normalized}
