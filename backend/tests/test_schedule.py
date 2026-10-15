from datetime import timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sleeper_assistant import jobs
from sleeper_assistant.dashboard import current_week, games_for_week
from sleeper_assistant.db import NflGameRow, utcnow
from sleeper_assistant.ingest import sync_schedule
from sleeper_assistant.sleeper import BASE_URL, SleeperClient
from sleeper_assistant.worker import enqueue_schedule_sync_if_due


def _game(gid: str, week: int, home: str, away: str, status: str) -> NflGameRow:
    return NflGameRow(
        game_id=gid,
        season="2026",
        week=week,
        home=home,
        away=away,
        game_date="2026-09-20",
        status=status,
    )


def _season(session: Session) -> None:
    session.add_all(
        [
            _game("1", 1, "SF", "DAL", "complete"),
            _game("2", 1, "MIN", "CHI", "complete"),
            _game("3", 2, "SF", "CHI", "in_game"),
            _game("4", 2, "DAL", "PIT", "pre_game"),
            _game("5", 2, "NE", "NYJ", "postponed"),  # a status we do not recognise
            _game("6", 1, "NE", "NYJ", "complete"),
            _game("7", 1, "PIT", "BUF", "complete"),
            _game("8", 1, "BUF", "NYJ", "complete"),
        ]
    )
    session.commit()


def test_current_week_is_the_first_unfinished_week(session: Session) -> None:
    assert current_week(session, "2026") is None  # no schedule loaded
    _season(session)
    assert current_week(session, "2026") == 2


def test_current_week_is_the_last_week_when_everything_is_final(session: Session) -> None:
    session.add_all(
        [_game("1", 1, "SF", "DAL", "complete"), _game("2", 2, "SF", "CHI", "complete")]
    )
    session.commit()
    assert current_week(session, "2026") == 2


def test_games_show_state_opponent_home_and_bye(session: Session) -> None:
    _season(session)
    week2 = games_for_week(session, "2026", 2)

    assert week2["SF"].state == "live"
    assert (week2["SF"].opponent, week2["SF"].home) == ("CHI", True)
    assert (week2["CHI"].opponent, week2["CHI"].home) == ("SF", False)
    assert week2["DAL"].state == "upcoming"
    assert week2["DAL"].date == "2026-09-20"
    assert week2["MIN"].state == "bye"  # MIN played in week 1 but has no game in week 2
    assert week2["MIN"].opponent is None


def test_unknown_status_shows_nothing_and_is_not_mistaken_for_a_bye(session: Session) -> None:
    _season(session)
    week2 = games_for_week(session, "2026", 2)
    assert "NE" not in week2
    assert "NYJ" not in week2


def test_a_week_without_games_marks_no_one_as_bye(session: Session) -> None:
    _season(session)
    assert games_for_week(session, "2026", 9) == {}  # missing data, not 32 byes


def test_final_games_in_a_finished_week(session: Session) -> None:
    _season(session)
    week1 = games_for_week(session, "2026", 1)
    assert week1["SF"].state == "final"
    assert week1["MIN"].state == "final"


def _client(payload: list[dict[str, object]]) -> SleeperClient:
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, json=payload))
    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=transport))


GAMES = [
    {
        "game_id": "a",
        "week": 1,
        "home": "SF",
        "away": "DAL",
        "date": "2026-09-13",
        "status": "pre_game",
    },
    {"game_id": "b", "week": 1, "home": "MIN", "away": "CHI", "date": None, "status": "pre_game"},
]


def test_sync_schedule_inserts_then_updates_in_place(session: Session) -> None:
    assert sync_schedule(session, _client(GAMES), "2026") == 2

    updated = [{**GAMES[0], "status": "complete"}, GAMES[1]]
    assert sync_schedule(session, _client(updated), "2026") == 2

    assert session.scalar(select(func.count()).select_from(NflGameRow)) == 2  # no duplicates
    session.expire_all()
    assert session.get(NflGameRow, "a").status == "complete"  # type: ignore[union-attr]
    assert session.get(NflGameRow, "b").game_date is None  # type: ignore[union-attr]


def test_schedule_refresh_is_enqueued_each_cycle_but_not_twice_at_once(session: Session) -> None:
    now = utcnow()
    assert enqueue_schedule_sync_if_due(session, now)
    assert not enqueue_schedule_sync_if_due(session, now)  # already queued

    job = jobs.claim_next(session, now + timedelta(seconds=1))
    assert job is not None
    jobs.complete(session, job, now)
    assert not enqueue_schedule_sync_if_due(session, now + timedelta(minutes=5))  # just refreshed
    assert enqueue_schedule_sync_if_due(session, now + timedelta(minutes=11))  # due again


def test_a_failing_schedule_source_is_not_hammered(session: Session) -> None:
    now = utcnow()
    enqueue_schedule_sync_if_due(session, now)
    job = jobs.claim_next(session, now + timedelta(seconds=1))
    assert job is not None
    job.max_attempts = 1
    jobs.fail(session, job, "boom", now)

    assert not enqueue_schedule_sync_if_due(session, now + timedelta(minutes=15))  # cooling down
    assert enqueue_schedule_sync_if_due(session, now + timedelta(minutes=31))


def test_a_postponed_game_does_not_pin_the_current_week(session: Session) -> None:
    session.add_all(
        [
            _game("1", 6, "SF", "DAL", "complete"),
            _game("2", 6, "MIN", "CHI", "pre_game"),  # postponed, never completed
            _game("3", 7, "PIT", "BUF", "complete"),
            _game("4", 8, "SF", "PIT", "pre_game"),
        ]
    )
    session.commit()
    assert current_week(session, "2026") == 8
