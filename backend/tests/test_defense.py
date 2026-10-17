"""Team defense projections: points-allowed tiers weighted by probability."""

import math

import pytest

from sleeper_assistant.core.defense import (
    SCORE_SPREAD,
    parse_tier,
    points_allowed_score,
    tier_probability,
)
from sleeper_assistant.core.projections import score_projection, score_stats

# the family league's points-allowed tiers
TIERS = {
    "pts_allow_0": 12.0,
    "pts_allow_1_6": 10.0,
    "pts_allow_7_13": 4.0,
    "pts_allow_14_20": 1.0,
    "pts_allow_21_27": 0.0,
    "pts_allow_28_34": -1.0,
    "pts_allow_35p": -4.0,
}
SCORING = {**TIERS, "sack": 1.0, "int": 3.0, "def_td": 6.0, "ff": 2.0, "fum_rec": 2.0}


def test_tier_keys_parse_into_score_ranges() -> None:
    assert parse_tier("pts_allow_0") == (0, 0.0)
    assert parse_tier("pts_allow_1_6") == (1, 6.0)
    assert parse_tier("pts_allow_28_34") == (28, 34.0)
    assert parse_tier("pts_allow_35p") == (35, math.inf)
    # keys that look similar but are not tiers
    for other in ("pts_allow", "yds_allow_300_349", "pass_td", "pts_allow_x"):
        assert parse_tier(other) is None


def test_the_tiers_always_cover_every_possible_score() -> None:
    for mean in (3.0, 14.0, 20.5, 27.0, 40.0):
        total = sum(
            tier_probability(low, high, mean)
            for low, high in (
                (0, 0),
                (1, 6),
                (7, 13),
                (14, 20),
                (21, 27),
                (28, 34),
                (35, math.inf),
            )
        )
        assert total == pytest.approx(1.0, abs=1e-9)


def test_a_projection_near_a_tier_edge_is_split_between_the_two_tiers() -> None:
    # 20.5 is the exact edge between 14-20 and 21-27, so both are about equally likely
    low = tier_probability(14, 20, 20.5)
    high = tier_probability(21, 27, 20.5)
    assert low == pytest.approx(high, abs=0.12)
    assert 0.2 < low < 0.4 and 0.2 < high < 0.4


def test_a_lower_projected_total_is_worth_more_to_the_defense() -> None:
    scores = [points_allowed_score(mean, SCORING) for mean in (10.0, 17.0, 24.0, 31.0)]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > 3.0 > scores[-1]  # a stingy matchup pays; a shootout costs


def test_the_expected_value_matches_a_hand_calculation() -> None:
    # mean 19.0: only the 14-20 tier (+1) and its neighbours 7-13 (+4) and 21-27 (0) matter much
    expected = sum(
        tier_probability(*parse_tier(key), 19.0) * value  # type: ignore[misc]
        for key, value in TIERS.items()
    )
    assert points_allowed_score(19.0, SCORING) == pytest.approx(expected)
    assert points_allowed_score(19.0, {"sack": 1.0}) == 0.0  # a league without tiers adds nothing


def test_a_defense_projection_replaces_the_all_or_nothing_tier_flag() -> None:
    sleeper_line = {
        "pts_allow": 19.0,
        "pts_allow_14_20": 1.0,  # Sleeper flags only the tier the average lands in
        "sack": 3.0,
        "int": 1.0,
        "def_td": 0.2,
    }
    flagged_only = score_stats(sleeper_line, SCORING)  # what scoring it as a game stat would do
    weighted = score_projection(sleeper_line, SCORING)
    assert flagged_only == 1.0 + 3.0 + 3.0 + 1.2
    non_tier = 3.0 + 3.0 + 1.2
    assert weighted == pytest.approx(non_tier + points_allowed_score(19.0, SCORING), abs=0.01)
    assert weighted != flagged_only


def test_other_players_are_scored_exactly_as_before() -> None:
    receiver = {"rec": 6.0, "rec_yd": 80.0}
    scoring = {"rec": 1.0, "rec_yd": 0.1}
    assert score_projection(receiver, scoring) == score_stats(receiver, scoring) == 14.0


def test_per_point_scoring_of_points_allowed_still_counts() -> None:
    # a league that charges 0.1 per point allowed instead of tiers
    stats = {"pts_allow": 20.0, "pts_allow_14_20": 1.0, "sack": 2.0}
    assert score_projection(stats, {"pts_allow": -0.1, "sack": 1.0}) == 0.0  # 2 sacks - 2.0


def test_spread_is_the_measured_one() -> None:
    assert 8.0 < SCORE_SPREAD < 10.0
