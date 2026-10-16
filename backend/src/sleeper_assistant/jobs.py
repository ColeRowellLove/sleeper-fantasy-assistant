"""Postgres-backed job queue: enqueue, claim, complete, retry with backoff."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sleeper_assistant.db import JobRow, utcnow

ACTIVE_STATUSES = ("queued", "running")
BACKOFF_BASE_SECONDS = 30
STALE_AFTER = timedelta(minutes=10)


def enqueue(  # noqa: PLR0913
    session: Session,
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    run_at: datetime | None = None,
    dedupe_key: str | None = None,
    max_attempts: int = 3,
) -> JobRow | None:
    """Add a job; returns None if ``dedupe_key`` matches a queued or running job."""
    if dedupe_key is not None:
        pending = session.scalar(
            select(JobRow.id)
            .where(JobRow.dedupe_key == dedupe_key, JobRow.status.in_(ACTIVE_STATUSES))
            .limit(1)
        )
        if pending is not None:
            return None
    job = JobRow(
        kind=kind,
        payload=payload or {},
        run_at=run_at or utcnow(),
        dedupe_key=dedupe_key,
        max_attempts=max_attempts,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:  # lost a race with a concurrent enqueue of the same dedupe_key
        session.rollback()
        return None
    return job


def claim_next(session: Session, now: datetime | None = None) -> JobRow | None:
    """Atomically claim the oldest due job. Safe with several workers (SKIP LOCKED on Postgres)."""
    now = now or utcnow()
    job = session.scalar(
        select(JobRow)
        .where(JobRow.status == "queued", JobRow.run_at <= now)
        .order_by(JobRow.run_at, JobRow.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        session.rollback()
        return None
    job.status = "running"
    job.attempts += 1
    job.locked_at = now
    session.commit()
    return job


def complete(session: Session, job: JobRow, now: datetime | None = None) -> None:
    job.status = "done"
    job.finished_at = now or utcnow()
    job.last_error = None
    session.commit()


def fail(session: Session, job: JobRow, error: str, now: datetime | None = None) -> None:
    """Retry with exponential backoff until max_attempts, then mark failed."""
    now = now or utcnow()
    job.last_error = error[:2000]
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        job.finished_at = now
    else:
        job.status = "queued"
        job.run_at = now + timedelta(seconds=BACKOFF_BASE_SECONDS * 2 ** (job.attempts - 1))
    job.locked_at = None
    session.commit()


def heartbeat(session: Session, job_id: int, now: datetime | None = None) -> None:
    """Mark a running job as still alive so it is not requeued as stale."""
    session.execute(
        update(JobRow)
        .where(JobRow.id == job_id, JobRow.status == "running")
        .values(locked_at=now or utcnow())
    )
    session.commit()


def forget_failed(session: Session) -> int:
    """Delete the jobs recorded as failed, so their failure cooldowns end and the next batch
    retries those syncs at once (after the cause, such as a missing migration, is fixed)."""
    result = session.execute(delete(JobRow).where(JobRow.status == "failed"))
    session.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def requeue_stale(session: Session, now: datetime | None = None) -> int:
    """Return jobs from a crashed worker to the queue. Returns how many were recovered."""
    now = now or utcnow()
    result = session.execute(
        update(JobRow)
        .where(JobRow.status == "running", JobRow.locked_at < now - STALE_AFTER)
        .values(status="queued", locked_at=None)
    )
    session.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
