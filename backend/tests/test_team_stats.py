"""Team stats per game with league ranks, summed from the stored weekly stat lines."""

from sqlalchemy.orm import Session

from sleeper_assistant.core.team_stats import (
    STATS,
    all_team_stats,
    build_team_stats,
    stats_for_position,
)
from sleeper_assistant.db import NflGameRow, PlayerRow, PlayerWeekStatsRow, utcnow


def _game(gid: str, week: int, home: str, away: str, status: str = "complete") -> NflGameRow:
    return NflGameRow(
        game_id=gid, season="2026", week=week, home=home, away=away,
        game_date="2026-09-13", status=status,
    )  # fmt: skip


def _player(pid: str, pos: str, team: str) -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=pid, position=pos, team=team, external_ids={})


def _stats(week: int, pid: str, team: str, stats: dict[str, float]) -> PlayerWeekStatsRow:
    return PlayerWeekStatsRow(
        season="2026", week=week, player_id=pid, team=team, stats=stats, fetched_at=utcnow()
    )


def _setup(session: Session) -> None:
    session.add_all(
        [
            _game("g1", 1, "AAA", "BBB"),
            _game("g2", 2, "AAA", "BBB", status="in_game"),  # not finished: ignored
            _player("qb_a", "QB", "AAA"),
            _player("rb_a", "RB", "AAA"),
            _player("qb_b", "QB", "BBB"),
            _player("def_a", "DEF", "AAA"),
            _player("def_b", "DEF", "BBB"),
            _stats(1, "qb_a", "AAA", {"pass_yd": 300.0, "pass_td": 2.0, "rush_yd": 10.0}),
            _stats(1, "rb_a", "AAA", {"rush_yd": 90.0, "rush_td": 1.0}),
            _stats(1, "qb_b", "BBB", {"pass_yd": 200.0, "pass_td": 1.0}),
            _stats(1, "def_a", "AAA", {"sack": 4.0, "int": 1.0, "fum_rec": 1.0, "pts_allow": 17.0}),
            _stats(1, "def_b", "BBB", {"sack": 1.0, "pts_allow": 24.0, "yds_allow": 400.0}),
            _stats(2, "qb_a", "AAA", {"pass_yd": 999.0}),  # a game still on: ignored
        ]
    )
    session.commit()


def test_offense_is_summed_over_the_team_and_ranked_most_first(session: Session) -> None:
    _setup(session)
    table = build_team_stats(session, "2026")
    a, b = table["AAA"], table["BBB"]
    assert (a["yards"].value, a["yards"].rank, a["yards"].teams) == (400.0, 1, 2)
    assert (b["yards"].value, b["yards"].rank) == (200.0, 2)
    assert a["rush_yd"].value == 100.0
    assert a["td"].value == 3.0  # 2 passing + 1 rushing
    assert a["yards"].games == 1  # the unfinished game is not counted


def test_defense_stats_come_from_the_defense_and_fewest_allowed_ranks_first(
    session: Session,
) -> None:
    _setup(session)
    table = build_team_stats(session, "2026")
    assert table["AAA"]["pts_allow"].rank == 1  # 17 allowed beats 24
    assert table["BBB"]["pts_allow"].rank == 2
    assert table["AAA"]["sack"].value == 4.0
    assert table["AAA"]["takeaways"].value == 2.0  # an interception and a fumble recovery
    assert table["AAA"]["pass_yd"].value == 300.0  # a defense's empty line adds no offense


def test_stats_for_a_position_and_for_a_team_page(session: Session) -> None:
    _setup(session)
    table = build_team_stats(session, "2026")
    rb = stats_for_position(table, "AAA", "RB")
    assert [s.key for s in rb] == ["yards", "rush_yd", "rush_att", "td", "rush_td"]
    assert stats_for_position(table, "AAA", "XX") == []
    assert stats_for_position(table, None, "RB") == []
    assert stats_for_position(table, "ZZZ", "RB") == []
    keys = [s.key for s in all_team_stats(table, "AAA")]
    assert keys[0] == "yards" and "pts_allow" in keys
    assert all_team_stats(table, "ZZZ") == []


def test_table_is_cached_until_games_or_stats_change(session: Session) -> None:
    _setup(session)
    first = build_team_stats(session, "2026")
    assert build_team_stats(session, "2026") is first
    session.add(_game("g9", 3, "CCC", "DDD"))
    session.commit()
    assert build_team_stats(session, "2026") is not first


def test_kicking_numbers_are_special_teams_stats() -> None:
    special = {s.key for s in STATS if s.side == "special"}
    assert special == {"fga", "fgm", "xpm"}
    assert {s.side for s in STATS} == {"offense", "defense", "special"}
