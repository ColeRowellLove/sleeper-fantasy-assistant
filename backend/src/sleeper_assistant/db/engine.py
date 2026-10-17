"""Building the engine and sessions from the settings (Postgres in production, SQLite in tests)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sleeper_assistant.settings import load_settings


def database_url() -> str:
    return load_settings().database_url


def normalize_url(url: str) -> str:
    """Hosts like Neon hand out postgres:// or postgresql:// URLs; use the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def make_engine(url: str | None = None) -> Engine:
    resolved = normalize_url(url or database_url())
    if resolved.startswith("postgresql"):
        return create_engine(
            resolved,
            pool_pre_ping=True,  # serverless instances freeze; drop dead connections
            pool_size=2,
            max_overflow=2,
            # Neon's pooler (PgBouncer, transaction mode) must not see server-side prepared
            # statements
            connect_args={"prepare_threshold": None},
        )
    return create_engine(resolved)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
