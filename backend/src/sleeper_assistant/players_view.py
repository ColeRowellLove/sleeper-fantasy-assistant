"""The Players tab: every relevant NFL player seen through one league.

Each player is shown with whether they are available or on a roster in this league, Sleeper's add
and drop counts, season points under this league's scoring with a positional rank, and this week's
projection. The list is sent whole and filtered and sorted in the browser, so every sort is instant.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.dashboard import (
    GameInfo,
    InjuryInfo,
    _injury,
    _team_names,
    current_week,
    games_for_week,
)
from sleeper_assistant.db import (
    LeagueRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    RosterRow,
)
from sleeper_assistant.projections import projected_points, score_stats

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


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


class PlayersResponse(BaseModel):
    league_id: str
    week: int | None
    trends_updated_at: datetime | None = None
    players: list[PlayerListing]


def _name(player: PlayerRow) -> str:
    """Sleeper sometimes has no full name (team defenses, brand-new players): never show a blank."""
    if player.full_name:
        return player.full_name
    if player.position == "DEF" and player.team:
        return f"{player.team} defense"
    return player.player_id


def _season_totals(session: Session, season: str, scoring: dict[str, float]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in session.scalars(
        select(PlayerWeekStatsRow).where(PlayerWeekStatsRow.season == season)
    ):
        totals[row.player_id] += score_stats(row.stats, scoring)
    return {pid: round(total, 2) for pid, total in totals.items()}


def build_players(session: Session, league: LeagueRow) -> PlayersResponse:
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    team_name, _ = _team_names(session, rosters)
    owner: dict[str, int] = {}
    for roster in rosters:
        for pid in [*roster.players, *roster.reserve, *roster.taxi]:
            owner[pid] = roster.roster_id

    week = current_week(session, league.season)
    games = games_for_week(session, league.season, week) if week else {}
    totals = _season_totals(session, league.season, league.scoring_settings)
    trends = {row.player_id: row for row in session.scalars(select(PlayerTrendRow))}
    projected: dict[str, float] = {}
    if week:
        projectable = session.scalars(
            select(PlayerProjectionRow.player_id).where(
                PlayerProjectionRow.season == league.season, PlayerProjectionRow.week == week
            )
        )
        projected = projected_points(
            session, league.season, week, league.scoring_settings, set(projectable)
        )

    # a player is listed when this league or Sleeper gives a reason to look at them
    relevant = set(owner) | set(totals) | set(trends) | set(projected)
    candidates = session.scalars(
        select(PlayerRow).where(
            PlayerRow.player_id.in_(relevant),
            PlayerRow.position.in_(POSITIONS),
        )
    )
    listings: list[PlayerListing] = []
    for p in candidates:
        trend = trends.get(p.player_id)
        roster_id = owner.get(p.player_id)
        listings.append(
            PlayerListing(
                player_id=p.player_id,
                name=_name(p),
                position=p.position or "",
                team=p.team,
                injury=_injury({p.player_id: p}, p.player_id),
                game=games.get(p.team) if p.team else None,
                owner_roster_id=roster_id,
                owner_team=team_name.get(roster_id) if roster_id is not None else None,
                adds=trend.adds if trend else None,
                drops=trend.drops if trend else None,
                total_points=totals.get(p.player_id, 0.0),
                projected=projected.get(p.player_id),
            )
        )

    by_position: dict[str, list[PlayerListing]] = defaultdict(list)
    for listing in listings:
        if listing.player_id in totals:
            by_position[listing.position].append(listing)
    for group in by_position.values():
        group.sort(key=lambda x: (-x.total_points, x.name))
        for rank, listing in enumerate(group, start=1):
            listing.rank = rank

    listings.sort(key=lambda x: (-x.total_points, x.name))
    updated = max((t.fetched_at for t in trends.values()), default=None)
    return PlayersResponse(
        league_id=league.league_id, week=week, trends_updated_at=updated, players=listings
    )
