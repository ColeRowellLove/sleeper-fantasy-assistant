"""A player's transactions in one league: who added, dropped or traded for him, and when."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.db import LeagueRow, SleeperUserRow, TransactionRow

Source = Literal["waivers", "free_agency", "trade", "commissioner"]
_SOURCES: dict[str, Source] = {
    "waiver": "waivers",
    "free_agent": "free_agency",
    "trade": "trade",
    "commissioner": "commissioner",
}
_MAX_EVENTS = 30


class HistoryEvent(BaseModel):
    kind: Literal["added", "dropped"]  # a trade shows as added for one team, dropped for another
    source: Source
    manager: str | None = None  # the Sleeper username (or display name) of the team involved
    date: str | None = None  # ISO date, UTC
    week: int


def transaction_date(created_ms: int | None) -> str | None:
    if created_ms is None:
        return None
    return datetime.fromtimestamp(created_ms / 1000, tz=UTC).date().isoformat()


def build_history(session: Session, league: LeagueRow, player_id: str) -> list[HistoryEvent]:
    """The player's completed adds and drops in this league, newest first (at most 30)."""
    owner_of = {r.roster_id: r.owner_id for r in league_rosters(session, league.league_id)}
    names = {
        u.user_id: u.username or u.display_name
        for u in session.scalars(
            select(SleeperUserRow).where(
                SleeperUserRow.user_id.in_({o for o in owner_of.values() if o})
            )
        )
    }

    def manager(roster_id: int) -> str | None:
        owner = owner_of.get(roster_id)
        return names.get(owner) if owner else None

    rows = session.scalars(
        select(TransactionRow).where(
            TransactionRow.league_id == league.league_id, TransactionRow.status == "complete"
        )
    )
    # newest first; the id breaks ties, and a missing time counts as oldest on every database
    ordered = sorted(rows, key=lambda r: (r.created_ms or 0, r.transaction_id), reverse=True)
    events: list[HistoryEvent] = []
    for row in ordered:
        source = _SOURCES.get(row.type)
        if source is None:
            continue
        for kind, key in (("added", "adds"), ("dropped", "drops")):
            roster_id = (row.payload.get(key) or {}).get(player_id)
            if roster_id is None:
                continue
            events.append(
                HistoryEvent(
                    kind=kind,
                    source=source,
                    manager=manager(roster_id),
                    date=transaction_date(row.created_ms),
                    week=row.week,
                )
            )
    return events[:_MAX_EVENTS]
