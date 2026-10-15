import pytest
from sqlalchemy.orm import Session

from sleeper_assistant.crosswalk import build_crosswalk, link, resolve
from sleeper_assistant.db import CrosswalkRow, PlayerRow


def _player(
    pid: str,
    pos: str,
    ext: dict[str, object],
    status: str = "Active",
    team: str | None = "X",
) -> PlayerRow:
    return PlayerRow(
        player_id=pid, full_name=pid, position=pos, team=team, status=status, external_ids=ext
    )


def test_build_and_report(session: Session) -> None:
    session.add_all(
        [
            _player("1", "RB", {"gsis": "00-1", "espn": 11}),
            _player("2", "WR", {}),  # skill player with no gsis -> unmatched
            _player("3", "DEF", {}),  # not required to have gsis, not counted
            _player("4", "LB", {}),  # not a fantasy position
            _player("5", "TE", {"gsis": "00-5"}, status="Injured Reserve"),  # IR still resolves
            _player("6", "QB", {"gsis": "00-6"}, status="Inactive", team=None),  # retired
        ]
    )
    session.commit()

    report = build_crosswalk(session)

    assert report.total == 3  # RB, WR, TE
    assert report.matched == 2
    assert report.unmatched == ["2"]
    assert 0.6 < report.match_rate < 0.7
    row = session.get(CrosswalkRow, "1")
    assert row is not None
    assert row.espn_id == "11"  # stored as string
    assert resolve(session, "gsis", "00-5") == "5"
    assert resolve(session, "gsis", "00-6") is None


def test_link_survives_rebuild_and_stale_sleeper_ids_clear(session: Session) -> None:
    player = _player("1", "RB", {"gsis": "00-1", "yahoo": 7})
    session.add(player)
    session.commit()
    build_crosswalk(session)
    link(session, "1", "fantasypros", "fp-99")

    player.external_ids = {"gsis": "00-1"}  # Sleeper dropped the yahoo id
    session.commit()
    build_crosswalk(session)

    assert resolve(session, "gsis", "00-1") == "1"
    assert resolve(session, "fantasypros", "fp-99") == "1"  # other sources kept
    assert resolve(session, "yahoo", "7") is None  # stale id cleared


def test_resolve_is_deterministic_for_duplicate_ids(session: Session) -> None:
    session.add_all([_player("b", "WR", {"espn": 1}), _player("a", "WR", {"espn": 1})])
    session.commit()
    build_crosswalk(session)
    assert resolve(session, "espn", "1") == "a"


def test_unknown_source_has_clear_error(session: Session) -> None:
    with pytest.raises(ValueError, match="unknown crosswalk source"):
        resolve(session, "fantasypro", "x")


def test_bulk_link_without_commit(session: Session) -> None:
    session.add(_player("1", "RB", {}))
    session.commit()
    link(session, "1", "fantasycalc", "fc-1", commit=False)
    session.rollback()
    assert resolve(session, "fantasycalc", "fc-1") is None


def test_empty_db_rate(session: Session) -> None:
    assert build_crosswalk(session).match_rate == 1.0
