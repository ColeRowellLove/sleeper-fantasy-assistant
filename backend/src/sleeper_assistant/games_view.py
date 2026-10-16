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
from sleeper_assistant.db import LeagueRow, NflGameRow, PlayerRow, PlayerWeekStatsRow, RosterRow
from sleeper_assistant.players_view import _name
from sleeper_assistant.projections import score_stats
from sleeper_assistant.stat_lines import stat_line

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


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
    candidates = session.scalars(
        select(PlayerRow).where(
            PlayerRow.team.in_(teams),
            PlayerRow.position.in_(POSITIONS),
        )
    )
    by_team: dict[str, list[GamePlayer]] = {t: [] for t in teams}
    for p in candidates:
        if p.team is None or (p.player_id not in stats and p.player_id not in owner):
            continue
        line = stats.get(p.player_id)
        roster_id = owner.get(p.player_id)
        by_team[p.team].append(
            GamePlayer(
                player_id=p.player_id,
                name=_name(p),
                position=p.position or "",
                team=p.team,
                injury=_injury({p.player_id: p}, p.player_id),
                owner_roster_id=roster_id,
                owner_team=team_name.get(roster_id) if roster_id is not None else None,
                points=score_stats(line, league.scoring_settings) if line else None,
                stat_line=stat_line(p.position, line, league.scoring_settings) if line else None,
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
