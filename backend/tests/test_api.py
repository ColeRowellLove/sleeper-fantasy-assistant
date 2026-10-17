from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from sleeper_assistant.api import app
from sleeper_assistant.api.deps import get_engine_factory


def _override_engine(factory: Callable[[], Engine]) -> None:
    app.dependency_overrides[get_engine_factory] = lambda: factory


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
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    _override_engine(lambda: engine)

    body = TestClient(app).get("/health/db").json()

    assert body == {
        "database_url_configured": True,
        "database_url_scheme": "sqlite",
        "dialect": "sqlite",
        "status": "ok",
    }


def test_health_db_returns_503_with_only_the_error_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # an unopenable path gives an OperationalError whose message contains the path
    engine = create_engine("sqlite:////nonexistent-dir/secret-name.db")
    _override_engine(lambda: engine)

    resp = TestClient(app).get("/health/db")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"] == "OperationalError"
    assert body["database_url_configured"] is False
    assert body["database_url_scheme"] == "none"
    assert "secret-name" not in resp.text


def test_health_db_reports_an_unparsable_url_instead_of_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "hunter2-should-never-appear"
    monkeypatch.setenv("DATABASE_URL", f"'postgresql://user:{secret}@host/db'")  # stray quote

    def broken() -> Engine:
        return create_engine(f"'postgresql://user:{secret}@host/db'")

    _override_engine(broken)

    resp = TestClient(app).get("/health/db")

    assert resp.status_code == 503
    body = resp.json()
    assert body["error"] == "ArgumentError"
    assert body["database_url_scheme"] == "'postgresql"
    assert secret not in resp.text
