import importlib.util
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.pool import QueuePool

from sleeper_assistant.db import make_engine


def test_vercel_entrypoint_exposes_the_fastapi_app() -> None:
    path = Path(__file__).parents[1] / "app.py"
    spec = importlib.util.spec_from_file_location("vercel_entrypoint", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.app, FastAPI)


def test_postgres_engine_is_serverless_and_pooler_safe() -> None:
    engine = make_engine("postgresql://u:p@ep-x-pooler.neon.tech/db?sslmode=require")
    assert engine.dialect.driver == "psycopg"
    assert engine.dialect.name == "postgresql"
    assert isinstance(engine.pool, QueuePool)  # small bounded pool, not unbounded connections
    assert engine.pool.size() == 2


def test_sqlite_engine_gets_no_postgres_options() -> None:
    engine = make_engine("sqlite://")
    assert engine.dialect.name == "sqlite"
