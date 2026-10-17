"""How a defense ranks against a position, and a player's opponent this week."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DefenseRank(BaseModel):
    """One opponent against one position. Rank 1 is always the best matchup for the player."""

    rank: int
    teams: int  # how many teams are ranked, so "3rd of 32" can be said
    points: float  # fantasy points per game: allowed to the position, or scored by the offense
    games: int  # completed games counted
    # "defense": ranked by points allowed to the position (most first);
    # "offense": a team defense's opponent, ranked by points scored (fewest first)
    side: Literal["defense", "offense"] = "defense"


class MatchupRank(DefenseRank):
    """A player's opponent this week and how that defense ranks against his position."""

    opponent: str
