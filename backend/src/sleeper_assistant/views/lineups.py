"""Read models for the weekly lineups: both sides of each matchup, with win chances."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import EMPTY_SLOT
from sleeper_assistant.core.league.lineup_slots import starter_slots
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.league.team_avatar import team_avatars
from sleeper_assistant.core.league.team_names import team_names
from sleeper_assistant.core.nfl.injury_status import InjuryInfo, injury_info
from sleeper_assistant.core.nfl.matchup_rank import (
    DefenseTable,
    MatchupRank,
    build_defense_table,
    matchup_rank,
)
from sleeper_assistant.core.nfl.nfl_games import GameInfo, current_week, games_for_week
from sleeper_assistant.core.scoring.projections import projected_points
from sleeper_assistant.core.scoring.win_probability import StarterState, matchup_chances
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    PlayerRow,
)
from sleeper_assistant.views.roster_players import (
    Line,
    display,
    load_players,
    projection_now,
    week_lines,
)

# Matchup `players` also lists IR and taxi players; they are shown after the bench, not as bench.
_PARKED_ORDER = {"BN": 0, "IR": 1, "TAXI": 2}


class LineupPlayer(BaseModel):
    slot: str  # QB/RB/FLEX/... for starters, "BN" for bench
    player_id: str | None  # None for an empty starter slot
    name: str
    position: str | None
    team: str | None
    points: float | None
    game: GameInfo | None = None
    injury: InjuryInfo | None = None
    projected: float | None = None  # live: equals the score once the game is over
    projected_pregame: float | None = None  # the projection frozen before kickoff
    projection_missing: bool = False  # no projection was stored, so the 0 above is an assumption
    matchup: MatchupRank | None = None  # the opponent's defense rank against his position
    stat_line: str | None = None  # how he did, once his game has started
    stat_line_projected: bool = False  # True when stat_line is what he is projected to do


class TeamLineup(BaseModel):
    roster_id: int
    team: str
    avatar: str | None = None  # the team's picture URL, when it has one
    owner_id: str | None = None
    points: float
    projected: float | None = (
        None  # sum of the starters' live projections; None when there are none
    )
    projected_pregame: float | None = None  # the same, from the projections frozen before kickoff
    win_probability: float | None = (
        None  # chance to win from projections; None = nothing fair to say
    )
    win_probability_rough: bool = False  # True when starters with no projection were filled in
    starters: list[LineupPlayer]
    bench: list[LineupPlayer]


class MatchupView(BaseModel):
    matchup_id: int | None
    teams: list[TeamLineup]


class Lineups(BaseModel):
    week: int | None
    current_week: int | None = None  # weeks after this one have not been played yet
    weeks: list[int]
    matchups: list[MatchupView]


def build_lineups(session: Session, league: LeagueRow, week: int | None = None) -> Lineups:
    """Both teams' lineups per matchup for one week.

    Default week: the current NFL week when known, otherwise the latest week with scores.
    Weeks after the current one are upcoming: pairings with each team's current starters.
    """
    rows = list(session.scalars(select(MatchupRow).where(MatchupRow.league_id == league.league_id)))
    weeks = sorted({m.week for m in rows})
    current = current_week(session, league.season)
    if week is None:
        if current in weeks:
            week = current
        else:
            scored = [w for w in weeks if any(m.points for m in rows if m.week == w)]
            candidates = scored or weeks
            week = candidates[-1] if candidates else None
    if week is None or week not in weeks:
        return Lineups(week=None, current_week=current, weeks=weeks, matchups=[])

    week_rows = [m for m in rows if m.week == week]
    rosters = league_rosters(session, league.league_id)
    team, _ = team_names(session, rosters)
    avatars = team_avatars(session, rosters)
    owners = {r.roster_id: r.owner_id for r in rosters}
    players = load_players(session, {pid for m in week_rows for pid in [*m.starters, *m.players]})
    slots = starter_slots(league.roster_positions)
    games = games_for_week(session, league.season, week)
    defense = build_defense_table(session, league.season, league.scoring_settings)
    lines = week_lines(session, league, week, players, games)
    projected = projected_points(
        session,
        league.season,
        week,
        league.scoring_settings,
        {pid for m in week_rows for pid in [*m.starters, *m.players]},
    )
    # IR and taxi come from the current roster (past weeks use today's IR list)
    parked = {
        r.roster_id: {**{pid: "IR" for pid in r.reserve}, **{pid: "TAXI" for pid in r.taxi}}
        for r in rosters
    }

    by_matchup: dict[int, list[TeamLineup]] = {}
    for m in sorted(week_rows, key=lambda m: m.roster_id):
        lineup = _team_lineup(
            m,
            team,
            owners,
            players,
            slots,
            games,
            parked.get(m.roster_id, {}),
            projected,
            defense,
            lines,
        )
        lineup.avatar = avatars.get(m.roster_id)
        # a missing matchup_id (bye/unscheduled) must not group unrelated teams together
        key = m.matchup_id if m.matchup_id is not None else -m.roster_id
        by_matchup.setdefault(key, []).append(lineup)

    for teams in by_matchup.values():
        if len(teams) == 2:  # noqa: PLR2004 - a matchup is two teams
            _set_win_probability(teams[0], teams[1])

    matchups = [
        MatchupView(matchup_id=key if key > 0 else None, teams=teams)
        for key, teams in sorted(by_matchup.items(), key=lambda kv: abs(kv[0]))
    ]
    return Lineups(week=week, current_week=current, weeks=weeks, matchups=matchups)


def _starter_states(team: TeamLineup) -> list[StarterState]:
    return [
        StarterState(
            p.game.state if p.game else None,
            p.points,
            None if p.projection_missing else p.projected,
            pregame=None if p.projection_missing else p.projected_pregame,
            elapsed=p.game.elapsed if p.game else None,
        )
        for p in team.starters
        if p.player_id is not None  # an empty slot scores nothing and projects nothing
    ]


def _set_win_probability(a: TeamLineup, b: TeamLineup) -> None:
    chances = matchup_chances(_starter_states(a), _starter_states(b))
    rough = False
    if chances is None:
        # too many starters without a projection for a firm number: still give a rough one so every
        # matchup has a bar, marked as rough (None stays for a decided or empty matchup)
        chances = matchup_chances(_starter_states(a), _starter_states(b), fill_missing=True)
        rough = chances is not None
    if chances is not None:
        a.win_probability, b.win_probability = chances
        a.win_probability_rough = b.win_probability_rough = rough


def _team_projection(starters: list[LineupPlayer], *, pregame: bool = False) -> float | None:
    """Sum of the starters' projections, or None when no starter has one (never a misleading 0)."""
    values: list[float] = []
    for p in starters:
        value = p.projected_pregame if pregame else p.projected
        if value is not None:
            values.append(value)
    return round(sum(values), 2) if values else None


def _team_lineup(  # noqa: PLR0913, PLR0917
    m: MatchupRow,
    team: dict[int, str],
    owners: dict[int, str | None],
    players: dict[str, PlayerRow],
    slots: list[str],
    games: dict[str, GameInfo],
    parked: dict[str, str],
    projected: dict[str, float],
    defense: DefenseTable,
    lines: dict[str, Line],
) -> TeamLineup:
    points: dict[str, Any] = m.players_points

    def pts(pid: str) -> float | None:
        value = points.get(pid)
        return None if value is None else float(value)

    starters: list[LineupPlayer] = []
    for i, pid in enumerate(m.starters):
        slot = slots[i] if i < len(slots) else "FLEX"
        if pid == EMPTY_SLOT:
            starters.append(
                LineupPlayer(
                    slot=slot, player_id=None, name="Empty", position=None, team=None, points=None
                )
            )
            continue
        name, position, nfl_team = display(players, pid)
        value = m.starters_points[i] if i < len(m.starters_points) else pts(pid)
        game = games.get(nfl_team) if nfl_team else None
        pregame = projected.get(pid, 0.0)
        starters.append(
            LineupPlayer(
                slot=slot,
                player_id=pid,
                name=name,
                position=position,
                team=nfl_team,
                points=None if value is None else float(value),
                game=game,
                injury=injury_info(players, pid),
                projected=projection_now(pregame, None if value is None else float(value), game),
                projected_pregame=pregame,
                projection_missing=pid not in projected,
                matchup=matchup_rank(defense, position, game.opponent if game else None),
                stat_line=lines[pid].text if pid in lines else None,
                stat_line_projected=pid in lines and lines[pid].projected,
            )
        )

    bench = []
    for pid in m.players:
        if pid in m.starters:
            continue
        name, position, nfl_team = display(players, pid)
        game = games.get(nfl_team) if nfl_team else None
        pregame = projected.get(pid, 0.0)
        bench.append(
            LineupPlayer(
                slot=parked.get(pid, "BN"),
                player_id=pid,
                name=name,
                position=position,
                team=nfl_team,
                points=pts(pid),
                game=game,
                injury=injury_info(players, pid),
                projected=projection_now(pregame, pts(pid), game),
                projected_pregame=pregame,
                projection_missing=pid not in projected,
                matchup=matchup_rank(defense, position, game.opponent if game else None),
                stat_line=lines[pid].text if pid in lines else None,
                stat_line_projected=pid in lines and lines[pid].projected,
            )
        )
    bench.sort(key=lambda p: (_PARKED_ORDER.get(p.slot, 0), -(p.points or 0.0), p.name))
    return TeamLineup(
        roster_id=m.roster_id,
        team=team.get(m.roster_id, f"Team {m.roster_id}"),
        owner_id=owners.get(m.roster_id),
        points=round(m.points, 2),
        projected=_team_projection(starters),
        projected_pregame=_team_projection(starters, pregame=True),
        starters=starters,
        bench=bench,
    )
