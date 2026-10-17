"""A team defense's projected score: expected value over points-allowed tiers.

Sleeper's projection for a defense includes ``pts_allow``: the points it is projected to give up,
which matches the betting line's implied opponent total (checked for a full week: the two agree
within a point for almost every team). Leagues score points allowed in tiers (0, 1 to 6, 7 to 13,
14 to 20, 21 to 27, 28 to 34, 35 or more), so scoring only the tier that the average lands in
would be wrong near a tier edge: a defense projected to allow 20.5 points is about as likely to
land in the next tier as the one below it.

Instead the opponent's score is modelled as a normal distribution around the projected total and
each tier is given its probability. Over the 2024 and 2025 regular seasons the spread of a team's
actual score around the betting line's implied total was about 8.9 points, which is the value used.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

SCORE_SPREAD = 8.9  # standard deviation of a team's score around its implied total (2024-2025)

_TIER = re.compile(r"^pts_allow_(\d+)(?:_(\d+)|(p))?$")


def parse_tier(key: str) -> tuple[int, float] | None:
    """The score range a key covers: pts_allow_7_13 is (7, 13); pts_allow_35p is (35, inf)."""
    match = _TIER.match(key)
    if match is None:
        return None
    low = int(match.group(1))
    if match.group(3):
        return low, math.inf
    return low, float(match.group(2)) if match.group(2) is not None else float(low)


def _cdf(x: float, mean: float, spread: float) -> float:
    return 0.5 * (1.0 + math.erf((x - mean) / (spread * math.sqrt(2.0))))


def tier_probability(low: int, high: float, mean: float, spread: float = SCORE_SPREAD) -> float:
    """Chance an opponent scoring around ``mean`` finishes with between ``low`` and ``high`` points.

    Scores are whole numbers, so each range is widened by half a point either side. The lowest tier
    takes all the probability below it, so the tiers together cover every possible score.
    """
    upper = 1.0 if math.isinf(high) else _cdf(high + 0.5, mean, spread)
    lower = 0.0 if low <= 0 else _cdf(low - 0.5, mean, spread)
    return max(0.0, upper - lower)


def points_allowed_score(mean: float, scoring: Mapping[str, float]) -> float:
    """Expected fantasy points from a defense's points-allowed tiers, with this league's values."""
    total = 0.0
    for key, value in scoring.items():
        tier = parse_tier(key)
        if tier is not None and value:
            total += tier_probability(tier[0], tier[1], mean) * value
    return total
