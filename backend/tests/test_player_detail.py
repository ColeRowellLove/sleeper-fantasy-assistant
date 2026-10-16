"""The player pop-up: bio, season, weekly log, projection, past seasons, and every stat counted."""

import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerSeasonStatsRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.ingest import _bio
from sleeper_assistant.player_data import stored_history_seasons, sync_season_history
from sleeper_assistant.player_detail import build_player_detail, display_stats
from sleeper_assistant.sleeper import BASE_URL, SleeperClient, SleeperPlayer

SCORING = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "rush_yd": 0.1, "pass_yd": 0.04}


def _stats(week: int, pid: str, stats: dict[str, float]) -> PlayerWeekStatsRow:
    return PlayerWeekStatsRow(
        season="2026", week=week, player_id=pid, team="LAR", stats=stats, fetched_at=utcnow()
    )


def _player(
    pid: str, name: str, pos: str, team: str, bio: dict[str, Any] | None = None
) -> PlayerRow:
    return PlayerRow(
        player_id=pid, full_name=name, position=pos, team=team, external_ids={}, bio=bio
    )  # fmt: skip


def _roster(rid: int, players: list[str]) -> RosterRow:
    return RosterRow(
        league_id="L1", roster_id=rid, owner_id=f"u{rid}", players=players, starters=[],
        reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
    )  # fmt: skip


def _setup(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="Family", season="2026", total_rosters=2,
        scoring_settings=SCORING, roster_positions=["WR", "BN"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            _player("1", "Nacua", "WR", "LAR", {"age": 25, "college": "BYU", "height": "74"}),
            _player("2", "Second WR", "WR", "SEA"),
            _player("3", "Third WR", "WR", "SF"),
            _roster(1, ["1"]),
            _roster(2, []),
            NflGameRow(
                game_id="g1", season="2026", week=1, home="LAR", away="SEA",
                game_date="2026-09-13", status="complete",
            ),
            NflGameRow(
                game_id="g2", season="2026", week=2, home="SF", away="LAR",
                game_date="2026-09-20", status="pre_game",
            ),
            # Nacua: week 1 catches, yards, a touchdown AND rushing yards; week 2 less
            _stats(1, "1", {"gp": 1, "rec": 7, "rec_yd": 90.0, "rec_td": 1, "rush_yd": 25.0, "rec_tgt": 10}),  # noqa: E501
            _stats(2, "1", {"gp": 1, "rec": 3, "rec_yd": 30.0}),
            _stats(1, "2", {"gp": 1, "rec": 10, "rec_yd": 100.0}),  # 20 points: ahead of Nacua's week 1  # noqa: E501
            _stats(1, "3", {"gp": 1, "rec": 1}),  # 1 point
            PlayerTrendRow(player_id="1", adds=None, drops=120, fetched_at=utcnow()),
            PlayerProjectionRow(
                season="2026", week=2, player_id="1", team="LAR",
                stats={"rec": 6.0, "rec_yd": 80.0, "rec_td": 0.5, "rec_tgt": 9.0, "gp": 1.0},
                fetched_at=utcnow(),
            ),
        ]
    )  # fmt: skip
    session.commit()
    return league


def test_the_season_counts_every_category_of_points(session: Session) -> None:
    detail = build_player_detail(session, _setup(session), "1")
    assert detail is not None
    # week 1: 7 + 9 + 6 + 2.5 (rushing yards on a receiver) = 24.5; week 2: 3 + 3 = 6
    assert [(w.week, w.points) for w in detail.weeks] == [(1, 24.5), (2, 6.0)]
    assert detail.season.points == 30.5
    assert detail.season.games == 2
    assert detail.season.average == 15.25
    assert detail.weeks[0].stats["rush_yd"] == 25.0  # the rushing yards are visible, not hidden


def test_the_weekly_log_names_the_opponent_and_whether_it_was_home(session: Session) -> None:
    detail = build_player_detail(session, _setup(session), "1")
    assert detail is not None
    assert (detail.weeks[0].opponent, detail.weeks[0].home) == ("SEA", True)
    assert (detail.weeks[1].opponent, detail.weeks[1].home) == ("SF", False)


def test_rank_is_within_position_under_this_leagues_scoring(session: Session) -> None:
    league = _setup(session)
    nacua = build_player_detail(session, league, "1")
    second = build_player_detail(session, league, "2")
    third = build_player_detail(session, league, "3")
    assert nacua is not None and second is not None and third is not None
    # totals: Nacua 30.5, Second WR 20.0, Third WR 1.0
    assert (nacua.season.rank, second.season.rank, third.season.rank) == (1, 2, 3)


def test_projection_shows_the_projected_stat_line(session: Session) -> None:
    detail = build_player_detail(session, _setup(session), "1")
    assert detail is not None and detail.projected is not None
    # the next unplayed week is 2: 6 catches, 8.0 yards points, half a touchdown
    assert detail.projected.week == 2
    assert detail.projected.points == 6.0 + 8.0 + 3.0
    assert detail.projected.stats == {"rec": 6.0, "rec_yd": 80.0, "rec_td": 0.5, "rec_tgt": 9.0}


def test_bio_ownership_and_trend_come_through(session: Session) -> None:
    detail = build_player_detail(session, _setup(session), "1")
    assert detail is not None
    assert detail.bio == {"age": 25, "college": "BYU", "height": "74"}
    assert (detail.owner_roster_id, detail.owner_team) == (1, "Team 1")
    assert (detail.adds, detail.drops) == (None, 120)
    free = build_player_detail(session, _setup_again(session), "2")
    assert free is not None and free.owner_roster_id is None  # available in this league


def _setup_again(session: Session) -> LeagueRow:
    league = session.get(LeagueRow, "L1")
    assert league is not None
    return league


def test_an_unknown_player_has_no_detail(session: Session) -> None:
    assert build_player_detail(session, _setup(session), "nope") is None


def test_a_player_with_no_games_yet_has_an_empty_but_valid_pop_up(session: Session) -> None:
    league = _setup(session)
    session.add(_player("9", "Rookie", "RB", "NE"))
    session.commit()
    detail = build_player_detail(session, league, "9")
    assert detail is not None
    assert detail.weeks == [] and detail.season.rank is None and detail.season.average is None
    assert detail.past_seasons == [] and detail.projected is None


def test_past_seasons_are_scored_and_ranked_with_this_leagues_rules(session: Session) -> None:
    league = _setup(session)
    session.add_all(
        [
            PlayerSeasonStatsRow(season="2025", player_id="1", games=16, stats={"rec": 90, "rec_yd": 1100.0}),  # noqa: E501
            PlayerSeasonStatsRow(season="2025", player_id="2", games=17, stats={"rec": 100, "rec_yd": 1300.0}),  # noqa: E501
            PlayerSeasonStatsRow(season="2024", player_id="1", games=10, stats={"rec": 40, "rush_yd": 100.0}),  # noqa: E501
        ]
    )  # fmt: skip
    session.commit()
    detail = build_player_detail(session, league, "1")
    assert detail is not None
    assert [(s.season, s.games, s.points, s.rank) for s in detail.past_seasons] == [
        ("2025", 16, 200.0, 2),  # 90 + 110, behind the other receiver's 230
        ("2024", 10, 50.0, 1),  # 40 + 10, alone that year
    ]


def test_display_stats_keeps_what_scores_plus_basic_volume() -> None:
    shown = display_stats(
        {"rec": 7.0, "rec_tgt": 10.0, "adp_dd_ppr": 5.0, "rec_fd": 3.0, "rush_yd": 0.0}, SCORING
    )
    assert shown == {"rec": 7.0, "rec_tgt": 10.0}  # unscored extras and zero values are left out


def _history_client(by_week: dict[int, list[dict[str, Any]]]) -> SleeperClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        week = int(path.rsplit("/", 1)[1])
        return httpx.Response(200, content=json.dumps(by_week.get(week, [])))

    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)))


def test_history_sums_the_weeks_and_does_not_keep_them(session: Session) -> None:
    week_rows = {
        1: [{"player_id": "1", "team": "LAR", "stats": {"gp": 1, "rec": 5, "rec_yd": 50.0}}],
        2: [{"player_id": "1", "team": "LAR", "stats": {"gp": 1, "rec": 3, "rec_yd": 30.0}}],
        3: [{"player_id": "1", "team": "LAR", "stats": {"gp": 0, "rec": 0.0}}],  # inactive
    }
    assert sync_season_history(session, _history_client(week_rows), "2025") == 1
    row = session.get(PlayerSeasonStatsRow, ("2025", "1"))
    assert row is not None
    assert row.games == 2  # the inactive week does not count as a game
    assert row.stats["rec"] == 8.0 and row.stats["rec_yd"] == 80.0
    assert session.scalars(select(PlayerWeekStatsRow)).first() is None  # weekly rows not stored
    assert stored_history_seasons(session) == {"2025"}


def test_history_skips_a_season_that_is_already_stored(session: Session) -> None:
    session.add(PlayerSeasonStatsRow(season="2025", player_id="1", games=1, stats={"rec": 1}))
    session.commit()
    assert sync_season_history(session, _history_client({}), "2025") == 0


def test_bio_keeps_only_what_sleeper_has() -> None:
    full = SleeperPlayer(
        player_id="1", age=25, height="74", college="BYU", number=12, depth_chart_order=1
    )
    assert _bio(full) == {
        "age": 25, "height": "74", "college": "BYU", "number": 12, "depth_chart_order": 1,
    }  # fmt: skip
    assert _bio(SleeperPlayer(player_id="2", college="")) is None  # nothing useful: no empty dict
