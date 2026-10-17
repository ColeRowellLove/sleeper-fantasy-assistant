"""A read endpoint must not start asking the database more questions than it does today.

The caps are the measured counts on the sample league plus a little room. If a change legitimately
needs more queries, raise the cap in the same pull request and say why; if one endpoint jumps, look
for a query inside a loop first.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from sleeper_assistant.api import app
from sleeper_assistant.api.deps import get_session
from sleeper_assistant.db import Base, make_session_factory
from sleeper_assistant.sample_league import LEAGUE_ID, seed

CAPS = {
    "": 25,
    "/settings": 5,
    "/players": 19,
    "/transactions": 11,
    "/news": 9,
    "/players/s1": 47,
    "/teams/SF": 17,
    "/lineups": 21,
    "/games": 22,
    "/alerts?roster=1": 8,
    "/waiver-wire?roster=1": 29,
    "/rankings": 21,
    "/accuracy": 9,
    "/start-sit/lineup?roster=1": 23,
}


class _Counter:
    def __init__(self) -> None:
        self.n = 0


@pytest.fixture
def counted() -> Iterator[tuple[TestClient, _Counter]]:
    engine: Engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as setup:
        seed(setup)
    counter = _Counter()

    @event.listens_for(engine, "before_cursor_execute")
    def _count(*_args: object) -> None:
        counter.n += 1

    def _session() -> Iterator[object]:
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    yield TestClient(app), counter
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("path", list(CAPS))
def test_an_endpoint_stays_within_its_query_budget(
    counted: tuple[TestClient, _Counter], path: str
) -> None:
    client, counter = counted
    counter.n = 0
    assert client.get(f"/api/leagues/{LEAGUE_ID}{path}").status_code == 200
    assert counter.n <= CAPS[path], f"{path or '/'} ran {counter.n} queries (cap {CAPS[path]})"
