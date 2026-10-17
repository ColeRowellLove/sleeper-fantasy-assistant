"""Sit vs start accuracy, from the numbers Sleeper itself reports for each team.

Sleeper keeps two season totals on every roster: ``fpts`` (the points the starters scored) and
``ppts`` (the points the best possible lineups would have scored: "potential points"). Accuracy is
the first over the second. Nothing is recomputed here, so it always matches what the Sleeper app
shows; a team whose roster carries no potential points shows no accuracy rather than a guess.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from sleeper_assistant.core.rosters import league_rosters
from sleeper_assistant.core.team_names import team_names
from sleeper_assistant.db import LeagueRow


class TeamAccuracy(BaseModel):
    roster_id: int
    team: str
    points: float  # Sleeper's season points for the team (fpts)
    potential: float | None  # Sleeper's potential points: the best lineup each week (ppts)
    accuracy: float | None  # points over potential, 0 to 1; None when Sleeper reports no potential
    left_on_bench: float | None  # potential minus points


class LineupAccuracy(BaseModel):
    league_id: str
    teams: list[TeamAccuracy]  # most accurate first; teams without a figure last


def build_lineup_accuracy(session: Session, league: LeagueRow) -> LineupAccuracy:
    rosters = league_rosters(session, league.league_id)
    team, _ = team_names(session, rosters)
    teams: list[TeamAccuracy] = []
    for roster in rosters:
        potential = roster.potential_points
        usable = potential is not None and potential > 0
        points = round(roster.points_for, 2)
        teams.append(
            TeamAccuracy(
                roster_id=roster.roster_id,
                team=team[roster.roster_id],
                points=points,
                potential=round(potential, 2) if potential is not None else None,
                # a lineup can never beat the best one, so a rounding gap never shows above 100%
                accuracy=min(1.0, round(points / potential, 4)) if usable and potential else None,
                left_on_bench=round(max(0.0, potential - points), 2)
                if usable and potential
                else None,
            )
        )
    teams.sort(key=lambda t: (t.accuracy is None, -(t.accuracy or 0.0), t.team))
    return LineupAccuracy(league_id=league.league_id, teams=teams)
