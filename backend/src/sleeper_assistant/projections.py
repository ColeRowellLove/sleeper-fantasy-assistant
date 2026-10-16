"""Weekly player projections from Sleeper, scored with each league's own scoring rules.

Sleeper's projections endpoint is unofficial. It returns a projected stat line per player, with the
same stat names a league uses in ``scoring_settings``, so projected points are simply each projected
stat times the league's value for it. A player's projection is kept as pulled before kickoff, so a
played week can still be compared with what was expected.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import NflGameRow, PlayerProjectionRow, utcnow
from sleeper_assistant.defense import parse_tier, points_allowed_score
from sleeper_assistant.sleeper import SleeperClient

# a game in any other state has kicked off (or finished), so its projections are frozen
_OPEN_STATUS = "pre_game"


def score_stats(stats: Mapping[str, float], scoring: Mapping[str, float]) -> float:
    """Fantasy points for a stat line under a league's scoring (stats the league ignores add 0)."""
    return round(sum(value * scoring[key] for key, value in stats.items() if key in scoring), 2)


def score_projection(stats: Mapping[str, float], scoring: Mapping[str, float]) -> float:
    """Projected fantasy points. A defense's points-allowed tiers are probability-weighted.

    A defense's projection carries ``pts_allow`` (its projected points allowed) and flags the one
    tier that figure lands in. That all-or-nothing flag is dropped and replaced by the expected
    value over every tier (see ``defense``). Every other stat is scored as usual.
    """
    mean = stats.get("pts_allow")
    if mean is None:
        return score_stats(stats, scoring)
    rest = {key: value for key, value in stats.items() if parse_tier(key) is None}
    return round(score_stats(rest, scoring) + points_allowed_score(mean, scoring), 2)


def sync_projections(session: Session, client: SleeperClient, season: str, week: int) -> int:
    """Store the week's projected stat lines. Returns how many players were stored or updated.

    A player whose game has already kicked off keeps the projection saved before it, so only a
    player seen for the first time is stored late.
    """
    projections = client.get_projections(season, week)
    status_by_team: dict[str, str] = {}
    for game in session.scalars(
        select(NflGameRow).where(NflGameRow.season == season, NflGameRow.week == week)
    ):
        status_by_team[game.home] = status_by_team[game.away] = game.status
    existing = {
        row.player_id: row
        for row in session.scalars(
            select(PlayerProjectionRow).where(
                PlayerProjectionRow.season == season, PlayerProjectionRow.week == week
            )
        )
    }
    now = utcnow()
    changed = 0
    for p in projections:
        row = existing.get(p.player_id)
        if row is None:
            session.add(
                PlayerProjectionRow(
                    season=season,
                    week=week,
                    player_id=p.player_id,
                    team=p.team,
                    stats=p.stats,
                    fetched_at=now,
                )
            )
            changed += 1
            continue
        if p.team and status_by_team.get(p.team, _OPEN_STATUS) != _OPEN_STATUS:
            continue  # the game has started: keep the pre-kickoff projection
        row.team = p.team
        row.stats = p.stats
        row.fetched_at = now
        changed += 1
    session.commit()
    return changed


def projected_points(
    session: Session,
    season: str,
    week: int,
    scoring: Mapping[str, float],
    player_ids: Iterable[str],
) -> dict[str, float]:
    """Projected fantasy points for the given players (those without a projection are absent)."""
    ids = set(player_ids)
    if not ids:
        return {}
    rows = session.scalars(
        select(PlayerProjectionRow).where(
            PlayerProjectionRow.season == season,
            PlayerProjectionRow.week == week,
            PlayerProjectionRow.player_id.in_(ids),
        )
    )
    return {row.player_id: score_projection(row.stats, scoring) for row in rows}
