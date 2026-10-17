"""The league's transactions board: who added, dropped or traded for whom, newest first."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.core.league.loaders import players_by_id
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.league.team_names import team_names
from sleeper_assistant.db import LeagueRow, PlayerRow, TransactionRow

Kind = Literal["waiver", "free_agent", "trade", "commissioner"]
_KINDS: set[str] = {"waiver", "free_agent", "trade", "commissioner"}
LIMIT = 60


class MovedPlayer(BaseModel):
    player_id: str
    name: str
    position: str | None = None
    team: str | None = None


class TeamMove(BaseModel):
    """What one team did in a transaction: who came in and who went out."""

    roster_id: int
    team: str
    manager: str | None = None
    added: list[MovedPlayer] = []
    dropped: list[MovedPlayer] = []


class TransactionItem(BaseModel):
    transaction_id: str
    kind: Kind
    week: int
    created_at: datetime | None = None
    moves: list[TeamMove]


class TransactionsView(BaseModel):
    league_id: str
    transactions: list[TransactionItem]


def _created(created_ms: int | None) -> datetime | None:
    return datetime.fromtimestamp(created_ms / 1000, tz=UTC) if created_ms is not None else None


def _recent_rows(session: Session, league: LeagueRow) -> list[TransactionRow]:
    """The league's latest completed moves of known kinds (at most ``LIMIT``), newest first."""
    rows = [
        r
        for r in session.scalars(
            select(TransactionRow).where(
                TransactionRow.league_id == league.league_id, TransactionRow.status == "complete"
            )
        )
        if r.type in _KINDS and (r.payload.get("adds") or r.payload.get("drops"))
    ]
    rows.sort(key=lambda r: (r.created_ms or 0, r.transaction_id), reverse=True)
    return rows[:LIMIT]


def _moved(players: Mapping[str, PlayerRow], pid: str) -> MovedPlayer:
    p = players.get(pid)
    if p is None:
        return MovedPlayer(player_id=pid, name=pid)
    return MovedPlayer(player_id=pid, name=player_name(p), position=p.position, team=p.team)


def transaction_item(
    row: TransactionRow,
    team: Mapping[int, str],
    manager: Mapping[int, str],
    players: Mapping[str, PlayerRow],
) -> TransactionItem:
    """One stored move as the card shows it: what each team got and gave."""
    adds: dict[str, int] = row.payload.get("adds") or {}
    drops: dict[str, int] = row.payload.get("drops") or {}
    by_roster: dict[int, TeamMove] = {}
    for key, table in (("added", adds), ("dropped", drops)):
        for pid, roster_id in table.items():
            move = by_roster.setdefault(
                roster_id,
                TeamMove(
                    roster_id=roster_id,
                    team=team.get(roster_id, f"Team {roster_id}"),
                    manager=manager.get(roster_id),
                ),
            )
            getattr(move, key).append(_moved(players, pid))
    return TransactionItem(
        transaction_id=row.transaction_id,
        kind=row.type,
        week=row.week,
        created_at=_created(row.created_ms),
        moves=sorted(by_roster.values(), key=lambda m: m.roster_id),
    )


def build_transactions(session: Session, league: LeagueRow) -> TransactionsView:
    rows = _recent_rows(session, league)
    team, manager = team_names(session, league_rosters(session, league.league_id))
    ids = {pid for r in rows for key in ("adds", "drops") for pid in (r.payload.get(key) or {})}
    players = players_by_id(session, ids)
    return TransactionsView(
        league_id=league.league_id,
        transactions=[transaction_item(r, team, manager, players) for r in rows],
    )
