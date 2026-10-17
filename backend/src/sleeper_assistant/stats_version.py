"""A cheap fingerprint of a season's stored games and stats, for caches that depend on them."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sleeper_assistant.db import NflGameRow, PlayerWeekStatsRow


def season_stats_version(session: Session, season: str) -> tuple[int, int]:
    """(completed games, stored stat rows): a table built from them is stale when this changes."""
    games = session.scalar(
        select(func.count())
        .select_from(NflGameRow)
        .where(NflGameRow.season == season, NflGameRow.status == "complete")
    )
    rows = session.scalar(
        select(func.count())
        .select_from(PlayerWeekStatsRow)
        .where(PlayerWeekStatsRow.season == season)
    )
    return (games or 0, rows or 0)
