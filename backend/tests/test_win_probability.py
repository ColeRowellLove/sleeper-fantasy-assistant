"""Matchup win probability from projected points."""

# ruff: noqa: E501  (projection fixtures read better on one line)

import math

import pytest
from sqlalchemy.orm import Session

from sleeper_assistant.dashboard import build_lineups
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    RosterRow,
    utcnow,
)
from sleeper_assistant.win_probability import (
    BASE_SPREAD,
    FLOOR,
    StarterState,
    expectation,
    matchup_chances,
    spread,
    win_probability,
)


def _team(*projections: float, state: str = "upcoming") -> list[StarterState]:
    return [StarterState(state, 0.0, p) for p in projections]


def test_equal_teams_are_a_coin_flip_and_the_two_chances_add_to_one() -> None:
    chances = matchup_chances(_team(20, 20, 20), _team(20, 20, 20))
    assert chances == (0.5, 0.5)


def test_a_bigger_projected_lead_is_a_bigger_chance_and_is_symmetric() -> None:
    small = matchup_chances(_team(110.0), _team(100.0))
    big = matchup_chances(_team(130.0), _team(100.0))
    assert small is not None and big is not None
    assert 0.5 < small[0] < big[0] < 1.0
    flipped = matchup_chances(_team(100.0), _team(130.0))
    assert flipped is not None
    assert flipped == (big[1], big[0])  # the same game seen from the other side
    assert math.isclose(sum(big), 1.0, abs_tol=1e-4)


def test_the_model_matches_the_documented_numbers() -> None:
    # nine starters: spread 28; a 14 point lead is half a spread -> about 69%
    sigma = spread(9, 1.0)
    assert sigma == pytest.approx(BASE_SPREAD)
    assert win_probability(114.0, 100.0, sigma) == pytest.approx(0.6915, abs=0.001)
    # more starters means more variation, so the same lead is worth less
    assert win_probability(114.0, 100.0, spread(16, 1.0)) < win_probability(114.0, 100.0, sigma)


def test_it_never_claims_certainty() -> None:
    assert win_probability(500.0, 0.0, 28.0) == pytest.approx(1.0 - FLOOR)
    assert win_probability(0.0, 500.0, 28.0) == pytest.approx(FLOOR)


def test_finished_games_use_actual_points_and_byes_score_nothing() -> None:
    team = [
        StarterState("final", 25.4, 18.0),  # played better than projected: actual counts
        StarterState("bye", None, None),  # a bye-week starter is zero, not "missing"
        StarterState("upcoming", 0.0, 12.0),
    ]
    got = expectation(team)
    assert got.total == pytest.approx(25.4 + 0.0 + 12.0)
    assert got.missing == 0 and got.starters == 3
    assert got.remaining == pytest.approx(12.0 / (18.0 + 12.0))  # only the upcoming player is left


def test_a_player_in_a_live_game_is_never_below_what_he_has_scored() -> None:
    assert expectation([StarterState("live", 22.0, 15.0)]).total == 22.0  # already beat it
    assert (
        expectation([StarterState("live", 4.0, 15.0)]).total == 15.0
    )  # still expected to get there


def test_uncertainty_shrinks_as_games_are_played() -> None:
    fresh = expectation(_team(20, 20, 20, 20))
    half = expectation(
        [StarterState("final", 20.0, 20.0)] * 2 + [StarterState("upcoming", 0.0, 20.0)] * 2
    )
    assert fresh.remaining == 1.0 and half.remaining == pytest.approx(0.5)
    assert spread(4, half.remaining) < spread(4, fresh.remaining)
    # the same 10 point lead is more convincing with less left to play
    early = matchup_chances(_team(30, 20), _team(20, 20))
    late = matchup_chances(
        [StarterState("final", 30.0, 30.0), StarterState("upcoming", 0.0, 20.0)],
        [StarterState("final", 20.0, 20.0), StarterState("upcoming", 0.0, 20.0)],
    )
    assert early is not None and late is not None and late[0] > early[0]


def test_no_percentage_when_projections_are_missing() -> None:
    one_missing = [StarterState("upcoming", 0.0, 20.0), StarterState("upcoming", 0.0, None)]
    assert matchup_chances(one_missing, _team(20, 20)) is not None  # one gap is tolerated
    two_missing = [*one_missing, StarterState("upcoming", 0.0, None)]
    assert matchup_chances(two_missing, _team(20, 20)) is None  # too many guesses
    assert matchup_chances(_team(20, 20), two_missing) is None


def test_no_percentage_for_a_decided_matchup_or_an_empty_team() -> None:
    done = [StarterState("final", 30.0, 25.0)]
    assert matchup_chances(done, [StarterState("final", 20.0, 22.0)]) is None  # show the result
    assert matchup_chances([], _team(20)) is None
    assert matchup_chances(_team(20), []) is None


def test_a_starter_with_no_schedule_but_points_is_counted_not_missing() -> None:
    unknown = [StarterState(None, 14.0, None)]
    assert expectation(unknown).missing == 0 and expectation(unknown).total == 14.0
    assert expectation([StarterState(None, None, None)]).missing == 1


SCORING = {"rec": 1.0}


def _player(pid: str, team: str) -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=pid, position="WR", team=team, external_ids={})


def _build(session: Session, projections_b: bool = True, status: str = "pre_game") -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="F", season="2026", total_rosters=2, scoring_settings=SCORING,
        roster_positions=["WR", "WR"], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [_player("a1", "LAR"), _player("a2", "LAR"), _player("b1", "SEA"), _player("b2", "SEA")]
    )
    for rid in (1, 2):
        session.add(
            RosterRow(
                league_id="L1", roster_id=rid, owner_id=f"u{rid}", players=[], starters=[],
                reserve=[], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
            )
        )  # fmt: skip
    session.add_all(
        [
            NflGameRow(
                game_id="g", season="2026", week=6, home="LAR", away="SEA",
                game_date="2026-10-18", status=status,
            ),
            MatchupRow(
                league_id="L1", week=6, roster_id=1, matchup_id=1, points=0, starters=["a1", "a2"],
                starters_points=[0, 0], players=["a1", "a2"], players_points={},
            ),
            MatchupRow(
                league_id="L1", week=6, roster_id=2, matchup_id=1, points=0, starters=["b1", "b2"],
                starters_points=[0, 0], players=["b1", "b2"], players_points={},
            ),
            PlayerProjectionRow(
                season="2026", week=6, player_id="a1", team="LAR", stats={"rec": 8.0}, fetched_at=utcnow()
            ),
            PlayerProjectionRow(
                season="2026", week=6, player_id="a2", team="LAR", stats={"rec": 8.0}, fetched_at=utcnow()
            ),
        ]
    )  # fmt: skip
    if projections_b:
        session.add_all(
            [
                PlayerProjectionRow(
                    season="2026", week=6, player_id="b1", team="SEA", stats={"rec": 4.0}, fetched_at=utcnow()
                ),
                PlayerProjectionRow(
                    season="2026", week=6, player_id="b2", team="SEA", stats={"rec": 4.0}, fetched_at=utcnow()
                ),
            ]
        )  # fmt: skip
    session.commit()
    return league


def test_the_lineups_carry_each_teams_chance_to_win(session: Session) -> None:
    lineups = build_lineups(session, _build(session), week=6)
    a, b = lineups.matchups[0].teams
    assert (a.projected, b.projected) == (16.0, 8.0)
    assert a.win_probability is not None and b.win_probability is not None
    assert a.win_probability > 0.5 > b.win_probability  # the projected favorite
    assert a.win_probability + b.win_probability == pytest.approx(1.0, abs=1e-3)


def test_no_chance_is_shown_when_one_team_has_no_projections(session: Session) -> None:
    lineups = build_lineups(session, _build(session, projections_b=False), week=6)
    a, b = lineups.matchups[0].teams
    assert a.win_probability is None and b.win_probability is None  # two starters with none


def test_a_finished_matchup_shows_no_chance(session: Session) -> None:
    lineups = build_lineups(session, _build(session, status="complete"), week=6)
    a, b = lineups.matchups[0].teams
    assert a.win_probability is None and b.win_probability is None  # the page shows the result


def test_zero_filled_projections_still_count_as_missing_for_the_win_chance(
    session: Session,
) -> None:
    # both of team B's starters have no stored projection: shown as 0.0 but not trusted as data
    lineups = build_lineups(session, _build(session, projections_b=False), week=6)
    a, b = lineups.matchups[0].teams
    assert [p.projected for p in b.starters] == [0.0, 0.0]
    assert all(p.projection_missing for p in b.starters)
    assert a.win_probability is None and b.win_probability is None
