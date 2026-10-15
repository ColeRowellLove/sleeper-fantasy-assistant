"""Read model for the league dashboard: standings and rosters, straight from the database."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import LeagueRow, PlayerRow, RosterRow, SleeperUserRow


class StandingsRow(BaseModel):
    rank: int
    roster_id: int
    team: str
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float


class RosterPlayer(BaseModel):
    player_id: str
    name: str
    position: str | None
    team: str | None
    starter: bool


class RosterView(BaseModel):
    roster_id: int
    team: str
    players: list[RosterPlayer]


class Dashboard(BaseModel):
    league_id: str
    name: str
    season: str
    standings: list[StandingsRow]
    rosters: list[RosterView]


def build_dashboard(session: Session, league: LeagueRow) -> Dashboard:
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    owner_ids = {r.owner_id for r in rosters if r.owner_id}
    names = {
        u.user_id: u.display_name
        for u in session.scalars(
            select(SleeperUserRow).where(SleeperUserRow.user_id.in_(owner_ids))
        )
    }
    team = {r.roster_id: names.get(r.owner_id or "", f"Team {r.roster_id}") for r in rosters}

    player_ids = {pid for r in rosters for pid in r.players}
    players = {
        p.player_id: p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(player_ids)))
    }

    ordered = sorted(rosters, key=lambda r: (-r.wins, r.losses, -r.ties, -r.points_for))
    standings = [
        StandingsRow(
            rank=i,
            roster_id=r.roster_id,
            team=team[r.roster_id],
            wins=r.wins,
            losses=r.losses,
            ties=r.ties,
            points_for=round(r.points_for, 2),
            points_against=round(r.points_against, 2),
        )
        for i, r in enumerate(ordered, start=1)
    ]

    views = []
    for r in sorted(rosters, key=lambda r: r.roster_id):
        starters = set(r.starters)
        roster_players = [
            RosterPlayer(
                player_id=pid,
                name=(players[pid].full_name if pid in players else None) or pid,
                position=players[pid].position if pid in players else None,
                team=players[pid].team if pid in players else None,
                starter=pid in starters,
            )
            for pid in r.players
        ]
        roster_players.sort(key=lambda p: (not p.starter, p.position or "~", p.name))
        views.append(
            RosterView(roster_id=r.roster_id, team=team[r.roster_id], players=roster_players)
        )

    return Dashboard(
        league_id=league.league_id,
        name=league.name,
        season=league.season,
        standings=standings,
        rosters=views,
    )
