import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sleeper_assistant.api import app, get_session, get_sleeper
from sleeper_assistant.db import Base, LeagueRow, make_session_factory
from sleeper_assistant.sleeper import BASE_URL, SleeperClient

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "sleeper_league.json").read_text()
)


def _routes() -> dict[str, Any]:
    routes: dict[str, Any] = {
        "/state/nfl": FIXTURE["state"],
        "/user/cole": FIXTURE["users"][0],
        "/user/nobody": None,
        "/user/u1/leagues/nfl/2026": [FIXTURE["league"]],
        "/league/L1": FIXTURE["league"],
        "/league/L1/users": FIXTURE["users"],
        "/league/L1/rosters": FIXTURE["rosters"],
        "/league/999": None,
    }
    routes["/league/1"] = FIXTURE["league"] | {"league_id": "1"}
    routes["/league/1/users"] = FIXTURE["users"]
    routes["/league/1/rosters"] = FIXTURE["rosters"]
    for week, items in FIXTURE["matchups"].items():
        routes[f"/league/1/matchups/{week}"] = items
    for week, items in FIXTURE["transactions"].items():
        routes[f"/league/1/transactions/{week}"] = items
    return routes


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path.removeprefix("/v1")
    routes = _routes()
    if path == "/user/down":
        return httpx.Response(503)
    if path in routes:
        # content= (not json=) so a None route is sent as the literal JSON null Sleeper returns
        return httpx.Response(200, content=json.dumps(routes[path]))
    return httpx.Response(404)


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)

    def _session() -> Iterator[Session]:
        with factory() as s:
            yield s

    sleeper = SleeperClient(
        httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(_handler))
    )
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_sleeper] = lambda: sleeper
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def test_list_leagues_for_username(client: TestClient) -> None:
    resp = client.get("/api/users/cole/leagues")
    assert resp.status_code == 200
    assert resp.json() == [
        {"league_id": "L1", "name": "Family League", "season": "2026", "total_rosters": 2}
    ]


def test_unknown_user_is_404(client: TestClient) -> None:
    assert client.get("/api/users/nobody/leagues").status_code == 404


def test_sleeper_down_is_502(client: TestClient) -> None:
    assert client.get("/api/users/down/leagues").status_code == 502


@pytest.mark.parametrize("bad", ["a b", "x" * 41, "../etc"])
def test_username_is_validated(client: TestClient, bad: str) -> None:
    assert client.get(f"/api/users/{bad}/leagues").status_code in (404, 422)


def test_season_is_validated(client: TestClient) -> None:
    assert client.get("/api/users/cole/leagues?season=20x6").status_code == 422


def test_connect_syncs_and_marks_active(client: TestClient) -> None:
    resp = client.post("/api/leagues/1/connect")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Family League"
    assert body["rules"]["uses_faab"] is True
    assert body["rules"]["trade_deadline_week"] == 11

    session = app.dependency_overrides[get_session]()
    league = session.__next__().get(LeagueRow, "1")  # type: ignore[attr-defined]
    assert league is not None
    assert league.last_viewed_at is not None
    assert league.last_synced_at is not None


def test_connect_unknown_league_is_404(client: TestClient) -> None:
    assert client.post("/api/leagues/999/connect").status_code == 404


def test_connect_rejects_non_numeric_league_id(client: TestClient) -> None:
    assert client.post("/api/leagues/abc/connect").status_code == 422


def test_connect_twice_within_cooldown_syncs_once(client: TestClient) -> None:
    calls: list[str] = []
    original = app.dependency_overrides[get_sleeper]()
    counting = httpx.Client(
        base_url=BASE_URL,
        transport=httpx.MockTransport(lambda r: (calls.append(r.url.path), _handler(r))[1]),
    )
    app.dependency_overrides[get_sleeper] = lambda: SleeperClient(counting)
    del original

    assert client.post("/api/leagues/1/connect").status_code == 200
    first = len(calls)
    assert first > 0
    assert client.post("/api/leagues/1/connect").status_code == 200
    assert len(calls) == first  # cooldown: second connect made no Sleeper requests


def test_unexpected_sleeper_payload_is_502(client: TestClient) -> None:
    bad = SleeperClient(
        httpx.Client(
            base_url=BASE_URL,
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"league_id": 1})),
        )
    )
    app.dependency_overrides[get_sleeper] = lambda: bad
    assert client.post("/api/leagues/1/connect").status_code == 502
