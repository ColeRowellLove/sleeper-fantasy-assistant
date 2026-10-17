"""Live projections: equal to the pre-game number at kickoff, to the score at the end."""

# ruff: noqa: E501  (fixtures read better on one line)

import pytest
from sqlalchemy.orm import Session

from sleeper_assistant.core.scoring.live_projection import live_projection
from sleeper_assistant.core.scoring.win_probability import (
    StarterState,
    expectation,
    matchup_chances,
)
from sleeper_assistant.core.sources import live
from sleeper_assistant.core.sources.live import LiveGame, fraction_elapsed
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.views.dashboard import build_dashboard
from sleeper_assistant.views.lineups import build_lineups


def test_before_kickoff_it_is_the_pregame_projection() -> None:
    assert live_projection(18.0, 0.0, "upcoming", 0.0) == 18.0
    assert live_projection(18.0, None, "upcoming", None) == 18.0
    assert live_projection(18.0, None, None, None) == 18.0  # no schedule data


def test_when_the_game_is_over_it_is_exactly_the_score() -> None:
    assert live_projection(18.0, 24.6, "final", 1.0) == 24.6
    assert live_projection(18.0, 3.1, "final", 1.0) == 3.1  # a bad game: below the projection
    assert live_projection(18.0, None, "final", 1.0) == 0.0  # no points recorded at all


def test_a_bye_week_is_zero() -> None:
    assert live_projection(0.0, None, "bye", None) == 0.0
    assert (
        live_projection(12.0, None, "bye", None) == 0.0
    )  # a stale projection cannot survive a bye


def test_in_between_it_is_the_score_so_far_plus_the_rest_of_the_projection() -> None:
    # half the game gone, 10 points so far, 18 projected: 10 + 18 * 0.5
    assert live_projection(18.0, 10.0, "live", 0.5) == 19.0
    assert live_projection(18.0, 0.0, "live", 0.0) == 18.0  # at kickoff: the pregame number
    assert live_projection(18.0, 10.0, "live", 1.0) == 10.0  # nothing left to play: the score
    assert live_projection(18.0, 30.0, "live", 0.75) == 34.5  # ahead of pace: keeps what he has


def test_it_never_goes_below_what_a_live_player_has_scored() -> None:
    assert live_projection(-2.0, 8.0, "live", 0.5) == 8.0
    assert live_projection(18.0, 22.0, "live", None) == 22.0  # clock unknown: still never below
    assert live_projection(18.0, 4.0, "live", None) == 18.0  # clock unknown: the pregame number


def test_a_player_with_points_but_no_schedule_is_not_waiting_to_play() -> None:
    assert live_projection(5.0, 12.0, None, None) == 12.0


def _game(state: str, **kw: object) -> LiveGame:
    return LiveGame(week=6, home="DEN", away="SEA", state=state, **kw)  # type: ignore[arg-type]


def test_the_share_of_the_game_played_comes_from_the_quarter_and_clock() -> None:
    assert fraction_elapsed(_game("upcoming")) == 0.0
    assert fraction_elapsed(_game("final")) == 1.0
    assert fraction_elapsed(_game("live", period=1, clock="15:00")) == 0.0
    assert fraction_elapsed(_game("live", period=1, clock="0:00")) == pytest.approx(0.25)
    assert fraction_elapsed(_game("live", period=2, clock="7:30")) == pytest.approx(0.375)
    assert fraction_elapsed(_game("live", period=3, clock="9:25")) == pytest.approx(
        (1800 + 900 - 565) / 3600
    )
    assert fraction_elapsed(_game("live", period=4, clock="0:00")) == 1.0
    assert fraction_elapsed(_game("live", period=2, clock="0:00", detail="Halftime")) == 0.5
    assert (
        fraction_elapsed(_game("live", period=5, clock="5:00")) == 1.0
    )  # overtime: regulation is over


def test_an_unreadable_clock_gives_no_fraction_rather_than_a_guess() -> None:
    assert fraction_elapsed(_game("live")) is None  # no period
    assert fraction_elapsed(_game("live", period=2)) is None  # no clock
    assert fraction_elapsed(_game("live", period=2, clock="soon")) is None
    assert fraction_elapsed(_game("live", period=2, clock="x:30")) is None
    assert fraction_elapsed(_game("live", period=2, clock="95:00")) == pytest.approx(
        0.25
    )  # clamped to the quarter


def test_the_win_chance_weighs_what_is_left_by_the_clock() -> None:
    # the same expected lead (20 against 15); the later in the games, the more it is worth
    def pair(elapsed: float) -> tuple[list[StarterState], list[StarterState]]:
        return (
            [StarterState("live", 20.0 * elapsed, 20.0, pregame=20.0, elapsed=elapsed)],
            [StarterState("live", 15.0 * elapsed, 15.0, pregame=15.0, elapsed=elapsed)],
        )

    early_a, early_b = pair(0.25)
    late_a, late_b = pair(0.75)
    assert expectation(early_a).remaining == pytest.approx(0.75)
    assert expectation(late_a).remaining == pytest.approx(0.25)
    early = matchup_chances(early_a, early_b)
    late = matchup_chances(late_a, late_b)
    assert early is not None and late is not None
    assert late[0] > early[0] > 0.5


def _league(session: Session, game_status: str) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="F", season="2026", total_rosters=2, scoring_settings={"rec": 1.0},
        roster_positions=["WR"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            PlayerRow(player_id="a", full_name="A", position="WR", team="DEN", external_ids={}),
            PlayerRow(player_id="b", full_name="B", position="WR", team="KC", external_ids={}),
            NflGameRow(game_id="g1", season="2026", week=6, home="DEN", away="SEA", game_date="2026-10-18", status=game_status),
            NflGameRow(game_id="g2", season="2026", week=6, home="KC", away="LV", game_date="2026-10-18", status="pre_game"),
            PlayerProjectionRow(season="2026", week=6, player_id="a", team="DEN", stats={"rec": 10.0}, fetched_at=utcnow()),
            PlayerProjectionRow(season="2026", week=6, player_id="b", team="KC", stats={"rec": 8.0}, fetched_at=utcnow()),
        ]
    )  # fmt: skip
    for rid, pid in ((1, "a"), (2, "b")):
        session.add(
            RosterRow(
                league_id="L1", roster_id=rid, owner_id=f"u{rid}", players=[pid], starters=[pid],
                reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
            )
        )  # fmt: skip
        session.add(
            MatchupRow(
                league_id="L1", week=6, roster_id=rid, matchup_id=1, points=0, starters=[pid],
                starters_points=[0.0], players=[pid], players_points={pid: 0.0},
            )
        )  # fmt: skip
    session.commit()
    return league


def test_lineups_show_the_live_projection_and_keep_the_frozen_one(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    league = _league(session, "in_game")
    row = session.get(MatchupRow, ("L1", 6, 1))
    assert row is not None
    row.players_points = {"a": 4.0}
    row.starters_points = [4.0]
    session.commit()
    monkeypatch.setattr(
        live,
        "FETCHER",
        lambda: [
            LiveGame(
                week=6,
                home="DEN",
                away="SEA",
                state="live",
                period=2,
                clock="0:00",
                detail="Halftime",
                home_score=7,
                away_score=3,
            )
        ],
    )
    team = build_lineups(session, league, week=6).matchups[0].teams[0]
    player = team.starters[0]
    assert player.projected_pregame == 10.0  # frozen at kickoff
    assert player.projected == 4.0 + 10.0 * 0.5  # points so far plus half the projection
    assert team.projected == 9.0 and team.projected_pregame == 10.0


def test_once_the_game_is_over_the_projection_equals_the_score(session: Session) -> None:
    league = _league(session, "complete")
    row = session.get(MatchupRow, ("L1", 6, 1))
    assert row is not None
    row.players_points = {"a": 13.0}
    row.starters_points = [13.0]
    row.points = 13.0
    session.commit()
    team = build_lineups(session, league, week=6).matchups[0].teams[0]
    assert team.starters[0].projected == 13.0 and team.starters[0].projected_pregame == 10.0
    assert team.projected == 13.0  # the team total follows
    assert team.projected_pregame == 10.0  # the frozen total is still there to compare with


def test_rosters_follow_the_same_rule(session: Session) -> None:
    league = _league(session, "complete")
    row = session.get(MatchupRow, ("L1", 6, 1))
    assert row is not None
    row.players_points = {"a": 13.0}
    session.commit()
    player = build_dashboard(session, league).rosters[0].players[0]
    assert (player.points, player.projected, player.projected_pregame) == (13.0, 13.0, 10.0)
    waiting = build_dashboard(session, league).rosters[1].players[0]  # KC has not played
    assert (waiting.points, waiting.projected, waiting.projected_pregame) == (None, 8.0, 8.0)
