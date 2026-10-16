"""Chance to win a fantasy matchup, from each team's projected points.

Each team's final score is treated as a normal distribution around its expected total, so the chance
that team A beats team B is the normal curve evaluated at (expected A - expected B) divided by the
spread of that difference. The spread is the part that has to be assumed, and it is a documented
starting value, not a measured one: a fantasy team's weekly score typically varies by about 20 to
25 points, and the difference of two teams by about 1.4 times that, so 28 points for a lineup of
nine starters, scaled by the square root of the number of starters. It shrinks as games are played,
because points already scored are certain and only what is still to play is uncertain.

The numbers should be checked against real results once a few weeks of projections have been stored
before anything is claimed about their accuracy.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import NamedTuple

BASE_SPREAD = 28.0  # standard deviation of the difference between two nine-starter teams' scores
BASE_STARTERS = 9
FLOOR = 0.01  # never claim certainty: the model is simple
MIN_REMAINING = 0.05  # keep a little uncertainty even when almost everything has been played
ROUGH_SPREAD = 1.25  # extra uncertainty when starters with no projection are filled in


class StarterState(NamedTuple):
    """What the model needs to know about one starter."""

    state: str | None  # upcoming, live, final or bye; None when the schedule is unknown
    actual: float | None
    projected: float | None  # the live projection: the score once final
    pregame: float | None = None  # the projection frozen before kickoff, to weigh what is left
    elapsed: float | None = None  # share of his game played, 0 to 1


class Expectation(NamedTuple):
    total: float  # expected final score
    remaining: float  # share of the projected points still to be played, 0 to 1
    missing: int  # starters still to play with no projection
    starters: int


def _expected(player: StarterState) -> float | None:
    """The player's expected final points, or None when it cannot be known."""
    actual = player.actual or 0.0
    if player.state == "final":
        return actual
    if player.state == "bye":
        return 0.0
    if player.state == "live":
        # stand-in until live projections exist: never below what he has already scored
        return max(actual, player.projected or 0.0)
    # upcoming, or no schedule data: a player who already has points is not waiting to play
    if player.projected is None:
        return actual if actual > 0 else None
    return max(actual, player.projected)


def expectation(starters: Iterable[StarterState], *, fill_missing: bool = False) -> Expectation:
    """The team's expected final score. With ``fill_missing`` a starter with no projection is
    assumed to score what the team's other starters average (a rough estimate, not a fact)."""
    players = list(starters)
    total = 0.0
    missing = 0
    still_to_play = 0.0
    projected_total = 0.0
    known = [e for p in players if (e := _expected(p)) is not None]
    stand_in = sum(known) / len(known) if fill_missing and known else None
    for p in players:
        expected = _expected(p)
        if expected is None:
            missing += 1
            if stand_in is None:
                continue
            expected = stand_in  # a starter still to play: his whole game is left
        total += expected
        planned = (
            p.pregame
            if p.pregame is not None
            else (p.projected if p.projected is not None else expected)
        )
        projected_total += planned
        if p.state not in ("final", "bye"):
            # what is left of his game, by the clock when we have it
            share_left = 1.0 if p.elapsed is None else max(0.0, 1.0 - p.elapsed)
            still_to_play += planned * share_left
    remaining = still_to_play / projected_total if projected_total > 0 else 1.0
    return Expectation(round(total, 2), min(1.0, max(0.0, remaining)), missing, len(players))


def spread(starters: int, remaining: float) -> float:
    """Spread of the final difference: bigger lineups vary more; less left to play varies less."""
    lineup = BASE_SPREAD * math.sqrt(max(starters, 1) / BASE_STARTERS)
    return lineup * math.sqrt(max(remaining, MIN_REMAINING))


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def win_probability(expected_a: float, expected_b: float, sigma: float) -> float:
    """Chance A beats B, kept between the floor and its complement."""
    chance = _phi((expected_a - expected_b) / sigma)
    return min(1.0 - FLOOR, max(FLOOR, chance))


def matchup_chances(
    team_a: Iterable[StarterState],
    team_b: Iterable[StarterState],
    *,
    max_missing: int = 1,
    fill_missing: bool = False,
) -> tuple[float, float] | None:
    """(chance A wins, chance B wins), or None when there is nothing fair to say.

    None when either team has more than ``max_missing`` starters with no projection (so the totals
    would be guesses), when no one has anything to compare, or when every starter on both teams
    is done (the result is known, so the page shows it instead of a percentage).
    """
    a, b = (
        expectation(team_a, fill_missing=fill_missing),
        expectation(team_b, fill_missing=fill_missing),
    )
    if a.starters == 0 or b.starters == 0:
        return None
    if fill_missing and (a.missing == a.starters or b.missing == b.starters):
        return None  # nothing to base a stand-in on
    if a.missing > max_missing or b.missing > max_missing:
        return None
    if a.remaining == 0.0 and b.remaining == 0.0:
        return None  # decided: show the result
    sigma = spread(max(a.starters, b.starters), max(a.remaining, b.remaining))
    if fill_missing and (a.missing or b.missing):
        sigma *= ROUGH_SPREAD  # the totals include guesses, so be less sure
    chance = win_probability(a.total, b.total, sigma)
    return round(chance, 4), round(1.0 - chance, 4)
