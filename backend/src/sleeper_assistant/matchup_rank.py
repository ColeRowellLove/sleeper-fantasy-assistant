"""How hard an opponent is for a position, from fantasy points in completed games.

For QB, RB, WR, TE and K it totals the points all players at that position scored against each
NFL defense and ranks the teams by points allowed per game. For a team defense (DEF) the measure
is the opposing offense: the points that team's QB, RB, WR, TE and K scored per game, since that
is what a defense is up against. Both are scored with the connected league's own rules (never
hard-coded), and rank 1 is always the best matchup for the player: ``vs JAX (3rd)`` says
Jacksonville gives up the 3rd most points to that position, and for a defense the offense with
the 3rd fewest points scored.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import GAME_COMPLETE, PLAYER_POSITIONS
from sleeper_assistant.db import NflGameRow, PlayerRow, PlayerWeekStatsRow
from sleeper_assistant.projections import score_stats
from sleeper_assistant.stats_version import season_stats_version

DEFENSE = "DEF"


class DefenseRank(BaseModel):
    """One opponent against one position. Rank 1 is always the best matchup for the player."""

    rank: int
    teams: int  # how many teams are ranked, so "3rd of 32" can be said
    points: float  # fantasy points per game: allowed to the position, or scored by the offense
    games: int  # completed games counted
    # "defense": ranked by points allowed to the position (most first);
    # "offense": a team defense's opponent, ranked by points scored (fewest first)
    side: Literal["defense", "offense"] = "defense"


class MatchupRank(DefenseRank):
    """A player's opponent this week and how that defense ranks against his position."""

    opponent: str


# (defense team, position) -> rank
DefenseTable = dict[tuple[str, str], DefenseRank]


_CACHE: dict[tuple[str, str], tuple[tuple[int, int], DefenseTable]] = {}


def reset_cache() -> None:
    _CACHE.clear()


def build_defense_table(
    session: Session, season: str, scoring: Mapping[str, float]
) -> DefenseTable:
    """Rank every defense against each position from the season's completed games.

    The table only changes when a game completes or stats are stored, so it is kept per season
    and scoring and rebuilt when the number of completed games or stored stat rows changes.
    """
    version = season_stats_version(session, season)
    key = (season, repr(sorted(scoring.items())))
    cached = _CACHE.get(key)
    if cached is not None and cached[0] == version:
        return cached[1]
    table = _build_defense_table(session, season, scoring)
    _CACHE[key] = (version, table)
    return table


def _build_defense_table(
    session: Session, season: str, scoring: Mapping[str, float]
) -> DefenseTable:
    opponent_of: dict[tuple[str, int], str] = {}
    for g in session.scalars(
        select(NflGameRow).where(NflGameRow.season == season, NflGameRow.status == GAME_COMPLETE)
    ):
        opponent_of[(g.home, g.week)] = g.away
        opponent_of[(g.away, g.week)] = g.home

    position_of = {
        pid: pos
        for pid, pos in session.execute(select(PlayerRow.player_id, PlayerRow.position))
        if pos in PLAYER_POSITIONS
    }
    allowed: dict[tuple[str, str], float] = defaultdict(float)
    scored: dict[str, float] = defaultdict(float)  # an offense's own fantasy points
    faced: set[tuple[str, int]] = set()  # (defense, week) with stats loaded: games that count
    attacked: set[tuple[str, int]] = set()  # (offense, week) with stats loaded
    for pid, team, week, stats in session.execute(
        select(
            PlayerWeekStatsRow.player_id,
            PlayerWeekStatsRow.team,
            PlayerWeekStatsRow.week,
            PlayerWeekStatsRow.stats,
        ).where(PlayerWeekStatsRow.season == season)
    ):
        position = position_of.get(pid)
        opponent = opponent_of.get((team or "", week))
        if opponent is None or not team:
            continue  # a game not finished yet
        faced.add((opponent, week))  # stats are in for this game, so it counts as a game
        attacked.add((team, week))
        played = stats.get("gp")
        if position is None or (played is not None and played <= 0):
            continue  # not a ranked position, or he did not play
        points = score_stats(stats, scoring)
        allowed[(opponent, position)] += points
        scored[team] += points

    defense_games: dict[str, int] = defaultdict(int)
    for team, _ in faced:
        defense_games[team] += 1
    offense_games: dict[str, int] = defaultdict(int)
    for team, _ in attacked:
        offense_games[team] += 1

    table: DefenseTable = {}
    for position in PLAYER_POSITIONS:
        per_game = {
            team: allowed.get((team, position), 0.0) / n for team, n in defense_games.items()
        }
        for team, value in per_game.items():
            table[(team, position)] = DefenseRank(
                rank=1 + sum(1 for other in per_game.values() if other > value),
                teams=len(per_game),
                points=round(value, 1),
                games=defense_games[team],
            )
    # a team defense is up against the opposing offense: fewest points scored is the best matchup
    offense = {team: scored.get(team, 0.0) / n for team, n in offense_games.items()}
    for team, value in offense.items():
        table[(team, DEFENSE)] = DefenseRank(
            rank=1 + sum(1 for other in offense.values() if other < value),
            teams=len(offense),
            points=round(value, 1),
            games=offense_games[team],
            side="offense",
        )
    return table


def matchup_rank(
    table: DefenseTable, position: str | None, opponent: str | None
) -> MatchupRank | None:
    """The opponent's rank against a position, or None (bye, unknown opponent, no games)."""
    if not position or not opponent:
        return None
    rank = table.get((opponent, position))
    if rank is None:
        return None
    return MatchupRank(opponent=opponent, **rank.model_dump())
