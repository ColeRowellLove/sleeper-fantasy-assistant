"""Weekly projections: fetching, scoring with league rules, keeping the pre-kickoff number."""

import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from sleeper_assistant.dashboard import build_dashboard, build_lineups
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    RosterRow,
)
from sleeper_assistant.projections import projected_points, score_stats, sync_projections
from sleeper_assistant.sleeper import BASE_URL, SleeperClient

# a receiver's projected line, shaped like Sleeper's response (stat names match league scoring keys)
WR_STATS = {
    "rec": 6.62,
    "rec_yd": 106.78,
    "rec_td": 0.81,
    "rush_yd": 3.06,
    "fum_lost": 0.03,
    "rec_tgt": 9.96,
    "gp": 1.0,
    "pts_ppr": 22.0,
}
SCORING = {
    "rec": 1.0,
    "rec_yd": 0.1,
    "rec_td": 6.0,
    "rush_yd": 0.1,
    "fum_lost": -2.0,
    "rec_fd": 0.5,
}


def _row(pid: str, team: str, stats: dict[str, Any] | None) -> dict[str, Any]:
    return {"player_id": pid, "team": team, "stats": stats}


def _client(rows: list[dict[str, Any]]) -> SleeperClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/projections/nfl/2026/6" in str(request.url)
        return httpx.Response(200, content=json.dumps(rows))

    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)))


def test_score_stats_applies_the_leagues_own_values() -> None:
    # 6.62 rec + 10.678 yds + 4.86 td + 0.306 rush - 0.06 fumbles lost; unscored keys add nothing
    assert score_stats(WR_STATS, SCORING) == 22.4
    assert score_stats({"rec": 5.0}, {}) == 0.0
    assert score_stats({"rec": 5.0}, {"rec": 0.5}) == 2.5  # a half-PPR league


def test_client_keeps_only_players_with_a_projection() -> None:
    client = _client(
        [
            _row("1", "LAR", WR_STATS),
            _row("2", "SF", None),  # no stats at all
            _row("3", "DAL", {"gp": 1.0}),  # stats but no projection
            _row("4", "NE", {"pts_ppr": 5.0, "rec": 3.0, "note": "text"}),  # non-numbers dropped
        ]
    )
    got = client.get_projections("2026", 6)
    assert [p.player_id for p in got] == ["1", "4"]
    assert got[1].stats == {"pts_ppr": 5.0, "rec": 3.0}


def _game(gid: str, home: str, away: str, status: str) -> NflGameRow:
    return NflGameRow(
        game_id=gid, season="2026", week=6, home=home, away=away, game_date="2026-10-18", status=status  # noqa: E501
    )  # fmt: skip


def test_sync_stores_then_refreshes_before_kickoff(session: Session) -> None:
    session.add(_game("g1", "LAR", "SEA", "pre_game"))
    session.commit()
    assert sync_projections(session, _client([_row("1", "LAR", WR_STATS)]), "2026", 6) == 1

    updated = {**WR_STATS, "rec": 8.0}
    assert sync_projections(session, _client([_row("1", "LAR", updated)]), "2026", 6) == 1
    session.expire_all()
    row = session.get(PlayerProjectionRow, ("2026", 6, "1"))
    assert row is not None and row.stats["rec"] == 8.0  # still before kickoff, so it moves


def test_sync_keeps_the_pre_kickoff_projection_once_the_game_has_started(
    session: Session,
) -> None:
    session.add_all([_game("g1", "LAR", "SEA", "pre_game"), _game("g2", "SF", "DAL", "pre_game")])
    session.commit()
    sync_projections(session, _client([_row("1", "LAR", WR_STATS)]), "2026", 6)

    game = session.get(NflGameRow, "g1")
    assert game is not None
    game.status = "in_game"
    session.commit()
    later = {**WR_STATS, "rec": 99.0}
    changed = sync_projections(
        session, _client([_row("1", "LAR", later), _row("9", "SF", WR_STATS)]), "2026", 6
    )

    session.expire_all()
    kept = session.get(PlayerProjectionRow, ("2026", 6, "1"))
    assert kept is not None and kept.stats["rec"] == 6.62  # frozen at kickoff
    assert changed == 1  # only the player on a game that has not started moved
    assert session.get(PlayerProjectionRow, ("2026", 6, "9")) is not None


def test_a_player_first_seen_after_kickoff_is_still_stored(session: Session) -> None:
    session.add(_game("g1", "LAR", "SEA", "complete"))
    session.commit()
    assert sync_projections(session, _client([_row("1", "LAR", WR_STATS)]), "2026", 6) == 1


def test_projected_points_leave_out_players_without_a_projection(session: Session) -> None:
    sync_projections(session, _client([_row("1", "LAR", WR_STATS)]), "2026", 6)
    got = projected_points(session, "2026", 6, SCORING, ["1", "2"])
    assert got == {"1": 22.4}
    assert projected_points(session, "2026", 6, SCORING, []) == {}
    assert projected_points(session, "2026", 5, SCORING, ["1"]) == {}  # another week


def _league_with_projections(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1",
        name="Family",
        season="2026",
        total_rosters=2,
        scoring_settings=SCORING,
        roster_positions=["WR", "WR", "BN"],
        settings={},
    )
    session.add(league)
    session.add_all(
        [
            PlayerRow(player_id="1", full_name="Nacua", position="WR", team="LAR", external_ids={}),
            PlayerRow(player_id="2", full_name="Unknown", position="WR", team="SEA", external_ids={}),  # noqa: E501
            RosterRow(
                league_id="L1", roster_id=1, owner_id="u1", players=["1", "2"], starters=["1", "2"],
                reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
            ),
            RosterRow(
                league_id="L1", roster_id=2, owner_id="u2", players=[], starters=[],
                reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
            ),
            _game("g1", "LAR", "SEA", "pre_game"),
            MatchupRow(
                league_id="L1", week=6, roster_id=1, matchup_id=1, points=0, starters=["1", "2"],
                starters_points=[0, 0], players=["1", "2"], players_points={},
            ),
            MatchupRow(
                league_id="L1", week=6, roster_id=2, matchup_id=1, points=0, starters=[],
                starters_points=[], players=[], players_points={},
            ),
        ]
    )  # fmt: skip
    session.commit()
    sync_projections(session, _client([_row("1", "LAR", WR_STATS)]), "2026", 6)
    return league


def test_lineups_show_projected_points_and_a_team_total(session: Session) -> None:
    league = _league_with_projections(session)
    lineups = build_lineups(session, league, week=6)
    mine, theirs = lineups.matchups[0].teams
    assert [p.projected for p in mine.starters] == [22.4, None]  # no projection is not 0
    assert mine.projected == 22.4  # only the starters that have one are summed
    assert theirs.projected is None  # nobody to project: not a misleading 0


def test_rosters_show_projected_points_for_the_current_week(session: Session) -> None:
    league = _league_with_projections(session)
    dashboard = build_dashboard(session, league)
    assert dashboard.week == 6
    projected = {p.name: p.projected for p in dashboard.rosters[0].players}
    assert projected == {"Nacua": 22.4, "Unknown": None}
