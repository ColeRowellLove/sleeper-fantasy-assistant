"""Leagues, managers, rosters, matchups and transactions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from sleeper_assistant.db.base import Base


class SleeperUserRow(Base):
    __tablename__ = "sleeper_users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String)
    avatar: Mapped[str | None] = mapped_column(String)  # Sleeper's avatar id


class LeagueRow(Base):
    __tablename__ = "leagues"

    league_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    season: Mapped[str] = mapped_column(String)
    total_rosters: Mapped[int]
    scoring_settings: Mapped[dict[str, Any]]
    roster_positions: Mapped[list[str]]
    settings: Mapped[dict[str, Any]]
    previous_league_id: Mapped[str | None] = mapped_column(String)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserLeagueRow(Base):
    """Which Sleeper users belong to which leagues (many-to-many)."""

    __tablename__ = "user_leagues"

    user_id: Mapped[str] = mapped_column(ForeignKey("sleeper_users.user_id"), primary_key=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.league_id"), primary_key=True)
    team_name: Mapped[str | None] = mapped_column(String)  # the name this manager gave their team
    team_avatar: Mapped[str | None] = mapped_column(String)  # the picture they gave their team


class RosterRow(Base):
    __tablename__ = "rosters"

    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.league_id"), primary_key=True)
    roster_id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String)
    players: Mapped[list[str]]
    starters: Mapped[list[str]]
    reserve: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    taxi: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    wins: Mapped[int] = mapped_column(default=0)
    losses: Mapped[int] = mapped_column(default=0)
    ties: Mapped[int] = mapped_column(default=0)
    points_for: Mapped[float] = mapped_column(default=0.0)
    points_against: Mapped[float] = mapped_column(default=0.0)
    streak: Mapped[str | None] = mapped_column(String)  # current run as Sleeper reports it: 3W, 2L
    potential_points: Mapped[float | None]  # Sleeper's ppts: points the best lineups would score


class MatchupRow(Base):
    __tablename__ = "matchups"

    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.league_id"), primary_key=True)
    week: Mapped[int] = mapped_column(primary_key=True)
    roster_id: Mapped[int] = mapped_column(primary_key=True)
    matchup_id: Mapped[int | None]
    points: Mapped[float] = mapped_column(default=0.0)
    starters: Mapped[list[str]]
    starters_points: Mapped[list[Any]]
    players: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    players_points: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'")
    )


class TransactionRow(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_league_week", "league_id", "week"),)

    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.league_id"), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    week: Mapped[int]
    created_ms: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict[str, Any]]
