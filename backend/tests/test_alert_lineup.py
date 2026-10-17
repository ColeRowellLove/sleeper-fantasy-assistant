"""Lineup move alert: a bench player projected well above the starter he could replace."""

from datetime import timedelta

from sqlalchemy.orm import Session

from sleeper_assistant.alerts import lineup as alert_lineup
from sleeper_assistant.alerts.engine import run_all_leagues
from sleeper_assistant.db import (
    AlertRow,
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    RosterRow,
    utcnow,
)

SOON = (utcnow() + timedelta(days=1)).date().isoformat()
DETECTORS = {"lineup_move": alert_lineup.detect_lineup_move}


def _player(pid: str, pos: str, name: str, team: str) -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=name, position=pos, team=team, external_ids={})


def _proj(pid: str, team: str, yards: float) -> PlayerProjectionRow:
    return PlayerProjectionRow(
        season="2026", week=7, player_id=pid, team=team, stats={"rush_yd": yards},
        fetched_at=utcnow(),
    )  # fmt: skip


def _setup(session: Session, bench_yards: float = 80.0, status: str = "pre_game") -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1, scoring_settings={"rush_yd": 0.1},
        roster_positions=["RB", "BN"], settings={}, last_viewed_at=utcnow(),
    )  # fmt: skip
    session.add(league)
    session.add(
        NflGameRow(game_id="g", season="2026", week=7, home="SF", away="DAL",
                   game_date=SOON, status=status)
    )  # fmt: skip
    session.add_all(
        [
            _player("weak", "RB", "Weak Back", "SF"), _player("strong", "RB", "Strong Back", "DAL"),
            _proj("weak", "SF", 20.0), _proj("strong", "DAL", bench_yards),
            RosterRow(league_id="L1", roster_id=1, owner_id="u1", players=["weak", "strong"],
                      starters=["weak"], reserve=[], taxi=[], wins=0, losses=0, ties=0,
                      points_for=0, points_against=0),
        ]
    )  # fmt: skip
    session.commit()
    return league


def _run(session: Session) -> int:
    now = utcnow()
    return run_all_leagues(session, now - timedelta(days=1), DETECTORS, now)


def test_a_clear_gain_is_told_once_with_both_projections(session: Session) -> None:
    _setup(session)
    assert _run(session) == 1
    alert = session.query(AlertRow).one()
    assert (alert.kind, alert.roster_id, alert.player_id) == ("lineup_move", 1, "strong")
    assert alert.title == "Start Strong Back over Weak Back: +6.0 projected points"
    assert "projected 8.0" in alert.why and "projected 2.0" in alert.why
    assert alert.data["gain"] == 6.0
    assert _run(session) == 0  # said once


def test_a_gain_under_the_threshold_is_not_told(session: Session) -> None:
    _setup(session, bench_yards=40.0)  # 4.0 vs 2.0: only +2
    assert _run(session) == 0


def test_a_locked_spot_is_not_told(session: Session) -> None:
    _setup(session, status="complete")  # the games are over
    assert _run(session) == 0


def test_a_starter_on_a_bye_is_left_to_the_bye_alert(session: Session) -> None:
    _setup(session)
    weak = session.get(PlayerRow, "weak")
    assert weak is not None
    weak.team = "SEA"  # SEA has no game this week
    session.add(
        NflGameRow(game_id="h", season="2026", week=8, home="SEA", away="DEN",
                   game_date="2026-11-01", status="pre_game")
    )  # fmt: skip
    session.commit()
    assert _run(session) == 0


def test_nothing_is_said_more_than_two_days_before_the_first_game(session: Session) -> None:
    _setup(session)
    game = session.get(NflGameRow, "g")
    assert game is not None
    game.game_date = (utcnow() + timedelta(days=5)).date().isoformat()
    session.commit()
    assert _run(session) == 0


def test_no_projections_no_alert(session: Session) -> None:
    _setup(session)
    session.query(PlayerProjectionRow).delete()
    session.commit()
    assert _run(session) == 0
