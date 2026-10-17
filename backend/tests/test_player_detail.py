"""The player pop-up: bio, season, weekly log, projection, past seasons, and every stat counted."""

# ruff: noqa: E501  (fixtures with long rows read better on one line)

import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerSeasonStatsRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.sources.sleeper import BASE_URL, SleeperClient, SleeperPlayer
from sleeper_assistant.sync.ingest import _bio
from sleeper_assistant.sync.player_data import stored_history_seasons, sync_season_history
from sleeper_assistant.views.player_detail import build_player_detail, display_stats

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
            _stats(1, "1", {"gp": 1, "rec": 7, "rec_yd": 90.0, "rec_td": 1, "rush_yd": 25.0, "rec_tgt": 10}),
            _stats(2, "1", {"gp": 1, "rec": 3, "rec_yd": 30.0}),
            _stats(1, "2", {"gp": 1, "rec": 10, "rec_yd": 100.0}),  # 20 points: ahead of Nacua's week 1
            _stats(1, "3", {"gp": 1, "rec": 1}),  # 1 point
            PlayerTrendRow(player_id="1", adds=None, drops=120, fetched_at=utcnow()),
            PlayerOwnershipRow(player_id="1", owned=99.93, started=25.94, fetched_at=utcnow()),
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
    # week 1's game is complete; week 2's has not been played, so it is not final
    assert [w.final for w in detail.weeks] == [True, False]


def test_rank_is_within_position_under_this_leagues_scoring(session: Session) -> None:
    league = _setup(session)
    nacua = build_player_detail(session, league, "1")
    second = build_player_detail(session, league, "2")
    third = build_player_detail(session, league, "3")
    assert nacua is not None and second is not None and third is not None
    # totals: Nacua 30.5, Second WR 20.0, Third WR 1.0
    assert (nacua.season.rank, second.season.rank, third.season.rank) == (1, 2, 3)


def test_each_week_carries_the_projection_that_was_stored_before_kickoff(session: Session) -> None:
    league = _setup(session)
    session.add(
        PlayerProjectionRow(
            season="2026", week=1, player_id="1", team="LAR",
            stats={"rec": 5.0, "rec_yd": 60.0, "rec_td": 0.5, "gp": 1.0}, fetched_at=utcnow(),
        )
    )  # fmt: skip
    session.commit()
    detail = build_player_detail(session, league, "1")
    assert detail is not None
    by_week = {w.week: w.projected for w in detail.weeks}
    assert by_week[1] == 5.0 + 6.0 + 3.0  # projected 14.0 against an actual 24.5
    assert by_week[2] == 6.0 + 8.0 + 3.0  # week 2 was projected in the shared setup
    assert detail.weeks[0].points - (by_week[1] or 0) == 10.5  # a big week: beat the projection


def test_a_week_with_no_stored_projection_shows_none_not_zero(session: Session) -> None:
    league = _setup(session)
    session.add(_stats(3, "1", {"gp": 1, "rec": 2, "rec_yd": 20.0}))  # played, never projected
    session.commit()
    detail = build_player_detail(session, league, "1")
    assert detail is not None
    assert {w.week: w.projected for w in detail.weeks}[3] is None


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
    assert detail.league_id == "L1"
    assert detail.owner_manager == "Team 1"  # no Sleeper user stored: falls back to the team label
    assert (detail.adds, detail.drops) == (None, 120)
    assert (detail.owned_pct, detail.started_pct) == (99.93, 25.94)
    free = build_player_detail(session, _setup_again(session), "2")
    assert free is not None and free.owner_roster_id is None  # available in this league
    assert (free.owned_pct, free.started_pct) == (None, None)  # ESPN has no number: not 0


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
            PlayerSeasonStatsRow(season="2025", player_id="1", games=16, stats={"rec": 90, "rec_yd": 1100.0}),
            PlayerSeasonStatsRow(season="2025", player_id="2", games=17, stats={"rec": 100, "rec_yd": 1300.0}),
            PlayerSeasonStatsRow(season="2024", player_id="1", games=10, stats={"rec": 40, "rush_yd": 100.0}),
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


def test_history_keeps_every_game_and_works_out_totals_and_teams(session: Session) -> None:
    week_rows = {
        1: [{"player_id": "1", "team": "LAR", "stats": {"gp": 1, "rec": 5, "rec_yd": 50.0}}],
        2: [{"player_id": "1", "team": "LAR", "stats": {"gp": 1, "rec": 3, "rec_yd": 30.0}}],
        3: [{"player_id": "1", "team": "LAR", "stats": {"gp": 0, "rec": 0.0}}],  # inactive
        4: [
            {"player_id": "1", "team": "SEA", "stats": {"gp": 1, "rec": 4, "rec_yd": 40.0}}
        ],  # traded
    }
    assert sync_season_history(session, _history_client(week_rows), "2025") == 1
    row = session.get(PlayerSeasonStatsRow, ("2025", "1"))
    assert row is not None
    assert row.games == 3  # the inactive week does not count as a game
    assert row.stats["rec"] == 12.0 and row.stats["rec_yd"] == 120.0
    assert row.teams == ["LAR", "SEA"]  # both teams, in the order he played for them
    games = session.scalars(
        select(PlayerWeekStatsRow).where(PlayerWeekStatsRow.season == "2025")
    ).all()
    assert sorted(g.week for g in games) == [1, 2, 3, 4]  # every game is kept, not only the total
    assert stored_history_seasons(session) == set()  # four weeks is not a whole season yet


def test_a_season_counts_as_stored_only_when_all_its_weeks_are(session: Session) -> None:
    full = {
        w: [{"player_id": "1", "team": "LAR", "stats": {"gp": 1, "rec": 1}}] for w in range(1, 19)
    }
    sync_season_history(session, _history_client(full), "2025")
    assert stored_history_seasons(session) == {"2025"}
    assert sync_season_history(session, _history_client(full), "2025") == 0  # not loaded twice


def test_a_season_that_failed_halfway_is_loaded_again(session: Session) -> None:
    half = {
        w: [{"player_id": "1", "team": "LAR", "stats": {"gp": 1, "rec": 1}}] for w in range(1, 9)
    }
    sync_season_history(session, _history_client(half), "2025")
    full = {
        w: [{"player_id": "1", "team": "LAR", "stats": {"gp": 1, "rec": 1}}] for w in range(1, 19)
    }
    assert sync_season_history(session, _history_client(full), "2025") == 1  # tried again
    row = session.get(PlayerSeasonStatsRow, ("2025", "1"))
    assert row is not None and row.games == 18  # replaced, not doubled


def test_the_pop_up_goes_game_by_game_through_a_past_season_with_teams(session: Session) -> None:
    league = _setup(session)
    session.add_all(
        [
            NflGameRow(game_id="p1", season="2025", week=1, home="LAR", away="SEA", game_date="2025-09-07", status="complete"),
            NflGameRow(game_id="p2", season="2025", week=4, home="SEA", away="DEN", game_date="2025-09-28", status="complete"),
            PlayerWeekStatsRow(season="2025", week=1, player_id="1", team="LAR", stats={"gp": 1, "rec": 5, "rec_yd": 50.0}, fetched_at=utcnow()),
            PlayerWeekStatsRow(season="2025", week=4, player_id="1", team="SEA", stats={"gp": 1, "rec": 4, "rush_yd": 20.0}, fetched_at=utcnow()),
            PlayerSeasonStatsRow(season="2025", player_id="1", games=2, stats={"rec": 9, "rec_yd": 50.0, "rush_yd": 20.0}, teams=["LAR", "SEA"]),
        ]
    )  # fmt: skip
    session.commit()
    detail = build_player_detail(session, league, "1")
    assert detail is not None
    season = detail.past_seasons[0]
    assert season.teams == ["LAR", "SEA"]
    first, second = season.log
    assert (first.week, first.team, first.opponent, first.home) == (1, "LAR", "SEA", True)
    # after the trade the game names the team he was on that week and its opponent
    assert (second.week, second.team, second.opponent, second.home) == (4, "SEA", "DEN", True)
    assert (
        first.points == 5.0 + 5.0 and second.points == 4.0 + 2.0
    )  # every stat counts, rushing too
    assert first.final and second.final  # a past game is over
    assert sum(g.points for g in season.log) == season.points  # the games add up to the season row


def test_a_week_he_did_not_play_is_not_listed_as_a_game(session: Session) -> None:
    league = _setup(session)
    session.add_all(
        [
            PlayerWeekStatsRow(season="2025", week=1, player_id="1", team="LAR", stats={"gp": 1, "rec": 5}, fetched_at=utcnow()),
            PlayerWeekStatsRow(season="2025", week=2, player_id="1", team="LAR", stats={"gp": 0}, fetched_at=utcnow()),
            PlayerSeasonStatsRow(season="2025", player_id="1", games=1, stats={"rec": 5}, teams=["LAR"]),
        ]
    )  # fmt: skip
    session.commit()
    log = build_player_detail(session, league, "1").past_seasons[0].log  # type: ignore[union-attr]
    assert [g.week for g in log] == [1]  # the injured week is simply absent


def test_current_season_weeks_name_the_team_for_each_week(session: Session) -> None:
    league = _setup(session)
    detail = build_player_detail(session, league, "1")
    assert detail is not None
    assert [w.team for w in detail.weeks] == ["LAR", "LAR"]  # recorded with each game


def test_a_past_season_with_no_stored_schedule_still_lists_its_games(session: Session) -> None:
    league = _setup(session)
    session.add_all(
        [
            PlayerWeekStatsRow(season="2024", week=2, player_id="1", team="LAR", stats={"gp": 1, "rec": 3}, fetched_at=utcnow()),
            PlayerSeasonStatsRow(season="2024", player_id="1", games=1, stats={"rec": 3}),
        ]
    )  # fmt: skip
    session.commit()
    season = build_player_detail(session, league, "1").past_seasons[0]  # type: ignore[union-attr]
    assert season.teams == ["LAR"]  # worked out from the games when none was stored
    assert (season.log[0].opponent, season.log[0].home) == (
        None,
        None,
    )  # no schedule: no opponent named


def test_bio_keeps_only_what_sleeper_has() -> None:
    full = SleeperPlayer(
        player_id="1", age=25, height="74", college="BYU", number=12, depth_chart_order=1
    )
    assert _bio(full) == {
        "age": 25, "height": "74", "college": "BYU", "number": 12, "depth_chart_order": 1,
    }  # fmt: skip
    assert _bio(SleeperPlayer(player_id="2", college="")) is None  # nothing useful: no empty dict


def test_each_played_week_has_his_rank_among_players_at_his_position(session: Session) -> None:
    league = _setup(session)
    detail = build_player_detail(session, league, "1")
    assert detail is not None
    # week 1: Nacua 24.5, the second WR 20.0, the third 1.0; week 2: only Nacua played
    assert [(w.week, w.rank) for w in detail.weeks] == [(1, 1), (2, 1)]


def test_the_schedule_lists_every_week_with_the_opponent_and_byes(session: Session) -> None:
    league = _setup(session)
    session.add(
        NflGameRow(
            game_id="g3", season="2026", week=3, home="SEA", away="SF",
            game_date="2026-09-27", status="pre_game",
        )
    )  # fmt: skip
    session.commit()
    detail = build_player_detail(session, league, "1")
    assert detail is not None
    by_week = {s.week: s for s in detail.schedule}
    assert sorted(by_week) == [1, 2, 3]
    assert (by_week[1].opponent, by_week[1].home) == ("SEA", True)
    assert (by_week[2].opponent, by_week[2].home) == ("SF", False)
    assert by_week[3].bye and by_week[3].opponent is None  # LAR does not play in week 3


def test_no_schedule_without_his_teams_games(session: Session) -> None:
    league = _setup(session)
    player = session.get(PlayerRow, "1")
    assert player is not None
    player.team = None
    session.commit()
    detail = build_player_detail(session, league, "1")
    assert detail is not None and detail.schedule == []


def test_his_teams_depth_chart_comes_with_the_detail(session: Session) -> None:
    league = _setup(session)
    detail = build_player_detail(session, league, "1")
    assert detail is not None and detail.depth is not None
    assert detail.depth.team == "LAR"


def test_no_depth_chart_for_a_free_agent_without_a_team(session: Session) -> None:
    league = _setup(session)
    player = session.get(PlayerRow, "1")
    assert player is not None
    player.team = None
    session.commit()
    detail = build_player_detail(session, league, "1")
    assert detail is not None and detail.depth is None
