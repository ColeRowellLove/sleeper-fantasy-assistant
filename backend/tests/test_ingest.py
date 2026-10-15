import json
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    PlayerRow,
    RawSnapshotRow,
    RosterRow,
    TransactionRow,
)
from sleeper_assistant.ingest import sync_league, sync_players
from sleeper_assistant.sleeper import BASE_URL, SleeperClient

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "sleeper_league.json").read_text()
)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path.removeprefix("/v1")
    routes: dict[str, Any] = {
        "/state/nfl": FIXTURE["state"],
        "/league/L1": FIXTURE["league"],
        "/league/L1/users": FIXTURE["users"],
        "/league/L1/rosters": FIXTURE["rosters"],
        "/players/nfl": FIXTURE["players"],
        "/schedule/nfl/regular/2026": FIXTURE["schedule"],
    }
    for week, items in FIXTURE["matchups"].items():
        routes[f"/league/L1/matchups/{week}"] = items
    for week, items in FIXTURE["transactions"].items():
        routes[f"/league/L1/transactions/{week}"] = items
    if path in routes:
        return httpx.Response(200, json=routes[path])
    return httpx.Response(404)


def _client() -> SleeperClient:
    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(_handler)))


def _count(session: Session, model: Any) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_sync_league(session: Session) -> None:
    sync_league(session, _client(), "L1")

    league = session.get(LeagueRow, "L1")
    assert league is not None
    assert league.previous_league_id == "L0"
    assert league.last_synced_at is not None

    roster = session.get(RosterRow, ("L1", 1))
    assert roster is not None
    assert (roster.wins, roster.points_for, roster.points_against) == (1, 120.42, 98.05)
    empty = session.get(RosterRow, ("L1", 2))
    assert empty is not None
    assert empty.players == []

    assert _count(session, MatchupRow) == 6  # weeks 1-3 (week 3 is an upcoming pairing)
    assert _count(session, TransactionRow) == 1
    assert _count(session, RawSnapshotRow) > 0


def test_sync_is_idempotent_and_keeps_last_viewed(session: Session) -> None:
    sync_league(session, _client(), "L1")
    league = session.get(LeagueRow, "L1")
    assert league is not None
    league.last_viewed_at = league.last_synced_at
    session.commit()
    viewed = league.last_viewed_at

    sync_league(session, _client(), "L1")
    assert _count(session, MatchupRow) == 6
    assert _count(session, RosterRow) == 2
    refreshed = session.get(LeagueRow, "L1")
    assert refreshed is not None
    assert refreshed.last_viewed_at == viewed


def test_sync_players(session: Session) -> None:
    assert sync_players(session, _client()) == 2
    cmc = session.get(PlayerRow, "4034")
    assert cmc is not None
    assert cmc.external_ids["gsis"] == "00-0033280"
    assert "yahoo" not in cmc.external_ids
    assert _count(session, RawSnapshotRow) == 0  # player DB is not snapshotted


def test_sync_players_updates_existing_rows(session: Session) -> None:
    sync_players(session, _client())
    changed = {**FIXTURE["players"]["4034"], "team": "DAL", "injury_status": "Questionable"}
    FIXTURE["players"]["4034"] = changed
    try:
        assert sync_players(session, _client()) == 2
    finally:
        FIXTURE["players"]["4034"] = {**changed, "team": "SF", "injury_status": None}
    session.expire_all()
    cmc = session.get(PlayerRow, "4034")
    assert cmc is not None
    assert (cmc.team, cmc.injury_status) == ("DAL", "Questionable")
    assert _count(session, PlayerRow) == 2  # updated in place, no duplicates
