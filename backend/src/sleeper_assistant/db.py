"""Database schema (SQLAlchemy 2.0). Postgres in production; SQLite works for tests.

Every league-scoped table is keyed by ``league_id``. Player-level data is shared across leagues.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./dev.db"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSON,
        list[str]: JSON,
        list[Any]: JSON,
    }


class SleeperUserRow(Base):
    __tablename__ = "sleeper_users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String)


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


class RosterRow(Base):
    __tablename__ = "rosters"

    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.league_id"), primary_key=True)
    roster_id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String)
    players: Mapped[list[str]]
    starters: Mapped[list[str]]
    wins: Mapped[int] = mapped_column(default=0)
    losses: Mapped[int] = mapped_column(default=0)
    ties: Mapped[int] = mapped_column(default=0)
    points_for: Mapped[float] = mapped_column(default=0.0)
    points_against: Mapped[float] = mapped_column(default=0.0)


class MatchupRow(Base):
    __tablename__ = "matchups"

    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.league_id"), primary_key=True)
    week: Mapped[int] = mapped_column(primary_key=True)
    roster_id: Mapped[int] = mapped_column(primary_key=True)
    matchup_id: Mapped[int | None]
    points: Mapped[float] = mapped_column(default=0.0)
    starters: Mapped[list[str]]
    starters_points: Mapped[list[Any]]


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


class PlayerRow(Base):
    """Shared across leagues."""

    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String, index=True)
    position: Mapped[str | None] = mapped_column(String)
    team: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    injury_status: Mapped[str | None] = mapped_column(String)
    external_ids: Mapped[dict[str, Any]]


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


class RawSnapshotRow(Base):
    """Raw source payloads kept for replay, backtests and schema-drift debugging."""

    __tablename__ = "raw_snapshots"
    __table_args__ = (Index("ix_raw_snapshots_source_key", "source", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String)
    key: Mapped[str] = mapped_column(String)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict[str, Any]]


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url())


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
