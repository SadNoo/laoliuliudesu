"""Validated HTTP request contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(min_length=1, max_length=16)


class UpdateAiProviderRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=8, max_length=2048)
    model: str = Field(min_length=1, max_length=128)
    api_key: str | None = Field(default=None, min_length=8, max_length=2048)
    clear_api_key: bool = False
    enabled: bool = False
