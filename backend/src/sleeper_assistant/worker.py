"""Worker process: runs queued jobs. A cron only enqueues work (see enqueue_due_syncs)."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session, sessionmaker

from sleeper_assistant.alerts import detectors  # noqa: F401  registers the alert detectors
from sleeper_assistant.alerts.engine import run_all_leagues
from sleeper_assistant.core.nfl.live_window import live_window_open
from sleeper_assistant.core.scoring.projections import sync_projections
from sleeper_assistant.core.sources.espn import fetch_ownership
from sleeper_assistant.core.sources.sleeper import SleeperClient
from sleeper_assistant.db import (
    make_engine,
    make_session_factory,
    utcnow,
)
from sleeper_assistant.sync import jobs
from sleeper_assistant.sync.crosswalk import build_crosswalk
from sleeper_assistant.sync.depth_sync import sync_depth_charts
from sleeper_assistant.sync.ingest import MAX_WEEKS, sync_league, sync_players, sync_schedule
from sleeper_assistant.sync.job_schedule import (
    ACTIVE_WINDOW,
    HISTORY_SEASONS,
    enqueue_alerts_if_due,
    enqueue_depth_sync_if_due,
    enqueue_due_syncs,
    enqueue_history_sync_if_due,
    enqueue_kickoff_sync_if_due,
    enqueue_news_sync_if_due,
    enqueue_ownership_sync_if_due,
    enqueue_player_sync_if_due,
    enqueue_projection_sync_if_due,
    enqueue_schedule_sync_if_due,
    enqueue_stats_sync_if_due,
    enqueue_trending_sync_if_due,
)
from sleeper_assistant.sync.kickoffs import sync_kickoffs
from sleeper_assistant.sync.news_sync import sync_news
from sleeper_assistant.sync.player_data import (
    stored_weeks,
    sync_ownership,
    sync_season_history,
    sync_trending,
    sync_week_stats,
)

log = logging.getLogger(__name__)

Handler = Callable[[Session, dict[str, Any]], None]

POLL_SECONDS = 5.0
LIVE_CYCLE_SECONDS = 60.0  # how often a batch repeats inside its job while a game is on
LIVE_LOOP_BUDGET = timedelta(minutes=11)  # stop well before the 15-minute job limit
LIVE_CYCLE_BUDGET = timedelta(minutes=2)  # one repeated cycle never runs longer than this
CYCLE_MAX_JOBS = 50
CYCLE_BUDGET = timedelta(minutes=10)
HEARTBEAT_SECONDS = jobs.STALE_AFTER.total_seconds() / 4


def _sleeper_handlers(client: SleeperClient) -> dict[str, Handler]:
    """Jobs that read from the Sleeper API."""

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

    def _sync_trending(session: Session, _payload: dict[str, Any]) -> None:
        sync_trending(session, client)

    def _sync_stats(session: Session, payload: dict[str, Any]) -> None:
        state = client.get_state()
        if state.season_type not in ("regular", "post"):
            return  # nothing has been played yet
        season = str(payload.get("season") or state.season)
        last = MAX_WEEKS if state.season_type == "post" else min(state.week, MAX_WEEKS)
        have = stored_weeks(session, season)
        # weeks never loaded, plus the latest week again because it is still changing
        weeks = {w for w in range(1, last + 1) if w not in have} | {last}
        sync_week_stats(session, client, season, weeks)

    def _sync_history(session: Session, payload: dict[str, Any]) -> None:
        current = int(payload.get("season") or client.get_state().season)
        for season in range(current - 1, current - 1 - HISTORY_SEASONS, -1):
            sync_season_history(session, client, str(season))

    return {
        "sync_history": _sync_history,
        "sync_projections": _sync_projections,
        "sync_stats": _sync_stats,
        "sync_trending": _sync_trending,
        "sync_league": _sync_league,
        "sync_players": _sync_players,
        "sync_schedule": _sync_schedule,
    }


def _web_handlers(
    client: SleeperClient, http_factory: Callable[[], httpx.Client]
) -> dict[str, Handler]:
    """Jobs that read from other sites (ESPN, nflverse, news feeds, depth charts)."""

    def _sync_ownership(session: Session, payload: dict[str, Any]) -> None:
        season = str(payload.get("season") or client.get_state().season)
        with http_factory() as http:
            sync_ownership(session, fetch_ownership(http, season))

    def _sync_depth_charts(session: Session, _payload: dict[str, Any]) -> None:
        with http_factory() as http:
            sync_depth_charts(session, http)

    def _sync_news(session: Session, _payload: dict[str, Any]) -> None:
        with http_factory() as http:
            sync_news(session, http)

    def _sync_kickoffs(session: Session, payload: dict[str, Any]) -> None:
        season = str(payload.get("season") or client.get_state().season)
        with http_factory() as http:
            sync_kickoffs(session, http, season)

    return {
        "sync_depth_charts": _sync_depth_charts,
        "sync_kickoffs": _sync_kickoffs,
        "sync_news": _sync_news,
        "sync_ownership": _sync_ownership,
    }


def default_handlers(
    client: SleeperClient,
    http_factory: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=30.0),
) -> dict[str, Handler]:
    def _run_alerts(session: Session, _payload: dict[str, Any]) -> None:
        run_all_leagues(session, utcnow() - ACTIVE_WINDOW)

    return {
        "run_alerts": _run_alerts,
        **_sleeper_handlers(client),
        **_web_handlers(client, http_factory),
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
    failures: list[str] | None = None,
) -> bool:
    """Claim and run a single job. Returns False if nothing was due.

    A job that raises is retried with backoff. Once it has used up its attempts (it is marked
    failed for good) its kind is added to ``failures`` (when given), so a one-shot run can end with
    a failing exit code instead of looking healthy, while a blip that a retry fixes stays quiet."""
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
            if failures is not None and job.status == "failed":
                failures.append(job.kind)
        else:
            jobs.complete(session, job)
        return True


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
    failures: list[str] | None = None,
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
            + int(enqueue_trending_sync_if_due(session))
            + int(enqueue_stats_sync_if_due(session))
            + int(enqueue_history_sync_if_due(session))
            + int(enqueue_ownership_sync_if_due(session))
            + int(enqueue_depth_sync_if_due(session))
            + int(enqueue_news_sync_if_due(session))
            + int(enqueue_alerts_if_due(session))
        )
    ran = 0
    while (
        ran < max_jobs
        and utcnow() - started < budget
        and run_once(factory, handlers, failures=failures)
    ):
        ran += 1
    log.info("worker cycle: enqueued %d, ran %d", enqueued, ran)
    return CycleResult(enqueued=enqueued, ran=ran)


def run_batch(
    factory: sessionmaker[Session],
    handlers: dict[str, Handler],
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = utcnow,
    failures: list[str] | None = None,
) -> int:
    """One scheduled batch, repeated about once a minute while a game is on.

    Outside a live window this is a single cycle, exactly as before. While a game is on it keeps
    cycling (so the stat lines, which sync every couple of minutes then, stay fresh) until the
    window closes or ``LIVE_LOOP_BUDGET`` is used up, leaving the next scheduled run to carry on.
    Each repeated cycle has its own short time budget, a failed one is logged and the loop goes on,
    and the workflow's concurrency group stops two runs overlapping.
    Returns how many cycles ran. The kinds of jobs that failed are added to ``failures``.
    """
    started = clock()
    cycles = 1
    run_cycle(factory, handlers, failures=failures)
    while clock() - started + timedelta(seconds=LIVE_CYCLE_SECONDS) < LIVE_LOOP_BUDGET:
        with factory() as session:
            if not live_window_open(session, now=clock()):
                break
        sleep(LIVE_CYCLE_SECONDS)
        remaining = LIVE_LOOP_BUDGET - (clock() - started)
        try:
            run_cycle(
                factory, handlers, budget=min(LIVE_CYCLE_BUDGET, remaining), failures=failures
            )
        except Exception:  # a dropped connection or a source down must not end the live loop
            log.exception("live worker cycle failed; trying again next minute")
            if failures is not None:
                failures.append("(a whole worker cycle)")
        cycles += 1
    return cycles


def exit_code(failures: list[str]) -> int:
    """1 when any job failed for good during a one-shot batch (so the workflow run shows red)."""
    return 1 if failures else 0


def run_one_shot(factory: sessionmaker[Session], handlers: dict[str, Handler]) -> int:
    """The cron entry point: one batch, then the process exit code (1 when jobs failed for good)."""
    failures: list[str] = []
    run_batch(factory, handlers, failures=failures)
    if failures:
        counts = ", ".join(f"{kind} x{n}" for kind, n in sorted(Counter(failures).items()))
        log.error("worker batch finished with jobs failed for good: %s", counts)
    return exit_code(failures)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - process entry point
    parser = argparse.ArgumentParser(description="Sleeper assistant worker")
    parser.add_argument("--once", action="store_true", help="run one batch and exit (cron mode)")
    parser.add_argument(
        "--forget-failures",
        action="store_true",
        help="first delete failed jobs so their failure cooldowns end (use after fixing a cause)",
    )
    args = parser.parse_args(argv)
    if args.once:
        logging.basicConfig(level=logging.INFO)
        factory = make_session_factory(make_engine())
        if args.forget_failures:
            with factory() as session:
                log.info("forgot %d failed jobs", jobs.forget_failed(session))
        sys.exit(run_one_shot(factory, default_handlers(SleeperClient())))
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
