"""Alerts, the job queue, news headlines and raw snapshots of what outside sources sent."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from sleeper_assistant.db.base import Base, utcnow


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


class NewsItemRow(Base):
    """A fantasy-relevant NFL headline from a public feed: title and link only, no article text."""

    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # a hash of the link
    source: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    teams: Mapped[list[str]] = mapped_column(JSON, default=list)  # team codes the headline names
    player_ids: Mapped[list[str]] = mapped_column(JSON, default=list)  # Sleeper ids it names
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)  # injury, depth, trade, waivers


class RawSnapshotRow(Base):
    """Raw source payloads kept for replay, backtests and schema-drift debugging."""

    __tablename__ = "raw_snapshots"
    __table_args__ = (Index("ix_raw_snapshots_source_key", "source", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String)
    key: Mapped[str] = mapped_column(String)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict[str, Any]]
