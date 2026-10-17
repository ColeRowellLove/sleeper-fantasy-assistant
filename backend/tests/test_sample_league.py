"""The sample league loads, and every league endpoint the pages use answers for it."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sleeper_assistant.api import app
from sleeper_assistant.api.deps import get_session
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


def test_the_box_score_route_answers_and_says_so_when_espn_has_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sleeper_assistant.core.sources import box_score as module  # noqa: PLC0415

    def ok(season: str, week: int, home: str, away: str) -> module.BoxScore:
        return module.BoxScore(home=home, away=away, final=True, teams=[])

    def nothing(season: str, week: int, home: str, away: str) -> module.BoxScore:
        raise module.BoxScoreError("down")

    url = f"/api/leagues/{LEAGUE_ID}/games/7/WAS/KC/box"
    module.reset_cache()
    monkeypatch.setattr(module, "FETCHER", ok)
    assert client.get(url).json()["home"] == "KC"
    module.reset_cache()
    monkeypatch.setattr(module, "FETCHER", nothing)
    assert client.get(url).status_code == 502
    assert client.get(f"/api/leagues/{LEAGUE_ID}/games/7/ZZZ/KC/box").status_code == 404
    module.reset_cache()
