"""The Games tab: every NFL game of a week with its score, line and conditions, and the players.

Each game carries the players from both teams who matter in this league: anyone with a stat line in
the game, and anyone a fantasy team in the league rosters (so an upcoming game still shows whose
players are in it). Points use the league's own scoring. The page puts the viewer's games first and
highlights their players, so every player names the roster that owns them.
"""

from __future__ import annotations

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
PROJECTED_PER_TEAM = (
    10  # projected players shown per team before kickoff, besides those on a roster
)


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

    stats = {
        (row.player_id): row.stats
        for row in session.scalars(
            select(PlayerWeekStatsRow).where(
                PlayerWeekStatsRow.season == season, PlayerWeekStatsRow.week == chosen
            )
        )
        if row.stats.get("gp") is None or row.stats["gp"] > 0
    }
    projections = {
        row.player_id: row.stats
        for row in session.scalars(
            select(PlayerProjectionRow).where(
                PlayerProjectionRow.season == season, PlayerProjectionRow.week == chosen
            )
        )
    }
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
    scored = {
        pid: score_projection(line, league.scoring_settings) for pid, line in projections.items()
    }
    top_projected: dict[str, set[str]] = {t: set() for t in teams}
    pool = [p for p in candidates if p.team is not None and p.player_id in scored]
    for team in teams:
        best = sorted((p for p in pool if p.team == team), key=lambda p: -scored[p.player_id])
        top_projected[team] = {p.player_id for p in best[:PROJECTED_PER_TEAM]}
    for p in candidates:
        if p.team is None:
            continue
        shown = (
            p.player_id in stats
            or p.player_id in owner
            or p.player_id in top_projected.get(p.team, set())
        )
        if not shown:
            continue
        line = stats.get(p.player_id)
        projected_line = None if line else projections.get(p.player_id)
        roster_id = owner.get(p.player_id)
        shown_stats = line or projected_line or {}
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
                    score_stats(line, league.scoring_settings) if line else scored.get(p.player_id)
                ),
                stat_line=stat_line(p.position, line, league.scoring_settings) if line else None,
                stats={k: float(shown_stats[k]) for k in STAT_KEYS if shown_stats.get(k)},
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
