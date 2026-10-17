"""The shape of an NFL game as the app shows it: state, score, clock, conditions, the ball."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

GameState = Literal["upcoming", "live", "final", "bye"]


class Situation(BaseModel):
    """Who has the ball and where, for a game in progress."""

    possession: str | None = None  # the team code with the ball
    down_distance: str | None = None  # "1st & 10"
    ball_on: str | None = None  # "DEN 35": the yard line and the side of the field
    red_zone: bool = False  # the offense is inside the opponent's 20


class GameConditions(BaseModel):
    """The setting of a game: roof, surface, weather and the betting line, from this team's side."""

    roof: str | None = None  # outdoors, dome, closed or open
    surface: str | None = None
    stadium: str | None = None
    temp: int | None = None  # degrees Fahrenheit
    wind: int | None = None  # miles per hour
    spread: float | None = None  # this team's spread: -3.5 means favoured by 3.5, +3.5 an underdog
    total: float | None = None  # the over/under for the game


class GameInfo(BaseModel):
    """A player's NFL game in a week: upcoming, live, final, or the team is on a bye."""

    state: GameState
    date: str | None = None  # ISO date
    kickoff: str | None = None  # ISO UTC timestamp, once the schedule publishes a time
    team: str | None = None  # the NFL team this game is for
    team_score: int | None = None  # live or final score, from this team's side
    opponent_score: int | None = None
    period_text: str | None = None  # where a live game is: "Q2 2:24", "Halftime"; "Final" when over
    elapsed: float | None = None  # share of the game played, 0 to 1; None when the clock is unknown
    opponent: str | None = None
    home: bool | None = None
    conditions: GameConditions | None = None
    situation: Situation | None = None  # who has the ball and where, while the game is live
