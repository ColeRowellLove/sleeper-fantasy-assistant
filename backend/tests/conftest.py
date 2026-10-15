import os
from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from sleeper_assistant.db import Base, make_engine, make_session_factory


@pytest.fixture
def engine() -> Iterator[Engine]:
    """SQLite in memory by default; set TEST_DATABASE_URL to run against Postgres."""
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    eng = make_engine(url)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with make_session_factory(engine)() as s:
        yield s
