"""The first injury alert: a player is ruled out, told once to every team that has him."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant import alert_injury, alerts
from sleeper_assistant.alerts import run_all_leagues
from sleeper_assistant.db import (
    AlertRow,
    LeagueRow,
    NflGameRow,
    PlayerInjuryRow,
    PlayerProjectionRow,
    PlayerRow,
    RosterRow,
    TeamDepthChartRow,
    utcnow,
)

SCORING = {"rush_yd": 0.1, "rec_yd": 0.1}


def _player(  # noqa: PLR0913, PLR0917
    pid: str,
    pos: str,
    name: str,
    status: str | None = None,
    part: str | None = None,
    team: str = "SF",
) -> PlayerRow:
    return PlayerRow(
        player_id=pid, full_name=name, position=pos, team=team, injury_status=status,
        injury_body_part=part, external_ids={},
    )  # fmt: skip


def _proj(pid: str, yards: float) -> PlayerProjectionRow:
    return PlayerProjectionRow(
        season="2026", week=7, player_id=pid, team="SF", stats={"rush_yd": yards},
        fetched_at=utcnow(),
    )  # fmt: skip


def _roster(
    rid: int,
    players: list[str],
    starters: list[str],
    reserve: list[str] | None = None,
    taxi: list[str] | None = None,
) -> RosterRow:
    return RosterRow(
        league_id="L1", roster_id=rid, owner_id=f"u{rid}", players=players, starters=starters,
        reserve=reserve or [], taxi=taxi or [], wins=0, losses=0, ties=0, points_for=0,
        points_against=0,
    )  # fmt: skip


def _setup(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=3, scoring_settings=SCORING,
        roster_positions=["RB", "WR", "BN", "BN"], settings={}, last_viewed_at=utcnow(),
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            NflGameRow(game_id="g", season="2026", week=7, home="SF", away="DAL",
                       game_date="2026-10-25", status="pre_game"),
            _player("star", "RB", "Star Back"), _player("bench", "RB", "Bench Back"),
            _player("hurt", "RB", "Hurt Back", status="Out", part="Hamstring", team="SF"),
            _player("wr", "WR", "Receiver"),
            _proj("star", 100.0), _proj("bench", 80.0), _proj("hurt", 120.0), _proj("wr", 90.0),
            # team 1 starts him, team 2 has him on the bench, team 3 has him on IR
            _roster(1, ["hurt", "bench", "wr"], ["hurt", "wr"]),
            _roster(2, ["hurt", "star"], ["star"]),
            _roster(3, ["hurt"], [], reserve=["hurt"]),
        ]
    )  # fmt: skip
    session.commit()
    return league


def _healthy_first_then_out(session: Session, league: LeagueRow, now) -> None:  # type: ignore[no-untyped-def]
    """Record him healthy, then Out an hour later: the change the detector reads."""
    hurt = session.get(PlayerRow, "hurt")
    assert hurt is not None
    hurt.injury_status = None
    session.commit()
    run_all_leagues(
        session,
        now - timedelta(days=1),
        {"injury_out": alert_injury.detect_ruled_out},
        now - timedelta(hours=1),
    )
    hurt.injury_status = "Out"
    session.commit()


def _run(session: Session, league: LeagueRow, now) -> int:  # type: ignore[no-untyped-def]
    return run_all_leagues(
        session, now - timedelta(days=1), {"injury_out": alert_injury.detect_ruled_out}, now
    )


def test_the_first_sight_of_a_player_who_is_already_out_is_not_news(session: Session) -> None:
    league = _setup(session)
    now = utcnow()
    assert _run(session, league, now) == 0
    row = session.get(PlayerInjuryRow, "hurt")
    assert row is not None and (row.status, row.changed_at) == ("Out", None)
    assert _run(session, league, now + timedelta(minutes=10)) == 0


def test_ruling_a_player_out_alerts_each_team_that_has_him_once(session: Session) -> None:
    league = _setup(session)
    now = utcnow()
    _healthy_first_then_out(session, league, now)
    assert _run(session, league, now) == 3
    by_team = {a.roster_id: a for a in session.scalars(select(AlertRow))}
    assert set(by_team) == {1, 2, 3}
    assert all(a.kind == "injury_out" and a.player_id == "hurt" for a in by_team.values())
    assert by_team[1].title == "Hurt Back (RB, SF) was ruled out"
    assert _run(session, league, now + timedelta(minutes=10)) == 0  # told once


def test_a_starter_is_told_where_he_starts_and_the_best_bench_replacement(session: Session) -> None:
    league = _setup(session)
    now = utcnow()
    _healthy_first_then_out(session, league, now)
    _run(session, league, now)
    why = next(a.why for a in session.scalars(select(AlertRow)) if a.roster_id == 1)
    assert why.startswith("Hurt Back was ruled out with a hamstring injury.")
    assert "He starts at RB for you in week 7 (projected 12.0)." in why
    assert "Best replacement on your bench: Bench Back (RB, projected 8.0)." in why


def test_a_bench_or_ir_player_gets_a_shorter_note_without_a_replacement(session: Session) -> None:
    league = _setup(session)
    now = utcnow()
    _healthy_first_then_out(session, league, now)
    _run(session, league, now)
    whys = {a.roster_id: a.why for a in session.scalars(select(AlertRow))}
    assert whys[2].endswith("He is on your bench.")
    assert "replacement" not in whys[2]
    assert whys[3].endswith("He is already on your injured reserve.")


def test_the_depth_chart_next_man_up_is_named_with_whether_he_is_free(session: Session) -> None:
    league = _setup(session)
    session.add(_player("next", "RB", "Backup Back"))
    chart = {"offense": {"rb": [
        {"name": "Hurt Back", "sleeper_id": "hurt", "espn_id": "1", "injury": "Out"},
        {"name": "Backup Back", "sleeper_id": "next", "espn_id": "2", "injury": None},
    ]}, "defense": {}, "special": {}}  # fmt: skip
    session.add(TeamDepthChartRow(team="SF", source="ESPN", chart=chart, fetched_at=utcnow()))
    session.commit()
    now = utcnow()
    _healthy_first_then_out(session, league, now)
    _run(session, league, now)
    why = next(a.why for a in session.scalars(select(AlertRow)) if a.roster_id == 1)
    assert "Next on the SF depth chart: Backup Back (available)." in why


def test_missing_projections_and_chart_leave_those_sentences_out(session: Session) -> None:
    league = _setup(session)
    session.query(PlayerProjectionRow).delete()
    session.commit()
    now = utcnow()
    _healthy_first_then_out(session, league, now)
    _run(session, league, now)
    why = next(a.why for a in session.scalars(select(AlertRow)) if a.roster_id == 1)
    assert (
        why == "Hurt Back was ruled out with a hamstring injury. He starts at RB for you in week 7."
    )


def test_no_healthy_bench_player_who_fits_is_said_plainly(session: Session) -> None:
    league = _setup(session)
    roster = session.get(RosterRow, ("L1", 1))
    assert roster is not None
    roster.players = ["hurt", "wr"]  # no back on the bench
    session.commit()
    now = utcnow()
    _healthy_first_then_out(session, league, now)
    _run(session, league, now)
    why = next(a.why for a in session.scalars(select(AlertRow)) if a.roster_id == 1)
    assert "Nobody on your bench fits that slot." in why


def test_only_out_counts_and_a_player_nobody_owns_alerts_nobody(session: Session) -> None:
    league = _setup(session)
    session.add(_player("doubt", "WR", "Doubtful Receiver"))
    session.add(_player("free", "RB", "Free Agent Back"))
    session.commit()
    now = utcnow()
    run_all_leagues(session, now - timedelta(days=1), {}, now - timedelta(hours=1))  # record health
    for pid, status in (("doubt", "Doubtful"), ("free", "Out")):
        player = session.get(PlayerRow, pid)
        assert player is not None
        player.injury_status = status
    hurt = session.get(PlayerRow, "hurt")
    assert hurt is not None
    hurt.injury_status = None
    session.commit()
    run_all_leagues(session, now - timedelta(days=1), {}, now - timedelta(minutes=30))
    assert _run(session, league, now) == 0  # Doubtful is not Out; "free" is on no roster


def test_a_second_ruling_after_returning_alerts_again_and_an_old_one_does_not(
    session: Session,
) -> None:
    league = _setup(session)
    now = utcnow()
    _healthy_first_then_out(session, league, now)
    _run(session, league, now)
    hurt = session.get(PlayerRow, "hurt")
    assert hurt is not None
    # an old ruling (three days ago) is no longer news
    later = now + timedelta(days=3)
    league.last_viewed_at = later  # the league is still being viewed three days on
    session.commit()
    assert _run(session, league, later) == 0
    # he returns, then is ruled out again: a new occurrence, a new alert for each team
    hurt.injury_status = None
    session.commit()
    run_all_leagues(session, later - timedelta(days=1), {}, later)
    hurt.injury_status = "Out"
    session.commit()
    assert _run(session, league, later + timedelta(minutes=5)) == 3


def test_registered_with_the_engine() -> None:
    assert alerts.DETECTORS["injury_out"] is alert_injury.detect_ruled_out
    assert alerts.PRE_RUN["injury_status"] is alert_injury.track_injuries
