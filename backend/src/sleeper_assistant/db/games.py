"""The NFL schedule."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from sleeper_assistant.db.base import Base, utcnow


class NflGameRow(Base):
    """An NFL game from the schedule; also tells us which teams are on a bye in a given week."""

    __tablename__ = "nfl_games"
    __table_args__ = (Index("ix_nfl_games_season_week", "season", "week"),)

    game_id: Mapped[str] = mapped_column(String, primary_key=True)
    season: Mapped[str] = mapped_column(String)
    week: Mapped[int]
    home: Mapped[str] = mapped_column(String)
    away: Mapped[str] = mapped_column(String)
    game_date: Mapped[str | None] = mapped_column(String)  # ISO date, e.g. 2026-10-18
    status: Mapped[str] = mapped_column(String)  # pre_game, in_game, complete
    kickoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # from nflverse
    home_score: Mapped[int | None]  # final score, from nflverse once the game is over
    away_score: Mapped[int | None]
    # game conditions from the nflverse schedule; all optional (unknown until published)
    roof: Mapped[str | None] = mapped_column(String)  # outdoors, dome, closed, open
    surface: Mapped[str | None] = mapped_column(String)  # grass, fieldturf, ...
    stadium: Mapped[str | None] = mapped_column(String)
    temp: Mapped[int | None]  # degrees Fahrenheit, outdoor games
    wind: Mapped[int | None]  # miles per hour, outdoor games
    spread_line: Mapped[float | None]  # points the home team is favoured by (negative: underdog)
    total_line: Mapped[float | None]  # the over/under
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
