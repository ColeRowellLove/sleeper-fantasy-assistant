"""The sample league loads, and every league endpoint the pages use answers for it."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sleeper_assistant.api import app
from sleeper_assistant.api_deps import get_session
from sleeper_assistant.db import Base, make_session_factory
from sleeper_assistant.sample_league import CURRENT_WEEK, LEAGUE_ID, seed

PATHS = [
    "",
    "/settings",
    "/players",
    "/lineups",
    "/games",
    "/alerts?roster=1",
    "/waiver-wire?roster=1",
    "/rankings",
    "/accuracy",
    "/start-sit/lineup?roster=1",
    "/teams/SF",
]


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as setup:
        seed(setup)

    def _session() -> Iterator[Session]:
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("path", PATHS)
def test_every_league_endpoint_answers_for_the_sample(client: TestClient, path: str) -> None:
    resp = client.get(f"/api/leagues/{LEAGUE_ID}{path}")
    assert resp.status_code == 200, resp.text


def test_the_sample_has_a_week_in_progress_a_bye_and_standings(client: TestClient) -> None:
    body = client.get(f"/api/leagues/{LEAGUE_ID}").json()
    assert body["week"] == CURRENT_WEEK and len(body["standings"]) == 6
    assert sum(r["wins"] for r in body["standings"]) == 3 * (CURRENT_WEEK - 1)
    states = {p["game"]["state"] for r in body["rosters"] for p in r["players"] if p.get("game")}
    assert {"upcoming", "live", "final", "bye"} <= states
