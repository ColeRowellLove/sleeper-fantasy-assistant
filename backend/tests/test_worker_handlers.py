"""The worker's real job handlers, run against a fake Sleeper and a fake nflverse download."""

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from sleeper_assistant.core.sources.sleeper import BASE_URL, SleeperClient
from sleeper_assistant.db import (
    JobRow,
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    RosterRow,
    make_session_factory,
    utcnow,
)
from sleeper_assistant.sync import jobs
from sleeper_assistant.worker import Heartbeat, default_handlers, run_once

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "sleeper_league.json").read_text()
)

ROUTES: dict[str, Any] = {
    "/state/nfl": FIXTURE["state"],
    "/league/1": FIXTURE["league"] | {"league_id": "1"},
    "/league/1/users": FIXTURE["users"],
    "/league/1/rosters": FIXTURE["rosters"],
    "/players/nfl": FIXTURE["players"],
    "/schedule/nfl/regular/2026": FIXTURE["schedule"],
}
for week, items in FIXTURE["matchups"].items():
    ROUTES[f"/league/1/matchups/{week}"] = items
for week, items in FIXTURE["transactions"].items():
    ROUTES[f"/league/1/transactions/{week}"] = items

PROJECTION = [{"player_id": "4034", "team": "SF", "stats": {"pts_ppr": 10.0, "rec": 4.0}}]
for _week in (1, 2, 3, 4, 5, 6, 7, 8):
    ROUTES[f"/projections/nfl/2026/{_week}"] = PROJECTION

ROUTES["/players/nfl/trending/add"] = [{"player_id": "4034", "count": 900}]
ROUTES["/players/nfl/trending/drop"] = []
STATS = [{"player_id": "4034", "team": "SF", "stats": {"rec": 5, "rec_yd": 80.0}}]
for _week in range(1, 19):
    ROUTES[f"/stats/nfl/2026/{_week}"] = STATS

NFLVERSE_CSV = "season,game_type,week,gameday,gametime,home_team,away_team\n"


def _sleeper() -> SleeperClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/v1")
        if path in ROUTES:
            return httpx.Response(200, content=json.dumps(ROUTES[path]))
        return httpx.Response(404)

    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)))


def _http(body: str, status: int = 200) -> Callable[[], httpx.Client]:
    transport = httpx.MockTransport(lambda _request: httpx.Response(status, text=body))
    return lambda: httpx.Client(transport=transport)


def _run(engine: Engine, kind: str, handlers: dict[str, Any], payload: dict[str, Any]) -> None:
    factory = make_session_factory(engine)
    with factory() as session:
        jobs.enqueue(session, kind, payload=payload)
    assert run_once(factory, handlers)


def _status_count(session: Session, kind: str) -> int:
    return len(
        list(session.scalars(select(JobRow.id).where(JobRow.kind == kind, JobRow.status == "done")))
    )


def _status(session: Session, kind: str) -> str:
    return session.scalars(select(JobRow.status).where(JobRow.kind == kind)).one()


def test_sync_league_handler_stores_the_league(engine: Engine, session: Session) -> None:
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    _run(engine, "sync_league", handlers, {"league_id": "1"})
    session.expire_all()
    assert _status(session, "sync_league") == "done"
    assert session.get(LeagueRow, "1") is not None
    assert session.scalar(select(func.count()).select_from(RosterRow)) == 2


def test_sync_players_handler_loads_players_and_crosswalk(engine: Engine, session: Session) -> None:
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    _run(engine, "sync_players", handlers, {})
    session.expire_all()
    assert _status(session, "sync_players") == "done"
    assert (session.scalar(select(func.count()).select_from(PlayerRow)) or 0) > 0


def test_sync_schedule_handler_defaults_to_the_current_season(
    engine: Engine, session: Session
) -> None:
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    _run(engine, "sync_schedule", handlers, {})  # no season in the payload: Sleeper's state decides
    session.expire_all()
    assert _status(session, "sync_schedule") == "done"
    assert (session.scalar(select(func.count()).select_from(NflGameRow)) or 0) > 0


def test_sync_kickoffs_handler_stores_times_from_the_download(
    engine: Engine, session: Session
) -> None:
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    _run(engine, "sync_schedule", handlers, {"season": "2026"})
    game = session.scalars(select(NflGameRow)).first()
    assert game is not None
    csv = NFLVERSE_CSV + f"2026,REG,{game.week},2026-09-20,13:00,{game.home},{game.away}\n"

    handlers = default_handlers(_sleeper(), _http(csv))
    _run(engine, "sync_kickoffs", handlers, {})
    session.expire_all()
    row = session.get(NflGameRow, game.game_id)
    assert row is not None and row.kickoff is not None
    assert row.kickoff.replace(tzinfo=UTC) == datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
    assert _status(session, "sync_kickoffs") == "done"


def test_sync_projections_handler_stores_this_week_and_next(
    engine: Engine, session: Session
) -> None:
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    _run(engine, "sync_projections", handlers, {})
    session.expire_all()
    assert _status(session, "sync_projections") == "done"
    weeks = sorted(session.scalars(select(PlayerProjectionRow.week)))
    state_week = ROUTES["/state/nfl"]["week"]
    assert weeks == [state_week, state_week + 1]


def test_sync_projections_handler_does_nothing_outside_the_regular_season(
    engine: Engine, session: Session
) -> None:
    offseason = dict(ROUTES["/state/nfl"], season_type="off")
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    ROUTES["/state/nfl"], original = offseason, ROUTES["/state/nfl"]
    try:
        _run(engine, "sync_projections", handlers, {})
    finally:
        ROUTES["/state/nfl"] = original
    session.expire_all()
    assert _status(session, "sync_projections") == "done"
    assert session.scalar(select(func.count()).select_from(PlayerProjectionRow)) == 0


def test_sync_trending_handler_stores_add_counts(engine: Engine, session: Session) -> None:
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    _run(engine, "sync_trending", handlers, {})
    session.expire_all()
    assert _status(session, "sync_trending") == "done"
    row = session.get(PlayerTrendRow, "4034")
    assert row is not None and row.adds == 900


def test_sync_stats_handler_loads_missing_weeks_and_refreshes_the_latest(
    engine: Engine, session: Session
) -> None:
    handlers = default_handlers(_sleeper(), _http(NFLVERSE_CSV))
    _run(engine, "sync_stats", handlers, {})
    session.expire_all()
    current = ROUTES["/state/nfl"]["week"]
    assert sorted(session.scalars(select(PlayerWeekStatsRow.week))) == list(range(1, current + 1))

    session.add(
        PlayerWeekStatsRow(season="2026", week=1, player_id="x", stats={}, fetched_at=utcnow())
    )
    session.commit()
    _run(engine, "sync_stats", handlers, {})  # nothing is missing, only the latest week reloads
    session.expire_all()
    assert _status_count(session, "sync_stats") == 2


def test_sync_stats_handler_does_nothing_before_the_season(
    engine: Engine, session: Session
) -> None:
    original = ROUTES["/state/nfl"]
    ROUTES["/state/nfl"] = dict(original, season_type="pre")
    try:
        _run(engine, "sync_stats", default_handlers(_sleeper(), _http(NFLVERSE_CSV)), {})
    finally:
        ROUTES["/state/nfl"] = original
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(PlayerWeekStatsRow)) == 0


def test_a_failed_kickoff_download_fails_the_job_and_keeps_the_worker_alive(
    engine: Engine, session: Session
) -> None:
    handlers = default_handlers(_sleeper(), _http("nope", status=503))
    _run(engine, "sync_kickoffs", handlers, {"season": "2026"})
    session.expire_all()
    job = session.scalars(select(JobRow)).one()
    assert job.status in {"queued", "failed"}  # retried or given up, never crashing the worker
    assert job.attempts == 1
    assert job.last_error is not None and "503" in job.last_error


def test_heartbeat_survives_a_failed_beat(monkeypatch: pytest.MonkeyPatch) -> None:
    beats = threading.Event()
    calls: list[int] = []

    class Broken:
        def __enter__(self) -> "Broken":
            calls.append(1)
            beats.set()
            raise RuntimeError("database went away")

        def __exit__(self, *_: object) -> None:
            return None

    with Heartbeat(Broken, job_id=1, interval=0.01):  # type: ignore[arg-type]
        assert beats.wait(2.0)
        threading.Event().wait(0.05)
    assert len(calls) >= 2  # it kept beating after the first failure
