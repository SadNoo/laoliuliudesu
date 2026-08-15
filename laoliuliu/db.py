"""SQLAlchemy engine and request session helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from laoliuliu.config import get_settings


class Base(DeclarativeBase):
    """Base for all database models."""


def _build_engine() -> Engine:
    settings = get_settings()
    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if settings.database_url.endswith(":memory:"):
            engine_options["poolclass"] = StaticPool
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
        **engine_options,
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one database session for a request."""

    with SessionLocal() as session:
        yield session
