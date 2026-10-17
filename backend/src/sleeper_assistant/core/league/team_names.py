"""A league's team names and managers, as the managers chose them in Sleeper."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import RosterRow, SleeperUserRow, UserLeagueRow


def team_names(session: Session, rosters: list[RosterRow]) -> tuple[dict[int, str], dict[int, str]]:
    """(roster_id -> team name, roster_id -> manager's username). The team name is what the
    manager chose in Sleeper, falling back to their username."""
    owner_ids = {r.owner_id for r in rosters if r.owner_id}
    league_ids = {r.league_id for r in rosters}
    managers = {
        u.user_id: u.display_name
        for u in session.scalars(
            select(SleeperUserRow).where(SleeperUserRow.user_id.in_(owner_ids))
        )
    }
    chosen = {
        link.user_id: link.team_name
        for link in session.scalars(
            select(UserLeagueRow).where(
                UserLeagueRow.user_id.in_(owner_ids), UserLeagueRow.league_id.in_(league_ids)
            )
        )
        if link.team_name
    }
    manager = {r.roster_id: managers.get(r.owner_id or "", f"Team {r.roster_id}") for r in rosters}
    team = {r.roster_id: chosen.get(r.owner_id or "", manager[r.roster_id]) for r in rosters}
    return team, manager
