"""A one-shot worker run reports jobs that failed for good so the workflow run turns red."""

import logging

import pytest
from sqlalchemy import Engine

from sleeper_assistant import jobs, worker
from sleeper_assistant.db import make_session_factory
from sleeper_assistant.worker import exit_code, run_batch, run_once, run_one_shot


def _boom(*_args: object) -> None:
    raise RuntimeError("source down")


def _enqueue(engine: Engine, kind: str, max_attempts: int = 1) -> None:
    with make_session_factory(engine)() as session:
        jobs.enqueue(session, kind, max_attempts=max_attempts)


def test_a_job_that_failed_for_good_is_reported_and_a_passing_one_is_not(engine: Engine) -> None:
    _enqueue(engine, "bad")
    _enqueue(engine, "good")
    failures: list[str] = []
    handlers = {"bad": _boom, "good": lambda *_: None}
    factory = make_session_factory(engine)
    while run_once(factory, handlers, failures=failures):
        pass
    assert failures == ["bad"]
    assert exit_code(failures) == 1
    assert exit_code([]) == 0


def test_a_job_that_will_be_retried_is_not_yet_a_failure(engine: Engine) -> None:
    _enqueue(engine, "flaky", max_attempts=3)
    failures: list[str] = []
    assert run_once(make_session_factory(engine), {"flaky": _boom}, failures=failures)
    assert failures == []  # queued again with backoff


def test_a_missing_handler_counts_as_a_failure(engine: Engine) -> None:
    _enqueue(engine, "unknown")
    failures: list[str] = []
    run_once(make_session_factory(engine), {}, failures=failures)
    assert failures == ["unknown"]


def test_the_one_shot_run_returns_1_and_says_what_failed(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    _enqueue(engine, "bad")
    _enqueue(engine, "bad")
    with caplog.at_level(logging.ERROR, logger="sleeper_assistant.worker"):
        code = run_one_shot(make_session_factory(engine), {"bad": _boom})
    assert code == 1
    assert "bad x2" in caplog.text


def test_a_clean_one_shot_run_returns_0(engine: Engine) -> None:
    _enqueue(engine, "good")
    assert run_one_shot(make_session_factory(engine), {"good": lambda *_: None}) == 0


def test_a_crashed_live_cycle_is_a_failure_too(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    real = worker.run_cycle

    def flaky(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("connection dropped")
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(worker, "run_cycle", flaky)
    monkeypatch.setattr(worker, "live_window_open", lambda *_a, **_k: True)
    clock = {"t": worker.utcnow()}

    def sleep(seconds: float) -> None:
        clock["t"] += worker.timedelta(seconds=seconds)

    failures: list[str] = []
    run_batch(
        make_session_factory(engine), {}, sleep=sleep, clock=lambda: clock["t"], failures=failures
    )
    assert failures and set(failures) == {"(a whole worker cycle)"}
