"""Worker process: runs queued jobs. A cron only enqueues work (see enqueue_due_syncs)."""

from __future__ import annotations

import argparse
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from sleeper_assistant import jobs
from sleeper_assistant.crosswalk import build_crosswalk
from sleeper_assistant.db import (
    JobRow,
    LeagueRow,
    as_utc,
    make_engine,
    make_session_factory,
    utcnow,
)
from sleeper_assistant.ingest import MAX_WEEKS, sync_league, sync_players, sync_schedule
from sleeper_assistant.kickoffs import sync_kickoffs
from sleeper_assistant.projections import sync_projections
from sleeper_assistant.sleeper import SleeperClient

log = logging.getLogger(__name__)

Handler = Callable[[Session, dict[str, Any]], None]

ACTIVE_WINDOW = timedelta(days=14)  # leagues viewed within this window sync on schedule
SYNC_INTERVAL = timedelta(minutes=15)
POLL_SECONDS = 5.0
PLAYER_SYNC_INTERVAL = timedelta(
    hours=1
)  # injury designations change during the week and on game days
PLAYER_SYNC_FAILURE_COOLDOWN = timedelta(hours=6)  # do not hammer a failing /players endpoint
SCHEDULE_SYNC_INTERVAL = timedelta(minutes=10)
SCHEDULE_FAILURE_COOLDOWN = timedelta(minutes=30)
PROJECTION_SYNC_INTERVAL = timedelta(hours=3)  # projections move with injuries and depth charts
PROJECTION_FAILURE_COOLDOWN = timedelta(hours=3)
KICKOFF_SYNC_INTERVAL = timedelta(hours=24)  # kickoff times only move for flexed games
KICKOFF_FAILURE_COOLDOWN = timedelta(hours=6)
CYCLE_MAX_JOBS = 50
CYCLE_BUDGET = timedelta(minutes=10)
HEARTBEAT_SECONDS = jobs.STALE_AFTER.total_seconds() / 4


def default_handlers(
    client: SleeperClient,
    http_factory: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=30.0),
) -> dict[str, Handler]:
    def _sync_league(session: Session, payload: dict[str, Any]) -> None:
        sync_league(session, client, str(payload["league_id"]))

    def _sync_players(session: Session, _payload: dict[str, Any]) -> None:
        sync_players(session, client)
        build_crosswalk(session)

    def _sync_schedule(session: Session, payload: dict[str, Any]) -> None:
        season = str(payload.get("season") or client.get_state().season)
        sync_schedule(session, client, season)

    def _sync_projections(session: Session, payload: dict[str, Any]) -> None:
        state = client.get_state()
        if state.season_type != "regular":
            return  # nothing is projected outside the regular season
        season = str(payload.get("season") or state.season)
        # this week and the next, so the coming week is ready before it starts
        for week in range(state.week, min(state.week + 1, MAX_WEEKS) + 1):
            sync_projections(session, client, season, week)

    def _sync_kickoffs(session: Session, payload: dict[str, Any]) -> None:
        season = str(payload.get("season") or client.get_state().season)
        with http_factory() as http:
            sync_kickoffs(session, http, season)

    return {
        "sync_kickoffs": _sync_kickoffs,
        "sync_projections": _sync_projections,
        "sync_league": _sync_league,
        "sync_players": _sync_players,
        "sync_schedule": _sync_schedule,
    }


class Heartbeat:
    """Refreshes a running job's ``locked_at`` from a background thread (own DB session).

    Keeps a healthy long job from being treated as stale by ``jobs.requeue_stale``.
    """

    def __init__(self, factory: sessionmaker[Session], job_id: int, interval: float) -> None:
        self._factory = factory
        self._job_id = job_id
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"heartbeat-{job_id}", daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                with self._factory() as session:
                    jobs.heartbeat(session, self._job_id)
            except Exception:  # a missed beat must not kill the job; the next one may succeed
                log.exception("heartbeat for job %s failed", self._job_id)

    def __enter__(self) -> Heartbeat:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)  # never let a hung beat block job completion


def run_once(
    factory: sessionmaker[Session],
    handlers: dict[str, Handler],
    now: datetime | None = None,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> bool:
    """Claim and run a single job. Returns False if nothing was due."""
    with factory() as session:
        job = jobs.claim_next(session, now)
        if job is None:
            return False
        handler = handlers.get(job.kind)
        try:
            if handler is None:
                raise LookupError(f"no handler for job kind {job.kind!r}")
            with Heartbeat(factory, job.id, heartbeat_seconds):
                handler(session, job.payload)
        except Exception as exc:  # job failures must never kill the worker
            session.rollback()
            log.exception("job %s (%s) failed", job.id, job.kind)
            jobs.fail(session, job, f"{type(exc).__name__}: {exc}")
        else:
            jobs.complete(session, job)
        return True


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
    """Refresh the NFL schedule (game statuses) about every cycle; it is one small request."""
    return _enqueue_periodic(
        session, "sync_schedule", SCHEDULE_SYNC_INTERVAL, SCHEDULE_FAILURE_COOLDOWN, now
    )


def enqueue_projection_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh weekly projections about every few hours."""
    return _enqueue_periodic(
        session,
        "sync_projections",
        PROJECTION_SYNC_INTERVAL,
        PROJECTION_FAILURE_COOLDOWN,
        now,
    )


def enqueue_kickoff_sync_if_due(session: Session, now: datetime | None = None) -> bool:
    """Refresh kickoff times from nflverse about daily."""
    return _enqueue_periodic(
        session, "sync_kickoffs", KICKOFF_SYNC_INTERVAL, KICKOFF_FAILURE_COOLDOWN, now
    )


@dataclass
class CycleResult:
    enqueued: int
    ran: int


def run_cycle(
    factory: sessionmaker[Session],
    handlers: dict[str, Handler],
    *,
    max_jobs: int = CYCLE_MAX_JOBS,
    budget: timedelta = CYCLE_BUDGET,
) -> CycleResult:
    """One scheduled batch: recover stale jobs, enqueue due work, run jobs within a budget."""
    started = utcnow()
    with factory() as session:
        jobs.requeue_stale(session)
        enqueued = (
            enqueue_due_syncs(session)
            + int(enqueue_player_sync_if_due(session))
            + int(enqueue_schedule_sync_if_due(session))
            + int(enqueue_kickoff_sync_if_due(session))
            + int(enqueue_projection_sync_if_due(session))
        )
    ran = 0
    while ran < max_jobs and utcnow() - started < budget and run_once(factory, handlers):
        ran += 1
    log.info("worker cycle: enqueued %d, ran %d", enqueued, ran)
    return CycleResult(enqueued=enqueued, ran=ran)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - process entry point
    parser = argparse.ArgumentParser(description="Sleeper assistant worker")
    parser.add_argument("--once", action="store_true", help="run one batch and exit (cron mode)")
    args = parser.parse_args(argv)
    if args.once:
        logging.basicConfig(level=logging.INFO)
        factory = make_session_factory(make_engine())
        run_cycle(factory, default_handlers(SleeperClient()))
    else:
        run_forever()


def run_forever() -> None:  # pragma: no cover - process entry point
    logging.basicConfig(level=logging.INFO)
    factory = make_session_factory(make_engine())
    handlers = default_handlers(SleeperClient())
    log.info("worker started")
    while True:
        try:
            with factory() as session:
                jobs.requeue_stale(session)
            idle = not run_once(factory, handlers)
        except Exception:  # e.g. a dropped DB connection: log, back off, keep running
            log.exception("worker loop error")
            idle = True
        if idle:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":  # pragma: no cover
    main()
