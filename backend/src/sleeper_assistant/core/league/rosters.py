"""A league's rosters, loaded the same way everywhere."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import RosterRow


def league_rosters(session: Session, league_id: str) -> list[RosterRow]:
    """Every roster of a league, by roster id."""
    return list(
        session.scalars(
            select(RosterRow).where(RosterRow.league_id == league_id).order_by(RosterRow.roster_id)
        )
    )
