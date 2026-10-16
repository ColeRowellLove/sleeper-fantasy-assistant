"""Database schema (SQLAlchemy 2.0). Postgres in production; SQLite works for tests.

Every league-scoped table is keyed by ``league_id``. Player-level data is shared across leagues.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./dev.db"


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes (stored as UTC); Postgres returns aware ones."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
    team_name: Mapped[str | None] = mapped_column(String)  # the name this manager gave their team


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


class PlayerProjectionRow(Base):
    """A player's projected stat line for one week, kept as pulled before the game kicked off."""

    __tablename__ = "player_projections"
    __table_args__ = (Index("ix_player_projections_season_week", "season", "week"),)

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

    season: Mapped[str] = mapped_column(String, primary_key=True)
    week: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    team: Mapped[str | None] = mapped_column(String)
    stats: Mapped[dict[str, float]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertRow(Base):
    """An alert for one team in one league. Created once per event (the dedupe key)."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("league_id", "roster_id", "dedupe_key", name="uq_alerts_event"),
        Index("ix_alerts_team_created", "league_id", "roster_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.league_id"))
    roster_id: Mapped[int]
    kind: Mapped[str] = mapped_column(String)  # injury_out, waiver_targets, ...
    dedupe_key: Mapped[str] = mapped_column(String)  # the same event never alerts a team twice
    player_id: Mapped[str | None] = mapped_column(
        String
    )  # the player it is about, when there is one
    title: Mapped[str] = mapped_column(String)
    why: Mapped[str] = mapped_column(String)  # one line with the numbers behind it
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # structured extras
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRow(Base):
    """Postgres-backed job queue. Workers claim rows with FOR UPDATE SKIP LOCKED."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_run_at", "status", "run_at"),
        # at most one queued/running job per dedupe_key (enforces enqueue dedupe atomically)
        Index(
            "uq_jobs_active_dedupe",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String)
    payload: Mapped[dict[str, Any]]
    status: Mapped[str] = mapped_column(String, default="queued")  # queued/running/done/failed
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    dedupe_key: Mapped[str | None] = mapped_column(String)
    last_error: Mapped[str | None] = mapped_column(String)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


def normalize_url(url: str) -> str:
    """Hosts like Neon hand out postgres:// or postgresql:// URLs; use the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def make_engine(url: str | None = None) -> Engine:
    resolved = normalize_url(url or database_url())
    if resolved.startswith("postgresql"):
        return create_engine(
            resolved,
            pool_pre_ping=True,  # serverless instances freeze; drop dead connections
            pool_size=2,
            max_overflow=2,
            # Neon's pooler (PgBouncer, transaction mode) must not see server-side prepared
            # statements
            connect_args={"prepare_threshold": None},
        )
    return create_engine(resolved)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
