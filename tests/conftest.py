"""Shared isolated database setup."""

from __future__ import annotations

import os

os.environ["LAOLIULIU_ENV"] = "test"
os.environ["LAOLIULIU_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["LAOLIULIU_SESSION_COOKIE_SECURE"] = "false"

import pytest

from laoliuliu.db import Base, engine


@pytest.fixture(autouse=True)
def isolated_schema() -> None:
    """Create a clean schema for every test."""

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
