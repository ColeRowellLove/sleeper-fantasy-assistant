"""A player's projection updated while his game is played.

At kickoff the live projection equals the pre-game projection; when the game ends it equals what
he actually scored; in between it is what he has scored so far plus what is still expected from
the rest of the game, which is the pre-game projection scaled by the share of the game left.

Scoring is linear in the stats, so scaling the projected points by the share left is the same as
scaling each projected stat. This first version does not adjust for how the game is going (a
receiver with ten first-half targets), because early in a game a few plays say very little; that
adjustment is left for when there is enough stored history to tune it on.
"""

from __future__ import annotations


def live_projection(
    pregame: float, actual: float | None, state: str | None, elapsed: float | None
) -> float:
    """Projected final points now, from the pre-game projection, points so far and the game clock.

    ``state`` is upcoming, live, final or bye; ``elapsed`` is the share of the game played, 0 to 1,
    or None when the clock is unknown (then a live game is never projected below what he has).
    """
    scored = actual or 0.0
    if state == "final":
        return round(scored, 2)
    if state == "bye":
        return 0.0
    if state == "live":
        if elapsed is None:
            return round(max(scored, pregame), 2)
        remaining = max(0.0, 1.0 - min(1.0, elapsed))
        return round(max(scored, scored + pregame * remaining), 2)
    # not started, or no schedule data: a player who already has points is not waiting to play
    return round(max(scored, pregame), 2) if scored > 0 else round(pregame, 2)
