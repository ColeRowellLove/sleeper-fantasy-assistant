"""The Games tab: every NFL game of a week with its score, line and conditions, and the players.

Each game carries the players from both teams who matter in this league: anyone with a stat line in
the game, and anyone a fantasy team in the league rosters (so an upcoming game still shows whose
players are in it). Points use the league's own scoring. The page puts the viewer's games first and
highlights their players, so every player names the roster that owns them.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

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
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerWeekStatsRow,
    RosterRow,
)
from sleeper_assistant.players_view import _name
from sleeper_assistant.projections import score_projection, score_stats
from sleeper_assistant.stat_lines import stat_line

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
# the stat lines the page lays out, by Sleeper's own names; anything else is left out
STAT_KEYS = (
    "pass_cmp", "pass_att", "pass_yd", "pass_td", "pass_int", "rush_att", "rush_yd", "rush_td",
    "rec_tgt", "rec", "rec_yd", "rec_td", "fum_lost", "fgm", "fga", "xpm", "xpa", "sack", "int",
    "fum_rec", "def_td", "pts_allow",
)  # fmt: skip
# before kickoff, the best-projected players of each position are shown for each team besides the
# ones on a fantasy roster (a few per position, so a kicker and a defense are never crowded out)
PROJECTED_PER_POSITION = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}


def _numbers(stats: Mapping[str, object]) -> dict[str, float]:
    """The finite numbers of a stored stat line; a null, text or NaN value is dropped, not fatal."""
    return {
        k: float(v)
        for k, v in stats.items()
        if isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
    }


class GamePlayer(BaseModel):
    player_id: str
    name: str
    position: str
    team: str  # the NFL team he plays for in this game
    injury: InjuryInfo | None = None
    owner_roster_id: int | None = None  # None means available in this league
    owner_team: str | None = None
    points: float | None = None  # this game's fantasy points once he has stats
    stat_line: str | None = None
    stats: dict[str, float] = {}  # the stat line (or the projected line before he has one)
    projected: bool = False  # True when ``stats`` and ``points`` are projections, not play


class GameCard(BaseModel):
    game_id: str
    week: int
    home: str
    away: str
    game: GameInfo  # from the home team's side: score, state, clock, line and conditions
    players: list[GamePlayer]  # both teams; owned players first, then by points


class Games(BaseModel):
    league_id: str
    week: int | None
    current_week: int | None
    weeks: list[int]
    games: list[GameCard]  # kickoff order


def build_games(session: Session, league: LeagueRow, week: int | None = None) -> Games:
    season = league.season
    now = current_week(session, season)
    all_games = list(session.scalars(select(NflGameRow).where(NflGameRow.season == season)))
    weeks = sorted({g.week for g in all_games})
    chosen = week if week in weeks else now
    if chosen is None:
        return Games(league_id=league.league_id, week=None, current_week=now, weeks=weeks, games=[])

    games = sorted(
        (g for g in all_games if g.week == chosen),
        key=lambda g: (g.kickoff is None, g.kickoff, g.game_date or "", g.home),
    )
    info = games_for_week(session, season, chosen)
    teams = {t for g in games for t in (g.home, g.away)}

    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    team_name, _ = _team_names(session, rosters)
    owner = {pid: r.roster_id for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]}

    # stored lines come from Sleeper's JSON: keep only the finite numbers (a null is not fatal)
    cleaned = {
        row.player_id: _numbers(row.stats)
        for row in session.scalars(
            select(PlayerWeekStatsRow).where(
                PlayerWeekStatsRow.season == season, PlayerWeekStatsRow.week == chosen
            )
        )
    }
    stats = {pid: line for pid, line in cleaned.items() if line.get("gp") is None or line["gp"] > 0}
    upcoming = {t for t in teams if t in info and info[t].state == "upcoming"}
    # projections stand in only before kickoff, so a week with no game left to play reads none
    projections = (
        {
            row.player_id: row.stats
            for row in session.scalars(
                select(PlayerProjectionRow).where(
                    PlayerProjectionRow.season == season, PlayerProjectionRow.week == chosen
                )
            )
        }
        if upcoming
        else {}
    )
    candidates = list(
        session.scalars(
            select(PlayerRow).where(
                PlayerRow.team.in_(teams),
                PlayerRow.position.in_(POSITIONS),
            )
        )
    )
    by_team: dict[str, list[GamePlayer]] = {t: [] for t in teams}
    # before a player has a line, the most projected of each team are worth showing
    wanted = {p.player_id for p in candidates if p.team in upcoming}  # score only who may show
    scored = {
        pid: score_projection(_numbers(line), league.scoring_settings)
        for pid, line in projections.items()
        if pid in wanted
    }
    groups: dict[tuple[str, str], list[PlayerRow]] = {}
    for p in candidates:  # one pass: (team, position) -> the unrostered players with a projection
        if p.team in upcoming and p.player_id in scored and p.player_id not in owner:
            groups.setdefault((p.team, p.position or ""), []).append(p)
    top_projected: set[str] = set()
    for (_team, position), members in groups.items():
        members.sort(key=lambda p: (-scored[p.player_id], p.player_id))
        top_projected |= {p.player_id for p in members[: PROJECTED_PER_POSITION.get(position, 0)]}
    for p in candidates:
        if p.team is None:
            continue
        if (
            p.player_id not in stats
            and p.player_id not in owner
            and p.player_id not in top_projected
        ):
            continue
        line = stats.get(p.player_id)
        # a projection stands in only before the game: after kickoff no line means he did not play
        projected_line = projections.get(p.player_id) if not line and p.team in upcoming else None
        roster_id = owner.get(p.player_id)
        shown_stats = _numbers(line or projected_line or {})
        by_team[p.team].append(
            GamePlayer(
                player_id=p.player_id,
                name=_name(p),
                position=p.position or "",
                team=p.team,
                injury=_injury({p.player_id: p}, p.player_id),
                owner_roster_id=roster_id,
                owner_team=team_name.get(roster_id) if roster_id is not None else None,
                points=(
                    score_stats(line, league.scoring_settings)
                    if line
                    else (scored.get(p.player_id) if projected_line else None)
                ),
                stat_line=stat_line(p.position, line, league.scoring_settings) if line else None,
                stats={k: shown_stats[k] for k in STAT_KEYS if k in shown_stats},
                projected=line is None and projected_line is not None,
            )
        )

    cards: list[GameCard] = []
    for g in games:
        game = info.get(g.home)
        if game is None:
            continue  # a status we do not understand: show nothing rather than a guess
        players = [*by_team.get(g.home, []), *by_team.get(g.away, [])]
        players.sort(key=lambda p: (p.owner_roster_id is None, -(p.points or 0.0), p.name))
        cards.append(
            GameCard(game_id=g.game_id, week=g.week, home=g.home, away=g.away, game=game,
                     players=players)
        )  # fmt: skip
    return Games(
        league_id=league.league_id, week=chosen, current_week=now, weeks=weeks, games=cards
    )
