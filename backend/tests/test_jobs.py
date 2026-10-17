import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sleeper_assistant import jobs
from sleeper_assistant.db import (
    Base,
    JobRow,
    LeagueRow,
    as_utc,
    make_engine,
    make_session_factory,
    utcnow,
)
from sleeper_assistant.job_schedule import enqueue_due_syncs, enqueue_player_sync_if_due
from sleeper_assistant.worker import run_cycle, run_once


def test_enqueue_and_claim_in_order(session: Session) -> None:
    now = utcnow()
    jobs.enqueue(session, "b", run_at=now - timedelta(seconds=1))
    jobs.enqueue(session, "a", run_at=now - timedelta(seconds=5))
    jobs.enqueue(session, "later", run_at=now + timedelta(hours=1))

    first = jobs.claim_next(session, now)
    second = jobs.claim_next(session, now)
    assert first is not None
    assert second is not None
    assert (first.kind, second.kind) == ("a", "b")
    assert first.status == "running"
    assert first.attempts == 1
    assert jobs.claim_next(session, now) is None  # "later" is not due yet


def test_dedupe_key(session: Session) -> None:
    assert jobs.enqueue(session, "sync", dedupe_key="k") is not None
    assert jobs.enqueue(session, "sync", dedupe_key="k") is None
    job = jobs.claim_next(session)
    assert job is not None
    assert jobs.enqueue(session, "sync", dedupe_key="k") is None  # still running
    jobs.complete(session, job)
    assert jobs.enqueue(session, "sync", dedupe_key="k") is not None  # done: allowed again


def test_retry_backoff_then_fail(session: Session) -> None:
    now = utcnow()
    jobs.enqueue(session, "x", max_attempts=2, run_at=now)
    job = jobs.claim_next(session, now)
    assert job is not None
    jobs.fail(session, job, "boom", now)
    assert job.status == "queued"
    assert job.run_at.replace(tzinfo=None) == (now + timedelta(seconds=30)).replace(tzinfo=None)

    job = jobs.claim_next(session, now + timedelta(minutes=1))
    assert job is not None
    jobs.fail(session, job, "boom again", now)
    assert job.status == "failed"
    assert job.last_error == "boom again"


def test_requeue_stale(session: Session) -> None:
    now = utcnow()
    jobs.enqueue(session, "x", run_at=now)
    job = jobs.claim_next(session, now)
    assert job is not None
    assert jobs.requeue_stale(session, now) == 0
    assert jobs.requeue_stale(session, now + timedelta(minutes=11)) == 1
    session.refresh(job)
    assert job.status == "queued"


def test_run_once_success_failure_and_unknown(engine: Engine) -> None:
    factory = make_session_factory(engine)
    calls: list[dict[str, object]] = []

    def ok(_s: Session, payload: dict[str, object]) -> None:
        calls.append(payload)

    def bad(_s: Session, _p: dict[str, object]) -> None:
        raise RuntimeError("nope")

    with factory() as s:
        jobs.enqueue(s, "ok", {"n": 1})
        jobs.enqueue(s, "bad", max_attempts=1)
        jobs.enqueue(s, "mystery", max_attempts=1)

    handlers = {"ok": ok, "bad": bad}
    assert [run_once(factory, handlers) for _ in range(4)] == [True, True, True, False]
    assert calls == [{"n": 1}]

    with factory() as s:
        rows = {j.kind: j for j in s.query(JobRow)}
    assert rows["ok"].status == "done"
    assert rows["bad"].status == "failed"
    assert rows["bad"].last_error == "RuntimeError: nope"
    assert rows["mystery"].status == "failed"


def test_enqueue_due_syncs(session: Session) -> None:
    now = utcnow()
    for lid, viewed, synced in [
        ("active_stale", now - timedelta(days=1), now - timedelta(hours=1)),
        ("active_fresh", now - timedelta(days=1), now - timedelta(minutes=1)),
        ("idle", now - timedelta(days=30), None),
        ("never_synced", now, None),
    ]:
        session.add(
            LeagueRow(
                league_id=lid,
                name=lid,
                season="2026",
                total_rosters=10,
                scoring_settings={},
                roster_positions=[],
                settings={},
                last_viewed_at=viewed,
                last_synced_at=synced,
            )
        )
    session.commit()

    assert enqueue_due_syncs(session, now) == 2
    assert enqueue_due_syncs(session, now) == 0  # deduped
    queued = {j.payload["league_id"] for j in session.query(JobRow)}
    assert queued == {"active_stale", "never_synced"}


def test_dedupe_enforced_by_database(session: Session) -> None:
    """A concurrent enqueue that slips past the check hits the partial unique index."""
    jobs.enqueue(session, "sync", dedupe_key="k")
    session.add(JobRow(kind="sync", payload={}, dedupe_key="k"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_as_utc_handles_naive_and_aware() -> None:
    naive = datetime(2026, 1, 1, 12, 0)
    aware = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    assert as_utc(naive) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert as_utc(aware) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_heartbeat_keeps_long_job_from_going_stale(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'hb.db'}")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    seen: list[datetime] = []

    def slow(session: Session, _payload: dict[str, object]) -> None:
        job = session.query(JobRow).one()
        session.refresh(job)
        first = job.locked_at
        assert first is not None
        deadline = time.monotonic() + 5  # poll rather than sleep a fixed time (slow CI runners)
        while time.monotonic() < deadline:
            session.refresh(job)
            assert job.locked_at is not None
            if job.locked_at > first:
                break
            time.sleep(0.02)
        seen.extend([first, job.locked_at])

    with factory() as s:
        jobs.enqueue(s, "slow")
    assert run_once(factory, {"slow": slow}, heartbeat_seconds=0.02)
    assert seen[1] > seen[0]
    engine.dispose()


def test_heartbeat_ignores_finished_jobs(session: Session) -> None:
    job = jobs.enqueue(session, "x")
    assert job is not None
    jobs.heartbeat(session, job.id)  # still queued: untouched
    session.refresh(job)
    assert job.locked_at is None


def test_player_sync_is_enqueued_hourly_but_not_twice_at_once(session: Session) -> None:
    now = utcnow()
    assert enqueue_player_sync_if_due(session, now)
    assert not enqueue_player_sync_if_due(session, now)  # already queued

    job = jobs.claim_next(session, now + timedelta(seconds=1))
    assert job is not None
    jobs.complete(session, job, now)
    assert not enqueue_player_sync_if_due(session, now + timedelta(minutes=30))  # done recently
    assert enqueue_player_sync_if_due(session, now + timedelta(minutes=61))  # due again


def test_run_cycle_enqueues_and_drains(engine: Engine) -> None:
    factory = make_session_factory(engine)
    ran: list[str] = []

    def record(s: Session, payload: dict[str, object]) -> None:
        league_id = payload.get("league_id")
        ran.append(str(league_id or "players"))
        if league_id:  # like a real sync, mark the league as freshly synced
            league = s.get(LeagueRow, str(league_id))
            assert league is not None
            league.last_synced_at = utcnow()
            s.commit()

    now = utcnow()
    with factory() as s:
        s.add(
            LeagueRow(
                league_id="L1",
                name="L",
                season="2026",
                total_rosters=2,
                scoring_settings={},
                roster_positions=[],
                settings={},
                last_viewed_at=now,
                last_synced_at=None,
            )
        )
        s.commit()

    result = run_cycle(
        factory,
        {
            "sync_league": record,
            "sync_players": record,
            "sync_schedule": lambda _s, _p: None,
            "sync_kickoffs": lambda _s, _p: None,
        },
    )

    # league, players, schedule, kickoffs, projections, trending, stats, history, ownership,
    # depth charts and the alert run
    assert result.enqueued == 12
    assert result.ran == 12
    assert sorted(ran) == ["L1", "players"]
    assert (
        run_cycle(
            factory,
            {
                "sync_league": record,
                "sync_players": record,
                "sync_schedule": lambda _s, _p: None,
                "sync_kickoffs": lambda _s, _p: None,
            },
        ).ran
        == 0
    )


def test_run_cycle_respects_max_jobs(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with factory() as s:
        for _ in range(3):
            jobs.enqueue(s, "noop")
    result = run_cycle(factory, {"noop": lambda _s, _p: None}, max_jobs=2)
    assert result.ran == 2


def test_failed_player_sync_backs_off(session: Session) -> None:
    now = utcnow()
    job = enqueue_player_sync_if_due(session, now)
    assert job
    claimed = jobs.claim_next(session, now + timedelta(seconds=1))
    assert claimed is not None
    claimed.max_attempts = 1
    jobs.fail(session, claimed, "boom", now)

    assert not enqueue_player_sync_if_due(session, now + timedelta(hours=2))  # cooling down
    assert enqueue_player_sync_if_due(session, now + timedelta(hours=7))  # try again later
