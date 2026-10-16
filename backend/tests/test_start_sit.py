"""Start/Sit: compare players for a spot, and the projected-best lineup for a roster."""

from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.start_sit import best_lineup, compare_players

SCORING = {"rush_yd": 0.1, "rec_yd": 0.1, "pass_yd": 0.04}


def _player(pid: str, pos: str, injury: str | None = None, team: str = "AAA") -> PlayerRow:
    return PlayerRow(
        player_id=pid, full_name=pid.upper(), position=pos, team=team, injury_status=injury,
        external_ids={},
    )  # fmt: skip


def _proj(pid: str, stats: dict[str, float], team: str = "AAA") -> PlayerProjectionRow:
    return PlayerProjectionRow(
        season="2026", week=2, player_id=pid, team=team, stats=stats, fetched_at=utcnow()
    )


def _form(pid: str, stats: dict[str, float]) -> PlayerWeekStatsRow:
    return PlayerWeekStatsRow(
        season="2026", week=1, player_id=pid, team="AAA", stats=stats, fetched_at=utcnow()
    )


def _setup(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1, scoring_settings=SCORING,
        roster_positions=["RB", "RB", "WR", "FLEX", "BN"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            NflGameRow(game_id="g1", season="2026", week=1, home="AAA", away="BBB",
                       game_date="2026-09-13", status="complete"),
            NflGameRow(game_id="g2", season="2026", week=2, home="AAA", away="BBB",
                       game_date="2026-09-20", status="pre_game"),
            _player("r1", "RB"), _player("r2", "RB"), _player("r3", "RB"), _player("r4", "RB"),
            _player("w1", "WR"), _player("w2", "WR"), _player("hurt", "RB", injury="Out"),
            _player("ir", "RB"), _player("nobody", "RB"),
            RosterRow(
                league_id="L1", roster_id=1, owner_id=None,
                players=["r1", "r2", "r3", "r4", "w1", "w2", "hurt", "ir", "nobody"],
                starters=["r3", "r4", "w2", "r2"], reserve=["ir"], taxi=[],
                wins=0, losses=0, ties=0, points_for=0, points_against=0,
            ),
            _proj("r1", {"rush_yd": 150.0}), _proj("r2", {"rush_yd": 100.0}),
            _proj("r3", {"rush_yd": 60.0}), _proj("r4", {"rush_yd": 90.0}),
            _proj("w1", {"rec_yd": 120.0}), _proj("w2", {"rec_yd": 50.0}),
            _proj("hurt", {"rush_yd": 200.0}), _proj("ir", {"rush_yd": 250.0}),
            _form("r1", {"gp": 1, "rush_yd": 140.0}), _form("r2", {"gp": 1, "rush_yd": 100.0}),
            _form("r3", {"gp": 1, "rush_yd": 40.0}), _form("r4", {"gp": 1, "rush_yd": 100.0}),
        ]
    )  # fmt: skip
    session.commit()
    return league


def test_the_better_projected_and_hotter_player_is_recommended_with_the_numbers(
    session: Session,
) -> None:
    result = compare_players(session, _setup(session), ["r3", "r1"])
    assert result.start == "r1"
    assert [c.player_id for c in result.candidates] == ["r1", "r3"]
    assert "Start R1: projected 15.0" in result.why
    assert "Over R3 by +9.0 projected points" in result.why
    assert result.close_call is False


def test_near_equal_players_are_called_a_close_call(session: Session) -> None:
    result = compare_players(session, _setup(session), ["r2", "r4"])  # 10.0 and 9.0
    assert result.close_call is True
    assert "close call" in result.why


def test_an_injured_player_is_never_recommended_and_the_reason_is_given(session: Session) -> None:
    result = compare_players(session, _setup(session), ["hurt", "r3"])
    assert result.start == "r3"
    assert next(c for c in result.candidates if c.player_id == "hurt").out == "listed Out"
    assert "HURT (listed Out)" in result.why
    assert result.candidates[-1].player_id == "hurt"  # unusable players sort last


def test_nobody_startable_gives_no_recommendation(session: Session) -> None:
    result = compare_players(session, _setup(session), ["hurt", "nobody"])
    assert result.start is None
    assert "None of these players can be started" in result.why
    assert next(c for c in result.candidates if c.player_id == "nobody").out == (
        "no projection this week"
    )


def test_repeated_and_unknown_ids_are_tolerated(session: Session) -> None:
    result = compare_players(session, _setup(session), ["r1", "r1", "zzz"])
    assert [c.player_id for c in result.candidates].count("r1") == 1
    assert result.start == "r1"


def test_the_best_lineup_fills_the_leagues_slots_and_lists_the_swaps(session: Session) -> None:
    result = best_lineup(session, _setup(session), 1)
    assert result is not None
    slots = {s.slot: s.player.player_id if s.player else None for s in result.lineup}
    assert [s.slot for s in result.lineup] == ["RB", "RB", "WR", "FLEX", "BN"][:4]
    assert slots["WR"] == "w1"  # the best receiver
    started = {s.player.player_id for s in result.lineup if s.player}
    assert started == {"r1", "r2", "w1", "r4"}  # not the injured, parked or unprojected players
    assert result.current_projected == (6 + 9 + 5 + 10)
    assert result.projected == (15 + 10 + 12 + 9)
    swaps = {(c.start.player_id, c.sit.player_id) for c in result.changes}
    assert swaps == {("r1", "r3"), ("w1", "w2")}
    assert all(c.gain > 0 for c in result.changes)
    assert "start R1" in result.why or "start W1" in result.why


def test_the_roster_list_carries_every_pickable_player_with_his_numbers(session: Session) -> None:
    result = best_lineup(session, _setup(session), 1)
    assert result is not None
    ids = [c.player_id for c in result.roster]
    assert "r3" in ids and "w2" in ids  # bench players are there to compare
    assert all(c.player_id not in {"parked"} for c in result.roster)  # nobody on IR or taxi
    positions = [c.position for c in result.roster]
    order = ["QB", "RB", "WR", "TE", "K", "DEF"]
    assert positions == sorted(positions, key=lambda p: order.index(p) if p in order else 99)
    rbs = [c.projected or 0.0 for c in result.roster if c.position == "RB"]
    assert rbs == sorted(rbs, reverse=True)  # best projection first within a position


def test_a_lineup_already_at_its_best_says_so(session: Session) -> None:
    league = _setup(session)
    roster = session.get(RosterRow, ("L1", 1))
    assert roster is not None
    roster.starters = ["r1", "r2", "w1", "r4"]
    session.commit()
    result = best_lineup(session, league, 1)
    assert result is not None
    assert result.changes == []
    assert result.why == "Your current lineup is already the projected best."


def test_an_unknown_team_has_no_lineup(session: Session) -> None:
    assert best_lineup(session, _setup(session), 99) is None
