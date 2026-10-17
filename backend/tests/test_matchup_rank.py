"""Defense rank against each position, from completed games and the league's own scoring."""

from sqlalchemy.orm import Session

from sleeper_assistant.core.nfl.matchup_rank import build_defense_table, matchup_rank
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.views.dashboard import build_dashboard
from sleeper_assistant.views.lineups import build_lineups
from sleeper_assistant.views.player_detail import build_player_detail

SCORING = {"rec": 1.0, "rec_yd": 0.1, "rush_yd": 0.1}


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
            _game("g2", 1, "CCC", "DDD"),
            _game("g3", 2, "AAA", "CCC", status="pre_game"),  # not played: ignored
            _player("rb_b", "RB", "BBB"),  # BBB's back plays at AAA
            _player("rb_d", "RB", "DDD"),  # DDD's back plays at CCC
            _player("def_b", "DEF", "BBB"),  # defenses are not ranked
            _player("wr_a", "WR", "AAA"),  # these two make AAA's and CCC's games count too
            _player("wr_c", "WR", "CCC"),
            _stats(1, "wr_a", "AAA", {"gp": 1}),
            _stats(1, "wr_c", "CCC", {"gp": 1}),
            _stats(1, "rb_b", "BBB", {"gp": 1, "rush_yd": 100.0}),  # 10 against AAA
            _stats(1, "rb_d", "DDD", {"gp": 1, "rush_yd": 50.0}),  # 5 against CCC
            _stats(1, "def_b", "BBB", {"gp": 1, "rush_yd": 999.0}),
            _stats(2, "rb_b", "BBB", {"gp": 1, "rush_yd": 500.0}),  # unplayed game: ignored
        ]
    )
    session.commit()


def test_most_points_allowed_ranks_first(session: Session) -> None:
    _setup(session)
    table = build_defense_table(session, "2026", SCORING)
    assert table[("AAA", "RB")].rank == 1
    assert table[("AAA", "RB")].points == 10.0
    assert table[("CCC", "RB")].rank == 2
    assert table[("AAA", "RB")].teams == 4
    assert table[("AAA", "RB")].games == 1


def test_teams_that_allowed_nothing_tie_for_last(session: Session) -> None:
    _setup(session)
    table = build_defense_table(session, "2026", SCORING)
    assert table[("BBB", "RB")].rank == 3 == table[("DDD", "RB")].rank
    assert table[("BBB", "RB")].points == 0.0


def test_defenses_do_not_add_to_the_offense_and_unplayed_games_are_not_counted(
    session: Session,
) -> None:
    _setup(session)
    table = build_defense_table(session, "2026", SCORING)
    assert (
        table[("BBB", "DEF")].points == 10.0
    )  # his 999 rushing yards are a defense's, not counted
    assert table[("AAA", "RB")].points == 10.0  # the 500-yard unplayed week is ignored


def test_uses_the_leagues_scoring(session: Session) -> None:
    _setup(session)
    table = build_defense_table(session, "2026", {"rush_yd": 0.2})
    assert table[("AAA", "RB")].points == 20.0


def test_a_player_who_did_not_play_adds_nothing(session: Session) -> None:
    _setup(session)
    session.add(_stats(1, "rb_b", "BBB", {"gp": 0, "rush_yd": 100.0}))  # replaces nothing: new key
    session.rollback()
    table = build_defense_table(session, "2026", SCORING)
    assert table[("AAA", "RB")].points == 10.0


def test_matchup_rank_lookup(session: Session) -> None:
    _setup(session)
    table = build_defense_table(session, "2026", SCORING)
    found = matchup_rank(table, "RB", "AAA")
    assert found is not None
    assert (found.opponent, found.rank, found.teams, found.points) == ("AAA", 1, 4, 10.0)
    assert matchup_rank(table, "RB", None) is None  # bye week
    assert matchup_rank(table, None, "AAA") is None
    assert matchup_rank(table, "XX", "AAA") is None
    assert matchup_rank(table, "RB", "ZZZ") is None


def test_no_completed_games_gives_an_empty_table(session: Session) -> None:
    session.add(LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=2,
        scoring_settings=SCORING, roster_positions=[], settings={},
    ))  # fmt: skip
    session.commit()
    assert build_defense_table(session, "2026", SCORING) == {}


def test_rank_reaches_roster_lineup_and_player_views(session: Session) -> None:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1,
        scoring_settings=SCORING, roster_positions=["RB"], settings={},
    )  # fmt: skip
    session.add(league)
    _setup(session)
    session.add_all(
        [
            _game("g4", 2, "AAA", "DDD", status="pre_game"),  # DDD's back visits AAA in week 2
            RosterRow(
                league_id="L1", roster_id=1, owner_id=None, players=["rb_d"], starters=["rb_d"],
                reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
            ),
            MatchupRow(
                league_id="L1", week=2, roster_id=1, matchup_id=1, points=0.0,
                starters=["rb_d"], starters_points=[0.0], players=["rb_d"], players_points={},
            ),
        ]
    )  # fmt: skip
    session.commit()

    on_roster = build_dashboard(session, league).rosters[0].players[0]
    assert on_roster.matchup is not None
    assert (on_roster.matchup.opponent, on_roster.matchup.rank) == ("AAA", 1)

    in_lineup = build_lineups(session, league, 2).matchups[0].teams[0].starters[0]
    assert in_lineup.matchup is not None
    assert in_lineup.matchup.rank == 1

    detail = build_player_detail(session, league, "rb_d")
    assert detail is not None
    assert detail.matchup is not None
    assert detail.matchup.opponent == "AAA"


def test_table_is_cached_until_stats_or_games_change(session: Session) -> None:
    _setup(session)
    first = build_defense_table(session, "2026", SCORING)
    assert build_defense_table(session, "2026", SCORING) is first
    session.add(
        _stats(1, "rb_b", "BBB", {"gp": 1, "rush_yd": 1.0})
        if False
        else _game("g9", 3, "AAA", "CCC")
    )
    session.commit()
    assert build_defense_table(session, "2026", SCORING) is not first


def test_a_null_games_played_still_counts_and_unloaded_games_are_not_counted(
    session: Session,
) -> None:
    _setup(session)
    session.add(_player("rb_x", "RB", "BBB"))
    session.add(_stats(1, "rb_x", "BBB", {"gp": None, "rush_yd": 1.0}))  # type: ignore[dict-item]
    session.add(_game("g8", 3, "EEE", "FFF"))  # complete, but no stats loaded yet
    session.commit()
    table = build_defense_table(session, "2026", SCORING)
    assert ("EEE", "RB") not in table  # no stats, so it is not a game that counts
    assert table[("AAA", "RB")].games == 1


def test_a_team_defense_is_ranked_by_the_offense_it_faces(session: Session) -> None:
    _setup(session)
    table = build_defense_table(session, "2026", SCORING)
    # points scored per game by each offense: BBB 10, DDD 5, AAA 0, CCC 0; fewest is rank 1
    assert [table[(t, "DEF")].rank for t in ("AAA", "CCC", "DDD", "BBB")] == [1, 1, 3, 4]
    assert table[("BBB", "DEF")].points == 10.0
    assert table[("BBB", "DEF")].side == "offense"
    assert table[("AAA", "RB")].side == "defense"
    found = matchup_rank(table, "DEF", "BBB")
    assert found is not None
    assert (found.opponent, found.rank, found.teams, found.side) == ("BBB", 4, 4, "offense")
