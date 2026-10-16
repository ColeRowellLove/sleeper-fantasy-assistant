"""League-independent player data for the Players tab: Sleeper's add/drop trends and weekly stats.

Both are stored as pulled and scored per league when shown, because every league scores differently.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import PlayerTrendRow, PlayerWeekStatsRow, utcnow
from sleeper_assistant.sleeper import SleeperClient


def sync_trending(session: Session, client: SleeperClient) -> int:
    """Store the latest add and drop counts. Returns how many players are listed.

    Sleeper only reports its top 100 each way, so a player outside a list has no number (None),
    which is different from having zero adds.
    """
    adds = dict(client.get_trending("add"))
    drops = dict(client.get_trending("drop"))
    existing = {row.player_id: row for row in session.scalars(select(PlayerTrendRow))}
    now = utcnow()
    listed = set(adds) | set(drops)
    for player_id in listed:
        row = existing.get(player_id)
        if row is None:
            row = existing[player_id] = PlayerTrendRow(player_id=player_id)
            session.add(row)
        row.adds = adds.get(player_id)
        row.drops = drops.get(player_id)
        row.fetched_at = now
    for player_id, row in existing.items():
        if player_id not in listed:
            session.delete(row)  # no longer trending either way
    session.commit()
    return len(listed)


def stored_weeks(session: Session, season: str) -> set[int]:
    return set(
        session.scalars(
            select(PlayerWeekStatsRow.week).where(PlayerWeekStatsRow.season == season).distinct()
        )
    )


def sync_week_stats(
    session: Session, client: SleeperClient, season: str, weeks: Iterable[int]
) -> int:
    """Store (or refresh) each week's actual stat lines. Returns how many rows were written."""
    written = 0
    for week in sorted(set(weeks)):
        lines = client.get_stats(season, week)
        existing = {
            row.player_id: row
            for row in session.scalars(
                select(PlayerWeekStatsRow).where(
                    PlayerWeekStatsRow.season == season, PlayerWeekStatsRow.week == week
                )
            )
        }
        now = utcnow()
        for line in lines:
            row = existing.get(line.player_id)
            if row is None:
                session.add(
                    PlayerWeekStatsRow(
                        season=season,
                        week=week,
                        player_id=line.player_id,
                        team=line.team,
                        stats=line.stats,
                        fetched_at=now,
                    )
                )
            else:
                row.team = line.team
                row.stats = line.stats
                row.fetched_at = now
            written += 1
        session.commit()
    return written
