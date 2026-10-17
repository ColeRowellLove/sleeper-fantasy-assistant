"""Bye week alert: a starter whose team has no game this week, told once per player per week."""

from datetime import timedelta

from sqlalchemy.orm import Session

from sleeper_assistant import alert_bye
from sleeper_assistant.alerts import run_all_leagues
from sleeper_assistant.db import (
    AlertRow,
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    RosterRow,
    utcnow,
)

SOON = (utcnow() + timedelta(days=2)).date().isoformat()
DETECTORS = {"bye_week": alert_bye.detect_bye_week}


def _player(pid: str, pos: str, name: str, team: str) -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=name, position=pos, team=team, external_ids={})


def _proj(pid: str, team: str, yards: float) -> PlayerProjectionRow:
    return PlayerProjectionRow(
        season="2026", week=7, player_id=pid, team=team, stats={"rush_yd": yards},
        fetched_at=utcnow(),
    )  # fmt: skip


def _setup(session: Session, games: bool = True) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1, scoring_settings={"rush_yd": 0.1},
        roster_positions=["RB", "WR", "BN", "BN"], settings={}, last_viewed_at=utcnow(),
    )  # fmt: skip
    session.add(league)
    if games:  # SF and DAL play; SEA and DEN are on a bye
        session.add(
            NflGameRow(game_id="g", season="2026", week=7, home="SF", away="DAL",
                       game_date=SOON, status="pre_game")
        )  # fmt: skip
        session.add(
            NflGameRow(game_id="h", season="2026", week=8, home="SEA", away="DEN",
                       game_date="2026-11-01", status="pre_game")
        )  # fmt: skip
    session.add_all(
        [
            _player("rb_bye", "RB", "Bye Back", "SEA"), _player("wr", "WR", "Receiver", "SF"),
            _player("rb_ok", "RB", "Good Back", "SF"), _player("rb_bye2", "RB", "Other Bye", "DEN"),
            _proj("rb_ok", "SF", 70.0), _proj("rb_bye2", "DEN", 200.0), _proj("wr", "SF", 60.0),
            RosterRow(league_id="L1", roster_id=1, owner_id="u1",
                      players=["rb_bye", "wr", "rb_ok", "rb_bye2"], starters=["rb_bye", "wr"],
                      reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0,
                      points_against=0),
        ]
    )  # fmt: skip
    session.commit()
    return league


def _run(session: Session) -> int:
    now = utcnow()
    return run_all_leagues(session, now - timedelta(days=1), DETECTORS, now)


def test_a_starter_on_a_bye_is_told_once_with_a_replacement(session: Session) -> None:
    _setup(session)
    assert _run(session) == 1
    alert = session.query(AlertRow).one()
    assert (alert.kind, alert.roster_id, alert.player_id) == ("bye_week", 1, "rb_bye")
    assert alert.title == "Bye Back (RB, SEA) is on a bye in week 7"
    assert "RB spot" in alert.why and "Good Back" in alert.why
    assert "Other Bye" not in alert.why  # a bench player who is also on a bye is no replacement
    assert _run(session) == 0  # said once


def test_nobody_is_told_without_a_schedule_or_without_a_starter_on_a_bye(session: Session) -> None:
    _setup(session, games=False)
    assert _run(session) == 0  # no games: cannot tell a bye from missing data


def test_nothing_is_said_more_than_three_days_before_the_first_game(session: Session) -> None:
    _setup(session)
    game = session.get(NflGameRow, "g")
    assert game is not None
    game.game_date = (utcnow() + timedelta(days=6)).date().isoformat()
    session.commit()
    assert _run(session) == 0
    game.game_date = (utcnow() + timedelta(days=3)).date().isoformat()
    session.commit()
    assert _run(session) == 1


def test_when_nobody_on_the_bench_can_play_the_alert_says_so(session: Session) -> None:
    _setup(session)
    roster = session.get(RosterRow, ("L1", 1))
    assert roster is not None
    roster.players = ["rb_bye", "wr", "rb_bye2"]  # the only other back is also on a bye
    session.commit()
    assert _run(session) == 1
    why = session.query(AlertRow).one().why
    assert "Nobody on your bench can play that slot this week." in why


def test_a_bench_player_on_a_bye_is_not_news(session: Session) -> None:
    _setup(session)
    roster = session.get(RosterRow, ("L1", 1))
    assert roster is not None
    roster.starters = ["wr", "rb_ok"]
    session.commit()
    assert _run(session) == 0
