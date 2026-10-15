from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sleeper_assistant import jobs
from sleeper_assistant.db import JobRow, LeagueRow, make_session_factory, utcnow
from sleeper_assistant.worker import _as_utc, enqueue_due_syncs, run_once


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
    assert _as_utc(naive) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert _as_utc(aware) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
