"""Validated environment configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="LAOLIULIU_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+pysqlite:///./data/laoliuliu.db"
    session_pepper: SecretStr = SecretStr("development-only-session-pepper-change-me")
    ai_encryption_key: SecretStr = SecretStr(
        "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    )
    session_cookie_secure: bool = False
    session_hours: int = Field(default=8, ge=1, le=168)

    source_url: str = "https://api.00853lhc.com/api/opencode/2032"
    history_source_url: str = "https://api.00853lhc.com/api/HistoryOpenInfo"
    lottery_id: int = 2032
    data_year: int = 2026
    timezone: str = "Asia/Hong_Kong"
    sync_hour: int = Field(default=21, ge=0, le=23)
    sync_minute: int = Field(default=35, ge=0, le=59)
    sync_empty_retries: int = Field(default=5, ge=0, le=10)
    sync_empty_retry_seconds: int = Field(default=120, ge=30, le=900)

    public_origin: str = "http://localhost:8000"
    request_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    source_max_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)
    ai_max_response_bytes: int = Field(default=262_144, ge=1024, le=2_097_152)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("public_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        normalized = value.rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("public_origin must be an HTTP(S) origin")
        return normalized

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.env != "production":
            return self
        if not self.session_cookie_secure:
            raise ValueError("production requires secure session cookies")
        session_pepper = self.session_pepper.get_secret_value()
        if "development-only" in session_pepper or len(session_pepper) < 32:
            raise ValueError("production session pepper must be replaced")
        encryption_key = self.ai_encryption_key.get_secret_value()
        if encryption_key == "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=":
            raise ValueError("production AI encryption key must be replaced")
        try:
            Fernet(encryption_key.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as error:
            raise ValueError(
                "production AI encryption key must be a Fernet key"
            ) from error
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("production database must use PostgreSQL with psycopg")
        if self.public_origin.startswith("http://"):
            raise ValueError("production public_origin must use HTTPS")
        return self

    @property
    def zone(self) -> ZoneInfo:
        """Return the configured IANA timezone."""

        return ZoneInfo(self.timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide validated settings object."""

    secrets_dir = os.getenv("LAOLIULIU_SECRETS_DIR")
    if secrets_dir:
        return Settings(_secrets_dir=secrets_dir)  # type: ignore[call-arg]
    return Settings()
