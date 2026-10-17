"""A team's depth chart as seen through one league: injuries, who owns whom, who starts.

The page answers "is my player going to start?": every slot lists its players in depth order with
an injury badge, which of the connected league's teams owns them (or that they are available), and
when a starter is out, who is next in line.
"""

from __future__ import annotations

import functools
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import GAME_COMPLETE
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.league.team_names import team_names
from sleeper_assistant.core.models.games import GameInfo
from sleeper_assistant.core.models.injury import InjuryInfo
from sleeper_assistant.core.nfl.depth import GROUPS, SKILL_SLOTS, slot_label, slot_order
from sleeper_assistant.core.nfl.injury_status import WILL_NOT_PLAY, injury_info
from sleeper_assistant.core.nfl.nfl_games import current_week, games_for_week
from sleeper_assistant.core.nfl.team_stats import TeamStat, all_team_stats, build_team_stats
from sleeper_assistant.db import LeagueRow, NflGameRow, PlayerRow, TeamDepthChartRow

# designations that mean a player will not play
_ORDINAL = {1: "Starter", 2: "2nd string", 3: "3rd string"}


class DepthPlayer(BaseModel):
    name: str
    player_id: str | None = None  # the Sleeper id, when the player could be matched
    depth: int  # 1 is the starter
    label: str  # Starter, 2nd string, ...
    injury: InjuryInfo | None = None
    owner_roster_id: int | None = None
    owner_team: str | None = None
    next_up: bool = False  # the starter is out and this player is first in line


class DepthSlot(BaseModel):
    slot: str
    label: str
    skill: bool = False  # a fantasy-relevant slot (QB, RB, WR, TE), shown first
    note: str | None = None  # for example "Starter out: next up is Jake Smith"
    players: list[DepthPlayer]


class DepthGroup(BaseModel):
    group: str  # offense, defense or special
    title: str
    slots: list[DepthSlot]


class TeamRecord(BaseModel):
    wins: int
    losses: int
    ties: int


def team_record(session: Session, season: str, team: str) -> TeamRecord | None:
    """The team's record from its finished games, or None when it cannot be stated exactly.

    Every finished game must have a stored score, otherwise the record could be wrong and is left
    out; a team with no finished game yet has no record either. The schedule holds the regular
    season only, so playoff games never count.
    """
    games = list(
        session.scalars(
            select(NflGameRow).where(
                NflGameRow.season == season,
                NflGameRow.status == GAME_COMPLETE,
                (NflGameRow.home == team) | (NflGameRow.away == team),
            )
        )
    )
    results: list[tuple[int, int]] = []  # (the team's points, the opponent's points)
    for g in games:
        if g.home_score is None or g.away_score is None:
            return None  # a finished game with no stored score could make the record wrong
        results.append(
            (g.home_score, g.away_score) if g.home == team else (g.away_score, g.home_score)
        )
    if not results:
        return None
    wins = sum(1 for mine, theirs in results if mine > theirs)
    losses = sum(1 for mine, theirs in results if mine < theirs)
    ties = len(results) - wins - losses
    return TeamRecord(wins=wins, losses=losses, ties=ties)


class TeamDepth(BaseModel):
    team: str
    source: str | None = None  # ESPN, or Sleeper when ESPN had no chart
    updated_at: datetime | None = None
    game: GameInfo | None = None
    record: TeamRecord | None = None  # wins, losses and ties; None unless exactly known
    stats: list[TeamStat] = []  # the team's per-game numbers with league ranks
    groups: list[DepthGroup]


_TITLES = {"offense": "Offense", "defense": "Defense", "special": "Special teams"}


def _status_of(player: DepthPlayer) -> str | None:
    return player.injury.status if player.injury else None


def _note(players: list[DepthPlayer]) -> str | None:
    """A plain sentence when the starter is out or doubtful, naming who is next; marks next_up."""
    if not players:
        return None
    starter_status = _status_of(players[0])
    if starter_status in WILL_NOT_PLAY:
        for backup in players[1:]:
            if _status_of(backup) not in WILL_NOT_PLAY:
                backup.next_up = True
                return f"{players[0].name} is out: next up is {backup.name}"
        return f"{players[0].name} is out and no healthy player is listed behind him"
    if starter_status == "Doubtful":
        return f"{players[0].name} is doubtful"
    return None


def build_team_depth(session: Session, league: LeagueRow, team: str) -> TeamDepth:
    """The stored depth chart for one NFL team, with this league's ownership and injuries."""
    row = session.get(TeamDepthChartRow, team)
    rosters = league_rosters(session, league.league_id)
    team_name, _ = team_names(session, rosters)
    owner = {pid: r.roster_id for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]}

    chart: dict[str, Any] = row.chart if row else {}
    ids = {
        e["sleeper_id"]
        for slots in chart.values()
        for players in slots.values()
        for e in players
        if e.get("sleeper_id")
    }
    sleeper = {
        p.player_id: p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(ids)))
    }

    groups: list[DepthGroup] = []
    for group in GROUPS:
        slots: list[DepthSlot] = []
        in_order = sorted(chart.get(group, {}), key=functools.partial(slot_order, group))
        for slot in in_order:
            players: list[DepthPlayer] = []
            for depth, entry in enumerate(chart[group][slot], start=1):
                pid = entry.get("sleeper_id")
                injury = injury_info(sleeper, pid) if pid else None
                if injury is None and entry.get("injury"):
                    injury = InjuryInfo(status=entry["injury"], body_part=None)
                owner_id = owner.get(pid) if pid else None
                players.append(
                    DepthPlayer(
                        name=entry["name"],
                        player_id=pid,
                        depth=depth,
                        label=_ORDINAL.get(depth, f"{depth}th string"),
                        injury=injury,
                        owner_roster_id=owner_id,
                        owner_team=team_name.get(owner_id) if owner_id is not None else None,
                    )
                )
            slots.append(
                DepthSlot(
                    slot=slot,
                    label=slot_label(group, slot),
                    skill=slot in SKILL_SLOTS,
                    note=_note(players),
                    players=players,
                )
            )
        if slots:
            groups.append(DepthGroup(group=group, title=_TITLES[group], slots=slots))

    week = current_week(session, league.season)
    game = games_for_week(session, league.season, week).get(team) if week else None
    return TeamDepth(
        team=team,
        source=row.source if row else None,
        updated_at=row.fetched_at if row else None,
        game=game,
        record=team_record(session, league.season, team),
        stats=all_team_stats(build_team_stats(session, league.season), team),
        groups=groups,
    )
