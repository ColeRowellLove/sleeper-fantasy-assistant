"""Roster players as the app shows them: status, game, injury, projection and stat line."""

from __future__ import annotations

from typing import Literal, NamedTuple

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import EMPTY_SLOT
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    PlayerRow,
    RosterRow,
)
from sleeper_assistant.injury_status import WILL_NOT_PLAY
from sleeper_assistant.live_projection import live_projection
from sleeper_assistant.matchup_rank import (
    DefenseTable,
    MatchupRank,
    matchup_rank,
)
from sleeper_assistant.nfl_games import GameInfo
from sleeper_assistant.stat_lines import projected_stat_lines, week_stat_lines

Status = Literal["starter", "bench", "ir", "taxi"]


class InjuryInfo(BaseModel):
    """Injury designation from Sleeper (Out, Doubtful, Questionable, IR, PUP, ...)."""

    status: str
    body_part: str | None = None


class RosterPlayer(BaseModel):
    player_id: str
    name: str
    position: str | None
    team: str | None
    status: Status
    slot: str | None  # lineup slot for starters, e.g. QB, RB, FLEX
    game: GameInfo | None = None  # this week's game (or bye) for the player's NFL team
    injury: InjuryInfo | None = None
    projected: float | None = (
        None  # this week, scored with the league's rules; None = no projection
    )
    points: float | None = None  # this week's actual points once the game has started
    projected_pregame: float | None = None  # the projection frozen before kickoff
    matchup: MatchupRank | None = None  # the opponent's defense rank against his position
    stat_line: str | None = None  # how he did, once his game has started: "18 car, 92 yds, 1 TD"
    stat_line_projected: bool = False  # True when stat_line is what he is projected to do
    owned_pct: float | None = None  # ESPN-wide share of leagues that roster him
    started_pct: float | None = None  # ESPN-wide share of leagues that start him


def load_players(session: Session, player_ids: set[str]) -> dict[str, PlayerRow]:
    rows = session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(player_ids)))
    return {p.player_id: p for p in rows}


# Designations that carry no information for a fantasy manager are hidden.
_HIDDEN_INJURY_STATUSES = {"", "NA"}


def injury_info(players: dict[str, PlayerRow], pid: str) -> InjuryInfo | None:
    p = players.get(pid)
    if p is None or not p.injury_status or p.injury_status in _HIDDEN_INJURY_STATUSES:
        return None
    return InjuryInfo(status=p.injury_status, body_part=p.injury_body_part or None)


def display(players: dict[str, PlayerRow], pid: str) -> tuple[str, str | None, str | None]:
    p = players.get(pid)
    if p is None:
        return pid, None, None
    return p.full_name or pid, p.position, p.team


class Line(NamedTuple):
    text: str
    projected: bool


def week_lines(
    session: Session,
    league: LeagueRow,
    week: int,
    players: dict[str, PlayerRow],
    games: dict[str, GameInfo],
) -> dict[str, Line]:
    """How each player did once his game started, or what he is projected to do before it."""
    started: dict[str, str | None] = {}
    waiting: dict[str, str | None] = {}
    for pid, p in players.items():
        game = games.get(p.team or "")
        if game is None:
            continue
        if game.state in ("live", "final"):
            started[pid] = p.position
        elif game.state == "upcoming" and p.injury_status not in WILL_NOT_PLAY:
            waiting[pid] = p.position  # a forecast for someone ruled out would only mislead
    played = week_stat_lines(session, league.season, week, started, league.scoring_settings)
    planned = projected_stat_lines(session, league.season, week, waiting, league.scoring_settings)
    return {
        **{pid: Line(text, False) for pid, text in played.items()},
        **{pid: Line(text, True) for pid, text in planned.items()},
    }  # the two sets of players never overlap: a game is either started or not


def week_points(session: Session, league_id: str, week: int) -> dict[int, dict[str, float]]:
    """roster_id -> player_id -> the points Sleeper credited that roster's player this week."""
    out: dict[int, dict[str, float]] = {}
    for m in session.scalars(
        select(MatchupRow).where(MatchupRow.league_id == league_id, MatchupRow.week == week)
    ):
        out[m.roster_id] = {
            pid: float(value)
            for pid, value in (m.players_points or {}).items()
            if value is not None
        }
    return out


def points_so_far(game: GameInfo | None, value: float | None) -> float | None:
    """A player's points once his game has started; before that there is nothing to show (not 0)."""
    if value is None or game is None or game.state not in ("live", "final"):
        return None
    return round(value, 2)


def roster_players(  # noqa: PLR0913, PLR0917
    roster: RosterRow,
    players: dict[str, PlayerRow],
    slots: list[str],
    games: dict[str, GameInfo],
    projected: dict[str, float],
    earned: dict[str, float],
    defense: DefenseTable,
    lines: dict[str, Line],
) -> list[RosterPlayer]:
    def make(pid: str, status: Status, slot: str | None = None) -> RosterPlayer:
        name, position, nfl_team = display(players, pid)
        game = games.get(nfl_team) if nfl_team else None
        pregame = projected.get(pid, 0.0)
        scored = points_so_far(game, earned.get(pid))
        return RosterPlayer(
            player_id=pid,
            name=name,
            position=position,
            team=nfl_team,
            status=status,
            slot=slot,
            game=game,
            injury=injury_info(players, pid),
            projected=projection_now(pregame, scored, game),
            projected_pregame=pregame,
            points=scored,
            matchup=matchup_rank(defense, position, game.opponent if game else None),
            stat_line=lines[pid].text if pid in lines else None,
            stat_line_projected=pid in lines and lines[pid].projected,
        )

    out: list[RosterPlayer] = []
    for i, pid in enumerate(roster.starters):
        if pid != EMPTY_SLOT:
            out.append(make(pid, "starter", slots[i] if i < len(slots) else None))

    placed = set(roster.starters) | set(roster.reserve) | set(roster.taxi)
    bench = [make(pid, "bench") for pid in roster.players if pid not in placed]
    bench.sort(key=lambda p: (p.position or "~", p.name))
    out.extend(bench)
    out.extend(make(pid, "ir") for pid in roster.reserve)
    out.extend(make(pid, "taxi") for pid in roster.taxi)
    return out


def projection_now(pregame: float, scored: float | None, game: GameInfo | None) -> float:
    """The projection now: the pre-game one before kickoff, the score once the game is over."""
    return live_projection(
        pregame, scored, game.state if game else None, game.elapsed if game else None
    )
