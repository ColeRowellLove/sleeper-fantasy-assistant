"""The Players tab data: trends, weekly stats, and the per-league listing built from them."""

import json
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.core.sources.sleeper import BASE_URL, SleeperClient
from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.sync.player_data import stored_weeks, sync_trending, sync_week_stats
from sleeper_assistant.views.players import build_players

SCORING = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "pass_yd": 0.04, "pass_td": 4.0}


def _client(routes: dict[str, Any]) -> SleeperClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/v1")
        if path in routes:
            return httpx.Response(200, content=json.dumps(routes[path]))
        return httpx.Response(404)

    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)))


def _trending(adds: list[tuple[str, int]], drops: list[tuple[str, int]]) -> SleeperClient:
    def rows(pairs: list[tuple[str, int]]) -> list[dict[str, Any]]:
        return [{"player_id": pid, "count": count} for pid, count in pairs]

    return _client(
        {
            "/players/nfl/trending/add": rows(adds),
            "/players/nfl/trending/drop": rows(drops),
        }
    )


def test_trending_stores_counts_and_leaves_unlisted_ones_empty(session: Session) -> None:
    client = _trending([("1", 500), ("2", 300)], [("2", 40), ("3", 900)])
    assert sync_trending(session, client) == 3
    rows = {r.player_id: (r.adds, r.drops) for r in session.scalars(select(PlayerTrendRow))}
    # a player missing from a list has no number, which is not the same as zero
    assert rows == {"1": (500, None), "2": (300, 40), "3": (None, 900)}


def test_trending_refresh_replaces_the_old_numbers(session: Session) -> None:
    sync_trending(session, _trending([("1", 500)], [("3", 900)]))
    sync_trending(session, _trending([("1", 650), ("4", 20)], []))
    session.expire_all()
    rows = {r.player_id: (r.adds, r.drops) for r in session.scalars(select(PlayerTrendRow))}
    assert rows == {"1": (650, None), "4": (20, None)}  # player 3 dropped off the list


def test_trending_rejects_an_unknown_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        _trending([], []).get_trending("hold")


def _stats_client(by_week: dict[int, list[dict[str, Any]]]) -> SleeperClient:
    return _client({f"/stats/nfl/2026/{w}": rows for w, rows in by_week.items()})


def test_week_stats_are_stored_and_refreshed(session: Session) -> None:
    rows = [
        {"player_id": "1", "team": "LAR", "stats": {"rec": 5, "rec_yd": 80.0, "note": "x"}},
        {"player_id": "2", "team": "SF", "stats": {}},  # nothing recorded: skipped
        {"player_id": None, "team": "SF", "stats": {"rec": 1}},  # not a player: skipped
    ]
    assert sync_week_stats(session, _stats_client({1: rows, 2: rows}), "2026", [1, 2]) == 2
    assert stored_weeks(session, "2026") == {1, 2}

    better = [{"player_id": "1", "team": "LAR", "stats": {"rec": 9, "rec_yd": 120.0}}]
    sync_week_stats(session, _stats_client({1: better}), "2026", [1])
    session.expire_all()
    row = session.get(PlayerWeekStatsRow, ("2026", 1, "1"))
    assert row is not None and row.stats == {"rec": 9.0, "rec_yd": 120.0}


def _player(
    pid: str, name: str, pos: str, team: str = "LAR", injury: str | None = None
) -> PlayerRow:
    return PlayerRow(
        player_id=pid, full_name=name, position=pos, team=team, external_ids={}, injury_status=injury  # noqa: E501
    )  # fmt: skip


def _roster(rid: int, players: list[str]) -> RosterRow:
    return RosterRow(
        league_id="L1", roster_id=rid, owner_id=f"u{rid}", players=players, starters=[],
        reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
    )  # fmt: skip


def _stats(week: int, pid: str, stats: dict[str, float]) -> PlayerWeekStatsRow:
    return PlayerWeekStatsRow(
        season="2026", week=week, player_id=pid, team="LAR", stats=stats, fetched_at=utcnow()
    )  # fmt: skip


@pytest.fixture
def league(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="Family", season="2026", total_rosters=2,
        scoring_settings=SCORING, roster_positions=["WR", "BN"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            _player("1", "Nacua", "WR", injury="Questionable"),
            _player("2", "Free Agent WR", "WR", "SEA"),
            _player("3", "Mahomes", "QB", "KC"),
            _player("4", "Nobody Special", "WR", "NE"),  # no reason to list: not shown
            _player("5", "Old Kicker", "K", "DAL"),  # on a roster, so shown without any stats
            PlayerRow(player_id="6", full_name="No Position", position=None, team="NE", external_ids={}),  # noqa: E501
            _roster(1, ["1", "5", "6"]),
            _roster(2, ["3"]),
            NflGameRow(
                game_id="g1", season="2026", week=2, home="LAR", away="SEA",
                game_date="2026-09-20", status="pre_game",
            ),
            # season totals: Nacua 5+8.0+6 = 19 then 3+4.0 = 7 -> 26; Free Agent 12; Mahomes 20
            _stats(1, "1", {"rec": 5, "rec_yd": 80.0, "rec_td": 1}),
            _stats(2, "1", {"rec": 3, "rec_yd": 40.0}),
            _stats(1, "2", {"rec": 6, "rec_yd": 60.0}),
            _stats(1, "3", {"pass_yd": 250.0, "pass_td": 2}),
            PlayerTrendRow(player_id="2", adds=900, drops=None, fetched_at=utcnow()),
            PlayerProjectionRow(
                season="2026", week=2, player_id="2", team="SEA", stats={"rec": 5.0, "rec_yd": 50.0},  # noqa: E501
                fetched_at=utcnow(),
            ),
        ]
    )  # fmt: skip
    session.commit()
    return league


def test_listing_marks_who_is_available_and_who_owns_everyone_else(
    session: Session, league: LeagueRow
) -> None:
    data = build_players(session, league)
    by_name = {p.name: p for p in data.players}
    assert by_name["Nacua"].owner_roster_id == 1
    assert by_name["Nacua"].owner_team == "Team 1"
    assert by_name["Free Agent WR"].owner_roster_id is None  # available in this league
    assert by_name["Free Agent WR"].owner_team is None
    assert by_name["Mahomes"].owner_roster_id == 2


def test_listing_scores_the_season_with_this_leagues_rules_and_ranks_by_position(
    session: Session, league: LeagueRow
) -> None:
    by_name = {p.name: p for p in build_players(session, league).players}
    assert by_name["Nacua"].total_points == 26.0  # (5+8+6) + (3+4)
    assert by_name["Free Agent WR"].total_points == 12.0
    assert by_name["Nacua"].rank == 1  # first of the receivers
    assert by_name["Free Agent WR"].rank == 2
    assert by_name["Mahomes"].rank == 1  # ranks are within a position
    assert by_name["Old Kicker"].rank is None  # no points yet, so no rank
    assert by_name["Old Kicker"].total_points == 0.0


def test_listing_carries_trends_projection_injury_and_game(
    session: Session, league: LeagueRow
) -> None:
    data = build_players(session, league)
    by_name = {p.name: p for p in data.players}
    free = by_name["Free Agent WR"]
    assert (free.adds, free.drops) == (900, None)
    assert free.projected == 10.0  # 5 rec + 50 yards * 0.1 + nothing else
    assert by_name["Nacua"].adds is None  # not in Sleeper's top 100 either way
    assert by_name["Nacua"].injury is not None
    assert by_name["Nacua"].injury.status == "Questionable"
    assert by_name["Nacua"].game is not None and by_name["Nacua"].game.opponent == "SEA"
    assert data.week == 2
    assert data.trends_updated_at is not None


def test_listing_leaves_out_players_with_no_reason_to_show_them(
    session: Session, league: LeagueRow
) -> None:
    names = {p.name for p in build_players(session, league).players}
    assert "Nobody Special" not in names  # no points, roster, trend or projection
    assert "No Position" not in names  # a roster spot with an unplayable position
    assert "Old Kicker" in names  # rostered, so it is worth seeing


def test_a_player_without_a_name_still_gets_a_readable_one(
    session: Session, league: LeagueRow
) -> None:
    nameless = PlayerRow(player_id="SF", full_name=None, position="DEF", team="SF", external_ids={})
    unknown = PlayerRow(player_id="9999", full_name=None, position="WR", team="NE", external_ids={})
    session.add_all(
        [nameless, unknown, _stats(1, "SF", {"sack": 3.0}), _stats(1, "9999", {"rec": 1})]
    )
    session.commit()
    names = {p.player_id: p.name for p in build_players(session, league).players}
    assert names["SF"] == "SF defense"
    assert names["9999"] == "9999"


def test_listing_is_ordered_by_season_points(session: Session, league: LeagueRow) -> None:
    names = [p.name for p in build_players(session, league).players]
    assert names[:3] == ["Nacua", "Mahomes", "Free Agent WR"]


def test_listing_for_an_empty_database_is_empty(session: Session) -> None:
    empty = LeagueRow(
        league_id="L9", name="Empty", season="2026", total_rosters=0,
        scoring_settings={}, roster_positions=[], settings={},
    )  # fmt: skip
    session.add(empty)
    session.commit()
    data = build_players(session, empty)
    assert data.players == [] and data.week is None and data.trends_updated_at is None


def test_listing_carries_last_weeks_points_for_those_who_played(
    session: Session, league: LeagueRow
) -> None:
    by_name = {p.name: p for p in build_players(session, league).players}
    assert by_name["Nacua"].last_points == 19.0  # week 1 of the current week 2: 5 + 8 + 6
    assert by_name["Free Agent WR"].last_points == 12.0
    assert by_name["Old Kicker"].last_points is None  # no game, so nothing is claimed
