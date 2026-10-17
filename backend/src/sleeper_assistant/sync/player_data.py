"""League-independent player data for the Players tab: Sleeper's add/drop trends and weekly stats.

Both are stored as pulled and scored per league when shown, because every league scores differently.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from sleeper_assistant.core.sources.espn import Ownership, SleeperPerson, match_players
from sleeper_assistant.core.sources.sleeper import SleeperClient
from sleeper_assistant.db import (
    PlayerOwnershipRow,
    PlayerRow,
    PlayerSeasonStatsRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    utcnow,
)
from sleeper_assistant.sync.ingest import sync_schedule


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


HISTORY_WEEKS = 18
log = logging.getLogger(__name__)


def stored_history_seasons(session: Session) -> set[str]:
    """Seasons whose weeks are all stored (a half-loaded season is loaded again next time)."""
    counts = session.execute(
        select(
            PlayerWeekStatsRow.season, func.count(func.distinct(PlayerWeekStatsRow.week))
        ).group_by(PlayerWeekStatsRow.season)
    )
    return {season for season, weeks in counts if weeks >= HISTORY_WEEKS - 1}


def sync_season_history(session: Session, client: SleeperClient, season: str) -> int:
    """Load a finished season game by game. Returns how many players were stored.

    Every week's stat line is kept (so the pop-up can go game by game), the season totals and the
    teams each player played for are worked out from them, and that season's schedule is loaded so
    each game can name its opponent. A season that is already stored is left alone.
    """
    if season in stored_history_seasons(session):
        return 0
    sync_week_stats(session, client, season, range(1, HISTORY_WEEKS + 1))
    try:
        sync_schedule(session, client, season)  # opponents and home or away for past games
    except (httpx.HTTPError, ValueError):
        log.warning("could not load the %s schedule; past games will not name an opponent", season)
        session.rollback()

    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    games: dict[str, int] = defaultdict(int)
    teams: dict[str, list[str]] = defaultdict(list)
    weekly = session.scalars(
        select(PlayerWeekStatsRow)
        .where(PlayerWeekStatsRow.season == season)
        .order_by(PlayerWeekStatsRow.week)
    )
    for row in weekly:
        for stat, value in row.stats.items():
            totals[row.player_id][stat] += value
        games[row.player_id] += 1 if row.stats.get("gp", 1.0) > 0 else 0
        if row.team and row.team not in teams[row.player_id]:
            teams[row.player_id].append(row.team)
    session.execute(delete(PlayerSeasonStatsRow).where(PlayerSeasonStatsRow.season == season))
    for player_id, stats in totals.items():
        session.add(
            PlayerSeasonStatsRow(
                season=season,
                player_id=player_id,
                games=games[player_id],
                stats={k: round(v, 4) for k, v in stats.items()},
                teams=teams[player_id],
            )
        )
    session.commit()
    return len(totals)


def sync_ownership(session: Session, espn: list[Ownership]) -> int:
    """Store ESPN's owned and started percentages for the Sleeper players they match.

    ``espn`` is what was pulled; an empty pull (ESPN down or changed) changes nothing, so the
    previous numbers stay. Returns how many players were stored.
    """
    if not espn:
        return 0
    people = [
        SleeperPerson(
            player_id=p.player_id,
            name=p.full_name,
            team=p.team,
            position=p.position,
            espn_id=str(p.external_ids["espn"]) if p.external_ids.get("espn") else None,
        )
        for p in session.scalars(select(PlayerRow).where(PlayerRow.team.is_not(None)))
    ]
    matched = match_players(espn, people)
    existing = {row.player_id: row for row in session.scalars(select(PlayerOwnershipRow))}
    now = utcnow()
    for player_id, numbers in matched.items():
        row = existing.pop(player_id, None)
        if row is None:
            row = PlayerOwnershipRow(player_id=player_id)
            session.add(row)
        row.owned = numbers.owned
        row.started = numbers.started
        row.fetched_at = now
    for stale in existing.values():
        session.delete(stale)  # no longer among ESPN's top players: below the cutoff
    session.commit()
    return len(matched)
