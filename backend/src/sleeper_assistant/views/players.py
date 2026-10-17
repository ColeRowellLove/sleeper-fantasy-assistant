"""The Players tab: every relevant NFL player seen through one league.

Each player is shown with whether they are available or on a roster in this league, Sleeper's add
and drop counts, season points under this league's scoring with a positional rank, and this week's
projection. The list is sent whole and filtered and sorted in the browser, so every sort is instant.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import FANTASY_POSITIONS
from sleeper_assistant.core.league.ownership import roster_owners
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.league.team_names import team_names
from sleeper_assistant.core.models.games import GameInfo
from sleeper_assistant.core.models.injury import InjuryInfo
from sleeper_assistant.core.nfl.injury_status import injury_info
from sleeper_assistant.core.nfl.nfl_games import current_week_games
from sleeper_assistant.core.scoring.projections import projected_points, score_stats
from sleeper_assistant.db import (
    LeagueRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
)


class PlayerListing(BaseModel):
    player_id: str
    name: str
    position: str
    team: str | None
    injury: InjuryInfo | None = None
    game: GameInfo | None = None  # this week's game (or bye) for the player's NFL team
    owner_roster_id: int | None = None  # None means available in this league
    owner_team: str | None = None
    adds: int | None = None  # Sleeper's 24-hour adds (top 100 only); None = not listed
    drops: int | None = None
    total_points: float = 0.0  # this season, under this league's scoring
    rank: int | None = None  # within position by total points; None when no points yet
    projected: float | None = None  # this week; None = no projection
    last_points: float | None = None  # last week's points; None = he did not play
    owned_pct: float | None = None  # ESPN-wide share of leagues that roster the player
    started_pct: float | None = None  # ESPN-wide share of leagues that start the player


class PlayersResponse(BaseModel):
    league_id: str
    week: int | None
    trends_updated_at: datetime | None = None
    players: list[PlayerListing]


def _season_totals(session: Session, season: str, scoring: dict[str, float]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in session.scalars(
        select(PlayerWeekStatsRow).where(PlayerWeekStatsRow.season == season)
    ):
        totals[row.player_id] += score_stats(row.stats, scoring)
    return {pid: round(total, 2) for pid, total in totals.items()}


def _last_week_points(
    session: Session, season: str, week: int | None, scoring: dict[str, float]
) -> dict[str, float]:
    """Points each player scored the week before ``week`` (only those who played)."""
    if not week or week < 2:  # noqa: PLR2004 - there is no week before the first
        return {}
    rows = session.scalars(
        select(PlayerWeekStatsRow).where(
            PlayerWeekStatsRow.season == season, PlayerWeekStatsRow.week == week - 1
        )
    )
    return {
        row.player_id: round(score_stats(row.stats, scoring), 2)
        for row in rows
        if row.stats.get("gp", 1.0) > 0
    }


def _projections_for(session: Session, league: LeagueRow, week: int | None) -> dict[str, float]:
    if not week:
        return {}
    projectable = session.scalars(
        select(PlayerProjectionRow.player_id).where(
            PlayerProjectionRow.season == league.season, PlayerProjectionRow.week == week
        )
    )
    return projected_points(session, league.season, week, league.scoring_settings, set(projectable))


def _add_position_ranks(listings: list[PlayerListing], totals: Mapping[str, float]) -> None:
    """Rank each player who has scored among his position by season points."""
    by_position: dict[str, list[PlayerListing]] = defaultdict(list)
    for listing in listings:
        if listing.player_id in totals:
            by_position[listing.position].append(listing)
    for group in by_position.values():
        group.sort(key=lambda x: (-x.total_points, x.name))
        for rank, listing in enumerate(group, start=1):
            listing.rank = rank


def build_players(session: Session, league: LeagueRow) -> PlayersResponse:
    rosters = league_rosters(session, league.league_id)
    team_name, _ = team_names(session, rosters)
    owner = roster_owners(rosters)

    week, games = current_week_games(session, league.season)
    totals = _season_totals(session, league.season, league.scoring_settings)
    last = _last_week_points(session, league.season, week, league.scoring_settings)
    trends = {row.player_id: row for row in session.scalars(select(PlayerTrendRow))}
    ownership = {row.player_id: row for row in session.scalars(select(PlayerOwnershipRow))}
    projected = _projections_for(session, league, week)

    # a player is listed when this league or Sleeper gives a reason to look at them
    relevant = set(owner) | set(totals) | set(trends) | set(projected) | set(ownership)
    candidates = session.scalars(
        select(PlayerRow).where(
            PlayerRow.player_id.in_(relevant),
            PlayerRow.position.in_(FANTASY_POSITIONS),
        )
    )
    listings: list[PlayerListing] = []
    for p in candidates:
        trend = trends.get(p.player_id)
        espn = ownership.get(p.player_id)
        roster_id = owner.get(p.player_id)
        listings.append(
            PlayerListing(
                player_id=p.player_id,
                name=player_name(p),
                position=p.position or "",
                team=p.team,
                injury=injury_info({p.player_id: p}, p.player_id),
                game=games.get(p.team) if p.team else None,
                owner_roster_id=roster_id,
                owner_team=team_name.get(roster_id) if roster_id is not None else None,
                adds=trend.adds if trend else None,
                drops=trend.drops if trend else None,
                total_points=totals.get(p.player_id, 0.0),
                projected=projected.get(p.player_id),
                last_points=last.get(p.player_id),
                owned_pct=espn.owned if espn else None,
                started_pct=espn.started if espn else None,
            )
        )

    _add_position_ranks(listings, totals)
    listings.sort(key=lambda x: (-x.total_points, x.name))
    updated = max((t.fetched_at for t in trends.values()), default=None)
    return PlayersResponse(
        league_id=league.league_id, week=week, trends_updated_at=updated, players=listings
    )
