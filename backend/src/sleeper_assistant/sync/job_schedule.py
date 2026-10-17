"""When each recurring job is due: intervals, cooldowns and the enqueue checks the cron runs."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from sleeper_assistant.core.live_window import live_window_open
from sleeper_assistant.db import (
    JobRow,
    LeagueRow,
    as_utc,
    utcnow,
)
from sleeper_assistant.sync import jobs

ACTIVE_WINDOW = timedelta(days=14)  # leagues viewed within this window sync on schedule
SYNC_INTERVAL = timedelta(minutes=15)
PLAYER_SYNC_INTERVAL = timedelta(
    hours=1
)  # injury designations change during the week and on game days
PLAYER_SYNC_FAILURE_COOLDOWN = timedelta(hours=6)  # do not hammer a failing /players endpoint
SCHEDULE_SYNC_INTERVAL = timedelta(minutes=10)
SCHEDULE_FAILURE_COOLDOWN = timedelta(minutes=30)
SCHEDULE_SYNC_INTERVAL_LIVE = timedelta(minutes=3)  # game states and scores, while a game is on
PROJECTION_SYNC_INTERVAL = timedelta(hours=3)  # projections move with injuries and depth charts
PROJECTION_FAILURE_COOLDOWN = timedelta(hours=3)
TRENDING_SYNC_INTERVAL = timedelta(hours=1)  # Sleeper's add/drop counts move all day
TRENDING_FAILURE_COOLDOWN = timedelta(hours=1)
STATS_SYNC_INTERVAL = timedelta(hours=1)  # the current week's stats grow during games
STATS_FAILURE_COOLDOWN = timedelta(hours=3)
STATS_SYNC_INTERVAL_LIVE = timedelta(minutes=2)  # stat lines grow play by play while a game is on
STATS_FAILURE_COOLDOWN_LIVE = timedelta(minutes=5)  # back off a little if the source fails
HISTORY_SYNC_INTERVAL = timedelta(days=7)  # past seasons never change; this only fills gaps
HISTORY_FAILURE_COOLDOWN = timedelta(hours=12)
HISTORY_SEASONS = 2  # how many finished seasons the player pop-up shows
OWNERSHIP_SYNC_INTERVAL = timedelta(hours=3)  # ESPN's percentages move slowly
OWNERSHIP_FAILURE_COOLDOWN = timedelta(hours=3)
DEPTH_SYNC_INTERVAL = timedelta(hours=3)  # depth charts change with injuries and news
DEPTH_FAILURE_COOLDOWN = timedelta(hours=3)
NEWS_SYNC_INTERVAL = timedelta(minutes=30)  # headlines are only worth having while fresh
NEWS_FAILURE_COOLDOWN = timedelta(minutes=30)
KICKOFF_SYNC_INTERVAL = timedelta(hours=24)  # kickoff times only move for flexed games
KICKOFF_FAILURE_COOLDOWN = timedelta(hours=6)
ALERTS_INTERVAL = timedelta(minutes=10)  # detectors run on whatever the syncs have stored
ALERTS_FAILURE_COOLDOWN = timedelta(minutes=30)


def enqueue_due_syncs(session: Session, now: datetime | None = None) -> int:
    """Enqueue a sync for each active league that has not synced recently. Called by cron."""
    now = now or utcnow()
    stmt = select(LeagueRow).where(LeagueRow.last_viewed_at >= now - ACTIVE_WINDOW)
    count = 0
    for league in session.scalars(stmt):
        last = league.last_synced_at
        if last is not None and as_utc(last) > now - SYNC_INTERVAL:
            continue
        job = jobs.enqueue(
            session,
            "sync_league",
            {"league_id": league.league_id},
            dedupe_key=f"sync_league:{league.league_id}",
        )
        count += job is not None
    return count


def _enqueue_periodic(
    session: Session,
    kind: str,
    interval: timedelta,
    failure_cooldown: timedelta,
    now: datetime | None = None,
) -> bool:
    """Enqueue a recurring job unless one is pending, finished within ``interval``, or failed
    within ``failure_cooldown`` (so a broken source is not hammered every cycle)."""
    now = now or utcnow()
    recent = session.scalar(
        select(JobRow.id)
        .where(
            JobRow.kind == kind,
            or_(
                JobRow.status.in_(jobs.ACTIVE_STATUSES),
                (JobRow.status == "done") & (JobRow.finished_at > now - interval),
                (JobRow.status == "failed") & (JobRow.finished_at > now - failure_cooldown),
            ),
        )
        .limit(1)
    )
    if recent is not None:
        return False
    return jobs.enqueue(session, kind, dedupe_key=kind) is not None


def enqueue_player_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Enqueue the hourly Sleeper player DB sync unless one is pending or finished recently."""
    return _enqueue_periodic(
        session, "sync_players", PLAYER_SYNC_INTERVAL, PLAYER_SYNC_FAILURE_COOLDOWN, now
    )


def enqueue_schedule_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh the NFL schedule (game states): every few minutes while a game is on, else slower."""
    live = live_window_open(session, now=now)
    interval = SCHEDULE_SYNC_INTERVAL_LIVE if live else SCHEDULE_SYNC_INTERVAL
    return _enqueue_periodic(session, "sync_schedule", interval, SCHEDULE_FAILURE_COOLDOWN, now)


def enqueue_projection_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh weekly projections about every few hours."""
    return _enqueue_periodic(
        session,
        "sync_projections",
        PROJECTION_SYNC_INTERVAL,
        PROJECTION_FAILURE_COOLDOWN,
        now,
    )


def enqueue_trending_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh Sleeper's add/drop counts about hourly."""
    return _enqueue_periodic(
        session, "sync_trending", TRENDING_SYNC_INTERVAL, TRENDING_FAILURE_COOLDOWN, now
    )


def enqueue_stats_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh the weekly stat lines: every couple of minutes while a game is on, else hourly."""
    if live_window_open(session, now=now):
        return _enqueue_periodic(
            session, "sync_stats", STATS_SYNC_INTERVAL_LIVE, STATS_FAILURE_COOLDOWN_LIVE, now
        )
    return _enqueue_periodic(
        session, "sync_stats", STATS_SYNC_INTERVAL, STATS_FAILURE_COOLDOWN, now
    )


def enqueue_history_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Fill in past seasons' stat totals (cheap to re-check: seasons already stored are skipped)."""
    return _enqueue_periodic(
        session, "sync_history", HISTORY_SYNC_INTERVAL, HISTORY_FAILURE_COOLDOWN, now
    )


def enqueue_ownership_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh ESPN's owned and started percentages every few hours."""
    return _enqueue_periodic(
        session, "sync_ownership", OWNERSHIP_SYNC_INTERVAL, OWNERSHIP_FAILURE_COOLDOWN, now
    )


def enqueue_depth_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh every team's depth chart every few hours."""
    return _enqueue_periodic(
        session, "sync_depth_charts", DEPTH_SYNC_INTERVAL, DEPTH_FAILURE_COOLDOWN, now
    )


def enqueue_news_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Pull the news feeds every half hour."""
    return _enqueue_periodic(session, "sync_news", NEWS_SYNC_INTERVAL, NEWS_FAILURE_COOLDOWN, now)


def enqueue_alerts_if_due(session: Session, now: datetime | None = None) -> bool:
    """Run the alert detectors for active leagues every few minutes, after their syncs."""
    return _enqueue_periodic(session, "run_alerts", ALERTS_INTERVAL, ALERTS_FAILURE_COOLDOWN, now)


def enqueue_kickoff_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh kickoff times from nflverse about daily."""
    return _enqueue_periodic(
        session, "sync_kickoffs", KICKOFF_SYNC_INTERVAL, KICKOFF_FAILURE_COOLDOWN, now
    )
