from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sleeper_assistant.api import app, get_session


def _override_session(engine: Engine) -> None:
    def _session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _session


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def test_health() -> None:
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_db_reports_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    _override_session(
        create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    )
    body = TestClient(app).get("/health/db").json()
    assert body == {"database_url_configured": True, "dialect": "sqlite", "status": "ok"}


def test_health_db_returns_503_with_only_the_error_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # an unopenable path gives an OperationalError whose message contains the path
    _override_session(create_engine("sqlite:////nonexistent-dir/secret-name.db"))

    resp = TestClient(app).get("/health/db")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"] == "OperationalError"
    assert body["database_url_configured"] is False
    assert "secret-name" not in resp.text
