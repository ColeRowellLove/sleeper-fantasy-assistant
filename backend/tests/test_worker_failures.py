"""A one-shot worker run reports failed jobs so the workflow run turns red."""

from sqlalchemy import Engine

from sleeper_assistant import jobs
from sleeper_assistant.db import make_session_factory
from sleeper_assistant.worker import exit_code, run_batch, run_once


def _boom(*_args: object) -> None:
    raise RuntimeError("source down")


def test_a_failing_job_is_reported_and_a_passing_one_is_not(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with factory() as session:
        jobs.enqueue(session, "bad")
        jobs.enqueue(session, "good")
    failures: list[str] = []
    handlers = {"bad": _boom, "good": lambda *_: None}
    while run_once(factory, handlers, failures=failures):
        pass
    assert failures == ["bad"]
    assert exit_code(failures) == 1
    assert exit_code([]) == 0


def test_a_missing_handler_counts_as_a_failure(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with factory() as session:
        jobs.enqueue(session, "unknown")
    failures: list[str] = []
    run_once(factory, {}, failures=failures)
    assert failures == ["unknown"]


def test_a_batch_collects_the_failures_of_its_cycle(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with factory() as session:
        jobs.enqueue(session, "bad")
    failures: list[str] = []
    run_batch(factory, {"bad": _boom}, failures=failures)
    assert "bad" in failures


def test_failures_are_optional(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with factory() as session:
        jobs.enqueue(session, "bad")
    assert run_once(factory, {"bad": _boom}) is True  # reported nowhere, still handled
