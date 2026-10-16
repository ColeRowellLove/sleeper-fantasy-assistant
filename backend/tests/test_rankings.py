"""Weekly rankings: a consensus of projection, recent form and ESPN start share, per position."""

from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.rankings import build_rankings

SCORING = {"rec": 1.0, "rec_yd": 0.1, "rush_yd": 0.1, "pass_yd": 0.04}


def _player(pid: str, pos: str, team: str = "AAA") -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=pid.upper(), position=pos, team=team, external_ids={})


def _proj(pid: str, week: int, stats: dict[str, float]) -> PlayerProjectionRow:
    return PlayerProjectionRow(
        season="2026", week=week, player_id=pid, team="AAA", stats=stats, fetched_at=utcnow()
    )


def _week(pid: str, week: int, stats: dict[str, float]) -> PlayerWeekStatsRow:
    return PlayerWeekStatsRow(
        season="2026", week=week, player_id=pid, team="AAA", stats=stats, fetched_at=utcnow()
    )


def _setup(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1, scoring_settings=SCORING,
        roster_positions=["RB"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            NflGameRow(game_id="g1", season="2026", week=1, home="AAA", away="BBB",
                       game_date="2026-09-13", status="complete"),
            NflGameRow(game_id="g2", season="2026", week=2, home="AAA", away="BBB",
                       game_date="2026-09-20", status="pre_game"),
            _player("a", "RB"), _player("b", "RB"), _player("c", "RB"), _player("w", "WR"),
            _player("zero", "RB"), _player("qb", "QB"),
            RosterRow(league_id="L1", roster_id=1, owner_id=None, players=["a"], starters=[],
                      reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0,
                      points_against=0),
            # week 2 projections: a 15, b 12, c 10 (RBs), w 11 (WR), qb 20; zero is not ranked
            _proj("a", 2, {"rush_yd": 150.0}), _proj("b", 2, {"rush_yd": 120.0}),
            _proj("c", 2, {"rush_yd": 100.0}), _proj("w", 2, {"rec_yd": 110.0}),
            _proj("qb", 2, {"pass_yd": 500.0}), _proj("zero", 2, {}),
            # form from week 1: c ran best, a worst
            _week("a", 1, {"gp": 1, "rush_yd": 20.0}), _week("b", 1, {"gp": 1, "rush_yd": 60.0}),
            _week("c", 1, {"gp": 1, "rush_yd": 130.0}),
            _week("qb", 1, {"gp": 0}),  # did not play: no form
            PlayerOwnershipRow(player_id="a", owned=99.0, started=90.0, fetched_at=utcnow()),
            PlayerOwnershipRow(player_id="c", owned=50.0, started=20.0, fetched_at=utcnow()),
        ]
    )  # fmt: skip
    session.commit()
    return league


def test_players_are_ranked_per_position_by_the_average_of_the_signals(session: Session) -> None:
    result = build_rankings(session, _setup(session))
    assert result.week == 2 and result.current_week == 2 and result.weeks == [1, 2]
    rbs = [p for p in result.players if p.position == "RB"]
    assert [p.player_id for p in rbs] == ["a", "b", "c"]  # a: proj 1st, form 3rd, start 1st
    a = rbs[0]
    assert a.signal_ranks == {"projection": 1, "form": 3, "start": 1}
    assert (a.sources, a.spread, a.score) == (3, 2, round(5 / 3, 2))
    assert a.projected == 15.0 and a.form == 2.0 and a.started_pct == 90.0
    assert a.owner_roster_id == 1 and a.owner_team == "Team 1"
    b = rbs[1]
    assert b.sources == 2 and set(b.signal_ranks) == {"projection", "form"}  # no ESPN number
    assert "zero" not in {p.player_id for p in result.players}  # nothing projected: not ranked


def test_a_why_line_gives_the_numbers_behind_the_rank(session: Session) -> None:
    result = build_rankings(session, _setup(session))
    a = next(p for p in result.players if p.player_id == "a")
    assert "projected 15.0 (1st RB)" in a.why
    assert "2.0 a game over his last 3" in a.why
    assert "started in 90% of ESPN leagues" in a.why
    qb = next(p for p in result.players if p.player_id == "qb")
    assert qb.sources == 1 and qb.why.startswith("projected 20.0")


def test_flex_ranks_pool_running_backs_receivers_and_tight_ends(session: Session) -> None:
    result = build_rankings(session, _setup(session))
    by_id = {p.player_id: p for p in result.players}
    assert by_id["qb"].flex_rank is None
    assert sorted(by_id[i].flex_rank or 0 for i in ("a", "b", "c", "w")) == [1, 2, 3, 4]
    assert by_id["a"].flex_rank == 1


def test_a_past_week_has_no_start_share_and_form_ignores_later_games(session: Session) -> None:
    session.add(_proj("a", 1, {"rush_yd": 80.0}))
    result = build_rankings(session, _setup(session), week=1)
    assert result.week == 1
    a = next(p for p in result.players if p.player_id == "a")
    assert a.started_pct is None and "start" not in a.signal_ranks  # ESPN's share is current-week
    assert a.form is None  # no game before week 1


def test_an_unknown_week_falls_back_to_the_current_one(session: Session) -> None:
    assert build_rankings(session, _setup(session), week=9).week == 2


def test_no_schedule_gives_an_empty_page(session: Session) -> None:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1, scoring_settings=SCORING,
        roster_positions=[], settings={},
    )  # fmt: skip
    session.add(league)
    session.commit()
    result = build_rankings(session, league)
    assert result.week is None and result.players == []
