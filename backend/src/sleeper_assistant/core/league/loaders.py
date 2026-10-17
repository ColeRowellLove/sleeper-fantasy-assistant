"""Loading the rows many views and alerts need, written once."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import PlayerRow


def players_by_id(session: Session, player_ids: Iterable[str]) -> dict[str, PlayerRow]:
    """The players with these ids, keyed by id; an unknown id is simply missing."""
    ids = list(player_ids)
    if not ids:
        return {}
    rows = session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(ids)))
    return {p.player_id: p for p in rows}
