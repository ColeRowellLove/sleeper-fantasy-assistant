"""The Games tab data: every game of a week with its players, scored with the league's rules."""

from sqlalchemy.orm import Session

from sleeper_assistant import games_view
from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.games_view import build_games

SCORING = {"rush_yd": 0.1, "rush_td": 6.0, "rec": 1.0, "rec_yd": 0.1}


def _player(pid: str, pos: str, team: str, name: str | None = None) -> PlayerRow:
    return PlayerRow(
        player_id=pid, full_name=name or pid.upper(), position=pos, team=team, external_ids={}
    )  # fmt: skip


def _stats(pid: str, team: str, stats: dict[str, float]) -> PlayerWeekStatsRow:
    return PlayerWeekStatsRow(
        season="2026", week=2, player_id=pid, team=team, stats=stats, fetched_at=utcnow()
    )


def _setup(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=2, scoring_settings=SCORING,
        roster_positions=["RB"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            NflGameRow(game_id="late", season="2026", week=2, home="CCC", away="DDD",
                       game_date="2026-09-20", status="pre_game"),
            NflGameRow(game_id="early", season="2026", week=2, home="AAA", away="BBB",
                       game_date="2026-09-20", status="complete", home_score=24, away_score=17,
                       roof="dome", spread_line=3.5, total_line=44.5),
            NflGameRow(game_id="old", season="2026", week=1, home="AAA", away="CCC",
                       game_date="2026-09-13", status="complete"),
            _player("hrb", "RB", "AAA", "Home Back"), _player("arb", "RB", "BBB", "Away Back"),
            _player("bench", "WR", "AAA", "Quiet Receiver"),  # no stats, not owned: left out
            _player("owned", "WR", "CCC", "Owned Receiver"),  # upcoming game, but rostered
            _player("dnp", "RB", "AAA", "Did Not Play"),
            _player("qbx", "QB", "ZZZ", "Other Game"),
            _stats("hrb", "AAA", {"gp": 1, "rush_yd": 100.0, "rush_td": 1, "rush_att": 20}),
            _stats("arb", "BBB", {"gp": 1, "rush_yd": 30.0}),
            _stats("dnp", "AAA", {"gp": 0}),
            RosterRow(league_id="L1", roster_id=1, owner_id=None, players=["arb", "owned"],
                      starters=[], reserve=[], taxi=[], wins=0, losses=0, ties=0,
                      points_for=0, points_against=0),
        ]
    )  # fmt: skip
    session.commit()
    return league


def test_every_game_of_the_week_in_kickoff_order_with_score_line_and_conditions(
    session: Session,
) -> None:
    result = build_games(session, _setup(session), 2)
    assert result.week == 2 and result.weeks == [1, 2]
    assert [g.game_id for g in result.games] == ["early", "late"]  # no kickoff times: by date, home
    early = next(g for g in result.games if g.game_id == "early")
    assert (early.home, early.away, early.game.state) == ("AAA", "BBB", "final")
    assert (early.game.team_score, early.game.opponent_score) == (24, 17)
    assert early.game.conditions is not None
    assert (early.game.conditions.roof, early.game.conditions.spread) == ("dome", -3.5)
    assert early.game.conditions.total == 44.5


def test_players_are_those_with_stats_or_owned_scored_with_the_leagues_rules(
    session: Session,
) -> None:
    result = build_games(session, _setup(session), 2)
    early = next(g for g in result.games if g.game_id == "early")
    assert [p.name for p in early.players] == ["Away Back", "Home Back"]  # owned first
    away, home = early.players
    assert (away.owner_roster_id, away.owner_team) == (1, "Team 1")
    assert (home.owner_roster_id, home.owner_team) == (None, None)
    assert home.points == 16.0 and home.stat_line == "20 car, 100 yds, 1 TD"
    assert away.points == 3.0
    late = next(g for g in result.games if g.game_id == "late")
    assert [p.name for p in late.players] == ["Owned Receiver"]
    assert late.players[0].points is None and late.players[0].stat_line is None  # not played yet
    everyone = {p.player_id for g in result.games for p in g.players}
    assert everyone.isdisjoint({"bench", "dnp", "qbx"})


def test_default_week_is_the_current_one_and_an_unknown_week_falls_back(session: Session) -> None:
    league = _setup(session)
    assert build_games(session, league).week == 2
    assert build_games(session, league, 9).week == 2
    assert [g.game_id for g in build_games(session, league, 1).games] == ["old"]


def test_no_schedule_gives_an_empty_page(session: Session) -> None:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1, scoring_settings=SCORING,
        roster_positions=[], settings={},
    )  # fmt: skip
    session.add(league)
    session.commit()
    result = build_games(session, league)
    assert result.week is None and result.games == []


def test_the_raw_stat_line_is_carried_for_the_page_to_lay_out(session: Session) -> None:
    result = build_games(session, _setup(session), 2)
    early = next(g for g in result.games if g.game_id == "early")
    back = next(p for p in early.players if p.player_id == "hrb")
    assert back.stats == {"rush_att": 20.0, "rush_yd": 100.0, "rush_td": 1.0}
    assert back.projected is False
    assert "gp" not in back.stats  # only the stats the page shows


def test_before_a_line_exists_the_most_projected_players_show_with_their_projection(
    session: Session,
) -> None:
    league = _setup(session)
    session.add_all(
        [
            PlayerProjectionRow(season="2026", week=2, player_id="owned", team="CCC",
                                stats={"rec": 5.0, "rec_yd": 60.0}, fetched_at=utcnow()),
            _player("proj_wr", "WR", "DDD", "Projected Receiver"),
            PlayerProjectionRow(season="2026", week=2, player_id="proj_wr", team="DDD",
                                stats={"rec_tgt": 8.0, "rec": 6.0, "rec_yd": 80.0},
                                fetched_at=utcnow()),
        ]
    )  # fmt: skip
    session.commit()
    result = build_games(session, league, 2)
    late = next(g for g in result.games if g.game_id == "late")
    by_id = {p.player_id: p for p in late.players}
    assert set(by_id) == {"owned", "proj_wr"}  # projected, not rostered, still shown
    wr = by_id["proj_wr"]
    assert wr.projected is True
    assert wr.stats == {"rec_tgt": 8.0, "rec": 6.0, "rec_yd": 80.0}
    assert wr.points == 14.0  # 6 rec + 8.0 yards points under the league's scoring
    assert by_id["owned"].owner_roster_id == 1


def test_only_the_most_projected_of_a_team_are_added_besides_the_rostered(
    session: Session,
) -> None:
    league = _setup(session)
    for i in range(games_view.PROJECTED_PER_TEAM + 3):
        pid = f"extra{i}"
        session.add(_player(pid, "WR", "DDD"))
        session.add(
            PlayerProjectionRow(season="2026", week=2, player_id=pid, team="DDD",
                                stats={"rec_yd": 10.0 + i}, fetched_at=utcnow())
        )  # fmt: skip
    session.commit()
    late = next(g for g in build_games(session, league, 2).games if g.game_id == "late")
    ddd = [p for p in late.players if p.team == "DDD"]
    assert len(ddd) == games_view.PROJECTED_PER_TEAM
    assert "extra0" not in {p.player_id for p in ddd}  # the least projected were left out
