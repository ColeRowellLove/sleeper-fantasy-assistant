"""Team stats with league ranks, for the player pop-up and the NFL team page.

Totals come from the weekly stat lines already stored (Sleeper's), summed over a team's players
for completed games, so no extra source is needed. Every number is per game, ranked among the
teams with stats. Rank 1 is always the team doing best at it: the most yards or touchdowns, and for
the stats a defense gives up, the fewest.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import GAME_COMPLETE
from sleeper_assistant.core.nfl.stats_version import season_stats_version
from sleeper_assistant.db import NflGameRow, PlayerRow, PlayerWeekStatsRow
from sleeper_assistant.utils.cache import VersionedCache


@dataclass(frozen=True)
class StatDef:
    key: str
    label: str
    value: Callable[[Mapping[str, float]], float]
    side: str  # "offense", "defense" or "special" (special teams)
    fewer_is_better: bool = False


def _get(key: str) -> Callable[[Mapping[str, float]], float]:
    return lambda stats: float(stats.get(key) or 0.0)


def _sum(*keys: str) -> Callable[[Mapping[str, float]], float]:
    return lambda stats: sum(float(stats.get(k) or 0.0) for k in keys)


# every stat is a team total per game; offense stats are summed over the team's players,
# defense stats come from the team defense's own stat line
STATS: tuple[StatDef, ...] = (
    StatDef("yards", "Total yards per game", _sum("pass_yd", "rush_yd"), "offense"),
    StatDef("pass_yd", "Pass yards per game", _get("pass_yd"), "offense"),
    StatDef("rush_yd", "Rush yards per game", _get("rush_yd"), "offense"),
    StatDef("pass_att", "Pass attempts per game", _get("pass_att"), "offense"),
    StatDef("rush_att", "Rush attempts per game", _get("rush_att"), "offense"),
    StatDef("targets", "Targets per game", _get("rec_tgt"), "offense"),
    StatDef("td", "Touchdowns per game", _sum("pass_td", "rush_td"), "offense"),
    StatDef("pass_td", "Pass touchdowns per game", _get("pass_td"), "offense"),
    StatDef("rush_td", "Rush touchdowns per game", _get("rush_td"), "offense"),
    StatDef("fga", "Field goal attempts per game", _get("fga"), "special"),
    StatDef("fgm", "Field goals made per game", _get("fgm"), "special"),
    StatDef("xpm", "Extra points made per game", _get("xpm"), "special"),
    StatDef("pts_allow", "Points allowed per game", _get("pts_allow"), "defense", True),
    StatDef("yds_allow", "Yards allowed per game", _get("yds_allow"), "defense", True),
    StatDef("sack", "Sacks per game", _get("sack"), "defense"),
    StatDef("takeaways", "Takeaways per game", _sum("int", "fum_rec"), "defense"),
    StatDef("def_td", "Defensive touchdowns per game", _get("def_td"), "defense"),
)
_BY_KEY = {s.key: s for s in STATS}

# the stats worth showing next to a player of each position
BY_POSITION: dict[str, tuple[str, ...]] = {
    "QB": ("yards", "pass_yd", "pass_att", "pass_td", "td"),
    "RB": ("yards", "rush_yd", "rush_att", "td", "rush_td"),
    "WR": ("yards", "pass_yd", "targets", "pass_td", "td"),
    "TE": ("yards", "pass_yd", "targets", "pass_td", "td"),
    "K": ("td", "fga", "yards"),
    "DEF": ("pts_allow", "yds_allow", "sack", "takeaways", "def_td"),
}


class TeamStat(BaseModel):
    key: str
    label: str
    side: str  # "offense", "defense" or "special"
    value: float  # per game
    rank: int  # 1 = best of `teams`
    teams: int
    games: int


TeamStatTable = dict[str, dict[str, TeamStat]]  # team -> stat key -> value and rank

_CACHE: VersionedCache[str, TeamStatTable] = VersionedCache()


def reset_cache() -> None:
    _CACHE.clear()


def build_team_stats(session: Session, season: str) -> TeamStatTable:
    """Every team's per-game stats and ranks, rebuilt only when games or stats change."""
    version = season_stats_version(session, season)
    return _CACHE.get(season, version, lambda: _build(session, season))


def _build(session: Session, season: str) -> TeamStatTable:
    finished = {
        (team, g.week)
        for g in session.scalars(
            select(NflGameRow).where(
                NflGameRow.season == season, NflGameRow.status == GAME_COMPLETE
            )
        )
        for team in (g.home, g.away)
    }
    position_of = {
        pid: pos for pid, pos in session.execute(select(PlayerRow.player_id, PlayerRow.position))
    }
    totals: dict[tuple[str, str], float] = defaultdict(float)  # (team, stat key) -> total
    weeks: dict[str, set[int]] = defaultdict(set)
    for pid, team, week, stats in session.execute(
        select(
            PlayerWeekStatsRow.player_id,
            PlayerWeekStatsRow.team,
            PlayerWeekStatsRow.week,
            PlayerWeekStatsRow.stats,
        ).where(PlayerWeekStatsRow.season == season)
    ):
        if not team or (team, week) not in finished:
            continue  # a game still on, or one with no known team
        weeks[team].add(week)
        is_defense = position_of.get(pid) == "DEF"
        for stat in STATS:
            if (stat.side == "defense") == is_defense:
                totals[(team, stat.key)] += stat.value(stats)

    table: TeamStatTable = {team: {} for team in weeks}
    for stat in STATS:
        per_game = {team: totals[(team, stat.key)] / len(played) for team, played in weeks.items()}
        for team, value in per_game.items():
            better = (
                sum(1 for o in per_game.values() if o < value)
                if stat.fewer_is_better
                else sum(1 for o in per_game.values() if o > value)
            )
            table[team][stat.key] = TeamStat(
                key=stat.key,
                label=stat.label,
                side=stat.side,
                value=round(value, 1),
                rank=1 + better,
                teams=len(per_game),
                games=len(weeks[team]),
            )
    return table


def stats_for_position(
    table: TeamStatTable, team: str | None, position: str | None
) -> list[TeamStat]:
    """The stats that matter for a position, for a player's team. Empty without data."""
    if not team or not position or team not in table:
        return []
    return [table[team][k] for k in BY_POSITION.get(position, ()) if k in table[team]]


def all_team_stats(table: TeamStatTable, team: str) -> list[TeamStat]:
    """Every stat for the team page, offense first."""
    row = table.get(team, {})
    return [row[s.key] for s in STATS if s.key in row]
