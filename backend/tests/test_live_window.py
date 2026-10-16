"""Rapid refresh while a game is on: the shared window check, the cache header and the worker."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from sleeper_assistant import api
from sleeper_assistant.db import JobRow, NflGameRow, make_session_factory, utcnow
from sleeper_assistant.live_window import live_window_open
from sleeper_assistant.worker import (
    LIVE_CYCLE_SECONDS,
    STATS_SYNC_INTERVAL,
    STATS_SYNC_INTERVAL_LIVE,
    enqueue_schedule_sync_if_due,
    enqueue_stats_sync_if_due,
    run_batch,
)

NOW = datetime(2026, 10, 18, 18, 0, tzinfo=UTC)


def _game(
    gid: str, kickoff: datetime | None, status: str = "pre_game", season: str = "2026"
) -> NflGameRow:
    return NflGameRow(
        game_id=gid, season=season, week=6, home=f"H{gid}", away=f"A{gid}",
        game_date="2026-10-18", status=status, kickoff=kickoff,
    )  # fmt: skip


def test_the_window_is_open_around_kickoffs_and_while_sleeper_says_in_game(
    session: Session,
) -> None:
    assert not live_window_open(session, now=NOW)  # no games at all
    session.add(_game("far", NOW + timedelta(hours=4)))
    session.commit()
    assert not live_window_open(session, now=NOW)  # hours away
    session.add(_game("soon", NOW + timedelta(minutes=30)))
    session.commit()
    assert live_window_open(session, now=NOW)  # about to kick off


def test_a_game_that_kicked_off_lately_or_is_in_progress_opens_it_and_a_finished_one_does_not(
    session: Session,
) -> None:
    session.add(_game("old", NOW - timedelta(hours=9), status="complete"))
    session.commit()
    assert not live_window_open(session, now=NOW)  # long over
    session.add(_game("late", NOW - timedelta(hours=2)))
    session.commit()
    assert live_window_open(session, now=NOW)
    session.add(_game("noclock", None, status="in_game"))
    session.commit()
    assert live_window_open(session, "2026", now=NOW)


def test_the_window_can_be_asked_per_season(session: Session) -> None:
    session.add(_game("a", NOW + timedelta(minutes=10), season="2025"))
    session.commit()
    assert live_window_open(session, now=NOW)
    assert not live_window_open(session, "2026", now=NOW)


def test_reads_are_cached_briefly_only_while_a_game_is_on(session: Session) -> None:
    now = datetime.now(UTC)
    assert api.read_cache(session, "2026") == api.READ_CACHE
    session.add(_game("g", now + timedelta(minutes=5)))
    session.commit()
    assert api.read_cache(session, "2026") == api.READ_CACHE_LIVE
    assert "s-maxage=10" in api.READ_CACHE_LIVE and "s-maxage=30" in api.READ_CACHE


def test_stats_and_schedule_sync_often_while_a_game_is_on_and_slowly_otherwise(
    session: Session,
) -> None:
    def finished(kind: str, minutes_ago: int) -> None:
        session.add(
            JobRow(
                kind=kind,
                payload={},
                status="done",
                finished_at=NOW - timedelta(minutes=minutes_ago),
            )
        )
        session.commit()

    finished("sync_stats", 5)
    finished("sync_schedule", 5)
    assert not enqueue_stats_sync_if_due(session, NOW)  # no game on: hourly, and 5 minutes is soon
    assert not enqueue_schedule_sync_if_due(session, NOW)
    session.add(_game("live", NOW - timedelta(minutes=30), status="in_game"))
    session.commit()
    assert enqueue_stats_sync_if_due(session, NOW)  # a game is on: every couple of minutes
    assert enqueue_schedule_sync_if_due(session, NOW)
    assert STATS_SYNC_INTERVAL_LIVE < STATS_SYNC_INTERVAL


def test_a_stats_sync_that_ran_a_minute_ago_is_not_repeated_during_a_game(session: Session) -> None:
    session.add(_game("live", NOW - timedelta(minutes=30), status="in_game"))
    session.add(
        JobRow(
            kind="sync_stats", payload={}, status="done", finished_at=NOW - timedelta(seconds=60)
        )
    )
    session.commit()
    assert not enqueue_stats_sync_if_due(session, NOW)


def test_a_batch_repeats_about_once_a_minute_while_a_game_is_on_then_stops(
    engine: Engine,
) -> None:
    factory = make_session_factory(engine)
    with factory() as s:
        s.add(_game("live", utcnow() - timedelta(minutes=30), status="in_game"))
        s.commit()
    clock = {"now": utcnow()}
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["now"] += timedelta(seconds=seconds)

    cycles = run_batch(factory, {}, sleep=sleep, clock=lambda: clock["now"])
    assert slept and all(s == LIVE_CYCLE_SECONDS for s in slept)
    assert cycles == len(slept) + 1
    assert 10 <= cycles <= 12  # about a cycle a minute for the 12 minutes of budget


def test_a_batch_is_a_single_cycle_when_no_game_is_on(engine: Engine) -> None:
    slept: list[float] = []
    cycles = run_batch(make_session_factory(engine), {}, sleep=slept.append, clock=utcnow)
    assert cycles == 1 and slept == []
