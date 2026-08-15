"""Stable application errors safe for API responses."""

from __future__ import annotations


class AppError(Exception):
    """Base error with a stable code and HTTP status."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AuthenticationError(AppError):
    """Authentication or session rejection."""


class AuthorizationError(AppError):
    """Role or account status rejection."""


class SourceError(AppError):
    """Source transport, schema, or data conflict failure."""


class AnalysisError(AppError):
    """Deterministic analysis cannot be produced."""


class AiServiceError(AppError):
    """OpenAI-compatible provider request or response failure."""
