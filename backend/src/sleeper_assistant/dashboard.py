"""Read models for the league dashboard: standings and rosters."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    PlayerOwnershipRow,
)
from sleeper_assistant.lineup_slots import starter_slots
from sleeper_assistant.matchup_rank import (
    build_defense_table,
)
from sleeper_assistant.nfl_games import current_week, games_for_week
from sleeper_assistant.projections import projected_points
from sleeper_assistant.roster_players import (
    RosterPlayer,
    load_players,
    roster_players,
    week_lines,
    week_points,
)
from sleeper_assistant.rosters import league_rosters
from sleeper_assistant.team_names import team_names


class StandingsRow(BaseModel):
    rank: int
    roster_id: int
    team: str
    manager: str | None = None  # the manager's Sleeper username
    owner_id: str | None = None
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    streak: str | None = None  # e.g. "3W" (three straight wins) or "2L"


class RosterView(BaseModel):
    roster_id: int
    team: str
    owner_id: str | None = None
    players: list[RosterPlayer]  # starters (slot order), bench, IR, taxi


class Dashboard(BaseModel):
    league_id: str
    name: str
    season: str
    week: int | None = None  # the current NFL week (first week with an unfinished game)
    standings: list[StandingsRow]
    rosters: list[RosterView]


def build_dashboard(session: Session, league: LeagueRow) -> Dashboard:
    rosters = league_rosters(session, league.league_id)
    team, manager = team_names(session, rosters)
    owners = {r.roster_id: r.owner_id for r in rosters}
    players = load_players(
        session, {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]}
    )
    slots = starter_slots(league.roster_positions)
    week = current_week(session, league.season)
    games = games_for_week(session, league.season, week) if week else {}
    defense = build_defense_table(session, league.season, league.scoring_settings)
    projected = (
        projected_points(
            session,
            league.season,
            week,
            league.scoring_settings,
            {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]},
        )
        if week
        else {}
    )

    earned = week_points(session, league.league_id, week) if week else {}
    lines = week_lines(session, league, week, players, games) if week else {}

    ordered = sorted(rosters, key=lambda r: (-r.wins, r.losses, -r.ties, -r.points_for))
    standings = [
        StandingsRow(
            rank=i,
            roster_id=r.roster_id,
            team=team[r.roster_id],
            manager=manager[r.roster_id],
            owner_id=owners[r.roster_id],
            wins=r.wins,
            losses=r.losses,
            ties=r.ties,
            points_for=round(r.points_for, 2),
            points_against=round(r.points_against, 2),
            streak=r.streak,
        )
        for i, r in enumerate(ordered, start=1)
    ]

    views = [
        RosterView(
            roster_id=r.roster_id,
            team=team[r.roster_id],
            owner_id=owners[r.roster_id],
            players=roster_players(
                r, players, slots, games, projected, earned.get(r.roster_id, {}), defense, lines
            ),
        )
        for r in sorted(rosters, key=lambda r: r.roster_id)
    ]
    _add_ownership(session, views)
    return Dashboard(
        league_id=league.league_id,
        name=league.name,
        season=league.season,
        week=week,
        standings=standings,
        rosters=views,
    )


def _add_ownership(session: Session, views: list[RosterView]) -> None:
    """Fill in ESPN's owned and started shares for every rostered player."""
    ids = {p.player_id for v in views for p in v.players}
    shares = {
        row.player_id: row
        for row in session.scalars(
            select(PlayerOwnershipRow).where(PlayerOwnershipRow.player_id.in_(ids))
        )
    }
    for view in views:
        for p in view.players:
            if row := shares.get(p.player_id):
                p.owned_pct, p.started_pct = row.owned, row.started
