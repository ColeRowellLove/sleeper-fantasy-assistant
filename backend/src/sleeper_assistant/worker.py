"""Worker process: runs queued jobs. A cron only enqueues work (see enqueue_due_syncs)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from sleeper_assistant import jobs
from sleeper_assistant.crosswalk import build_crosswalk
from sleeper_assistant.db import LeagueRow, as_utc, make_engine, make_session_factory, utcnow
from sleeper_assistant.ingest import sync_league, sync_players
from sleeper_assistant.sleeper import SleeperClient

log = logging.getLogger(__name__)

Handler = Callable[[Session, dict[str, Any]], None]

ACTIVE_WINDOW = timedelta(days=14)  # leagues viewed within this window sync on schedule
SYNC_INTERVAL = timedelta(minutes=15)
POLL_SECONDS = 5.0
HEARTBEAT_SECONDS = jobs.STALE_AFTER.total_seconds() / 4


def default_handlers(client: SleeperClient) -> dict[str, Handler]:
    def _sync_league(session: Session, payload: dict[str, Any]) -> None:
        sync_league(session, client, str(payload["league_id"]))

    def _sync_players(session: Session, _payload: dict[str, Any]) -> None:
        sync_players(session, client)
        build_crosswalk(session)

    return {"sync_league": _sync_league, "sync_players": _sync_players}


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
    run_forever()
