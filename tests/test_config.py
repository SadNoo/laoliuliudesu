"""Production configuration safety tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from laoliuliu.config import Settings


def test_production_rejects_default_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            database_url="postgresql+psycopg://app:password@postgres/app",
            session_cookie_secure=True,
            public_origin="https://example.com",
        )


def test_production_accepts_explicit_secure_configuration() -> None:
    settings = Settings(
        env="production",
        database_url="postgresql+psycopg://app:password@postgres/app",
        session_pepper="session-pepper-with-at-least-32-characters",
        ai_encryption_key="MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTE=",
        session_cookie_secure=True,
        public_origin="https://example.com",
    )
    assert settings.env == "production"
    assert settings.data_start_issue_id == "2026048"


def test_project_rejects_a_different_data_start_issue() -> None:
    with pytest.raises(ValidationError):
        Settings(env="test", data_start_issue=1)
