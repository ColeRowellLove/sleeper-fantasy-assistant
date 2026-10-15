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

from sleeper_assistant import jobs
from sleeper_assistant.db import (
    JobRow,
    LeagueRow,
    NflGameRow,
    PlayerRow,
    RosterRow,
    make_session_factory,
)
from sleeper_assistant.sleeper import BASE_URL, SleeperClient
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
