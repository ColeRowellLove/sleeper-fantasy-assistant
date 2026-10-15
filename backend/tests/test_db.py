from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sleeper_assistant.db import Base, LeagueRow, RosterRow, make_engine


def _league(league_id: str) -> LeagueRow:
    return LeagueRow(
        league_id=league_id,
        name="Family",
        season="2026",
        total_rosters=10,
        scoring_settings={"rec": 1.0},
        roster_positions=["QB", "BN"],
        settings={},
    )


def test_league_round_trip(session: Session) -> None:
    session.add(_league("1"))
    session.commit()
    got = session.get(LeagueRow, "1")
    assert got is not None
    assert got.scoring_settings == {"rec": 1.0}
    assert got.roster_positions == ["QB", "BN"]


def test_rosters_are_keyed_by_league(session: Session) -> None:
    session.add_all([_league("1"), _league("2")])
    session.add_all(
        [
            RosterRow(league_id="1", roster_id=1, players=[], starters=[]),
            RosterRow(league_id="2", roster_id=1, players=[], starters=[]),
        ]
    )
    session.commit()  # same roster_id in two leagues is fine


def test_duplicate_roster_rejected(session: Session) -> None:
    session.add(_league("1"))
    session.add(RosterRow(league_id="1", roster_id=1, players=[], starters=[]))
    session.commit()
    session.add(RosterRow(league_id="1", roster_id=1, players=[], starters=[]))
    with pytest.raises(IntegrityError):
        session.commit()


def test_migrations_match_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    tables = set(inspect(make_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tables
