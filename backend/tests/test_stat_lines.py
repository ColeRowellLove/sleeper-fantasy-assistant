"""The one-line stat summary on roster and matchup rows, from the league's own scoring."""

from sqlalchemy.orm import Session

from sleeper_assistant.dashboard import build_dashboard, build_lineups
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.stat_lines import stat_line, week_stat_lines

SCORING = {
    "pass_yd": 0.04, "pass_td": 4.0, "pass_int": -2.0, "rush_yd": 0.1, "rush_td": 6.0,
    "rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "fum_lost": -2.0, "xpm": 1.0, "sack": 1.0,
    "int": 2.0, "fum_rec": 2.0, "def_td": 6.0,
}  # fmt: skip


def test_a_back_leads_with_rushing_then_receiving() -> None:
    line = stat_line(
        "RB",
        {"rush_att": 18, "rush_yd": 92.0, "rush_td": 1, "rec": 3, "rec_tgt": 4, "rec_yd": 21.0},
        SCORING,
    )
    assert line == "18 car, 92 yds, 1 TD · 3 rec on 4 tgt, 21 yds"


def test_a_quarterback_leads_with_passing_and_a_receiver_with_catches() -> None:
    qb = {
        "pass_cmp": 24,
        "pass_att": 35,
        "pass_yd": 281.0,
        "pass_td": 2,
        "pass_int": 1,
        "rush_att": 3,
        "rush_yd": 12.0,
    }
    assert stat_line("QB", qb, SCORING) == "24/35, 281 yds, 2 TD, 1 INT · 3 car, 12 yds"
    wr = {"rec": 6, "rec_tgt": 9, "rec_yd": 74.0, "rec_td": 1, "fum_lost": 1}
    assert stat_line("WR", wr, SCORING) == "6 rec on 9 tgt, 74 yds, 1 TD · 1 FL"


def test_only_categories_the_league_scores_are_named() -> None:
    line = stat_line("RB", {"rush_att": 10, "rush_yd": 50.0, "rush_td": 1}, {"rec": 1.0})
    assert line == "10 car"  # no yards or touchdowns scoring: just the volume


def test_kickers_and_defenses() -> None:
    assert stat_line("K", {"fgm": 2, "fga": 3, "xpm": 4}, SCORING) == "2/3 FG, 4 XP"
    assert (
        stat_line("DEF", {"sack": 4, "int": 1, "fum_rec": 1, "def_td": 1, "pts_allow": 17}, SCORING)
        == "4 sack, 1 INT, 1 FR, 1 TD, 17 pts allowed"
    )


def test_nothing_to_say_is_none() -> None:
    assert stat_line("RB", {}, SCORING) is None
    assert stat_line("K", {"fga": 0}, SCORING) is None
    assert stat_line(None, {"rec": 2}, SCORING) == "2 rec, 0 yds"  # unknown position: still shown


def _player(pid: str, pos: str, team: str) -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=pid, position=pos, team=team, external_ids={})


def _stats(pid: str, week: int, stats: dict[str, float]) -> PlayerWeekStatsRow:
    return PlayerWeekStatsRow(
        season="2026", week=week, player_id=pid, team="AAA", stats=stats, fetched_at=utcnow()
    )


def _setup(session: Session, status: str) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=1, scoring_settings=SCORING,
        roster_positions=["RB", "WR"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            NflGameRow(game_id="g", season="2026", week=2, home="AAA", away="BBB",
                       game_date="2026-09-20", status=status),
            _player("rb", "RB", "AAA"), _player("wr", "WR", "AAA"), _player("dnp", "WR", "AAA"),
            _stats("rb", 2, {"gp": 1, "rush_att": 18, "rush_yd": 92.0, "rush_td": 1}),
            _stats("wr", 2, {"gp": 1, "rec": 6, "rec_yd": 74.0}),
            _stats("dnp", 2, {"gp": 0}),
            RosterRow(league_id="L1", roster_id=1, owner_id=None, players=["rb", "wr", "dnp"],
                      starters=["rb", "wr"], reserve=[], taxi=[], wins=0, losses=0, ties=0,
                      points_for=0, points_against=0),
            MatchupRow(league_id="L1", week=2, roster_id=1, matchup_id=1, points=0.0,
                       starters=["rb", "wr"], starters_points=[0.0, 0.0],
                       players=["rb", "wr", "dnp"], players_points={}),
        ]
    )  # fmt: skip
    session.commit()
    return league


def test_rows_show_the_summary_once_the_game_is_over_and_live(session: Session) -> None:
    league = _setup(session, "complete")
    lines = {p.player_id: p.stat_line for p in build_dashboard(session, league).rosters[0].players}
    assert lines == {"rb": "18 car, 92 yds, 1 TD", "wr": "6 rec, 74 yds", "dnp": None}
    lineup = build_lineups(session, league, 2).matchups[0].teams[0]
    assert [p.stat_line for p in lineup.starters] == ["18 car, 92 yds, 1 TD", "6 rec, 74 yds"]
    assert [p.stat_line for p in lineup.bench] == [None]  # did not play


def test_nothing_is_shown_before_kickoff(session: Session) -> None:
    league = _setup(session, "pre_game")
    assert all(p.stat_line is None for p in build_dashboard(session, league).rosters[0].players)
    lineup = build_lineups(session, league, 2).matchups[0].teams[0]
    assert all(p.stat_line is None for p in lineup.starters)


def test_week_stat_lines_skips_players_without_stats_or_who_did_not_play(session: Session) -> None:
    _setup(session, "complete")
    got = week_stat_lines(session, "2026", 2, {"rb": "RB", "dnp": "WR", "ghost": "RB"}, SCORING)
    assert got == {"rb": "18 car, 92 yds, 1 TD"}
    assert week_stat_lines(session, "2026", 2, {}, SCORING) == {}
