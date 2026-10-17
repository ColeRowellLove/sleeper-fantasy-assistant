"""Players and what is stored about them: ids, stats, projections, trends, injuries, charts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from sleeper_assistant.db.base import Base, utcnow


class PlayerRow(Base):
    """Shared across leagues."""

    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String, index=True)
    position: Mapped[str | None] = mapped_column(String)
    team: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    injury_status: Mapped[str | None] = mapped_column(String)
    injury_body_part: Mapped[str | None] = mapped_column(String)
    external_ids: Mapped[dict[str, Any]]
    # age, height, weight, college, experience, jersey number and depth chart, as Sleeper sends them
    bio: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CrosswalkRow(Base):
    """Maps a Sleeper player id to the ids other sources use. One row per player."""

    __tablename__ = "player_crosswalk"

    player_id: Mapped[str] = mapped_column(ForeignKey("players.player_id"), primary_key=True)
    gsis_id: Mapped[str | None] = mapped_column(String, index=True)
    espn_id: Mapped[str | None] = mapped_column(String, index=True)
    yahoo_id: Mapped[str | None] = mapped_column(String, index=True)
    sportradar_id: Mapped[str | None] = mapped_column(String, index=True)
    fantasypros_id: Mapped[str | None] = mapped_column(String, index=True)
    fantasycalc_id: Mapped[str | None] = mapped_column(String, index=True)


class PlayerProjectionRow(Base):
    """A player's projected stat line for one week, kept as pulled before the game kicked off."""

    __tablename__ = "player_projections"
    __table_args__ = (
        Index("ix_player_projections_season_week", "season", "week"),
        Index("ix_player_projections_player_season", "player_id", "season"),  # one player's year
    )

    season: Mapped[str] = mapped_column(String, primary_key=True)
    week: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    team: Mapped[str | None] = mapped_column(String)
    stats: Mapped[dict[str, float]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TeamDepthChartRow(Base):
    """One NFL team's depth chart, stored as pulled: group -> slot -> players in depth order."""

    __tablename__ = "team_depth_charts"

    team: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String)  # ESPN, or Sleeper when ESPN had nothing
    chart: Mapped[dict[str, Any]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerOwnershipRow(Base):
    """ESPN-wide percent of leagues that roster and start a player (not Sleeper's numbers)."""

    __tablename__ = "player_ownership"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)  # the Sleeper player id
    owned: Mapped[float | None]
    started: Mapped[float | None]
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerSeasonStatsRow(Base):
    """A player's stat totals for a past season; the weeks are in player_week_stats."""

    __tablename__ = "player_season_stats"

    season: Mapped[str] = mapped_column(String, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    games: Mapped[int]
    stats: Mapped[dict[str, float]] = mapped_column(JSON)
    teams: Mapped[list[str] | None] = mapped_column(JSON)  # teams he played for, in order


class PlayerTrendRow(Base):
    """How many Sleeper leagues added and dropped a player in the last 24 hours (top 100 only)."""

    __tablename__ = "player_trends"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    adds: Mapped[int | None]
    drops: Mapped[int | None]
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerWeekStatsRow(Base):
    """A player's actual stat line for one week, scored per league when needed."""

    __tablename__ = "player_week_stats"
    __table_args__ = (Index("ix_player_week_stats_player_season", "player_id", "season"),)

    season: Mapped[str] = mapped_column(String, primary_key=True)
    week: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    team: Mapped[str | None] = mapped_column(String)
    stats: Mapped[dict[str, float]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerInjuryRow(Base):
    """The last injury status seen for a player, so a change (ruled out) is a real comparison."""

    __tablename__ = "player_injury_status"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str | None] = mapped_column(
        String
    )  # Out, Doubtful, Questionable, ...; None = healthy
    previous: Mapped[str | None] = mapped_column(String)  # the status before the last change
    changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # None = first sight
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
