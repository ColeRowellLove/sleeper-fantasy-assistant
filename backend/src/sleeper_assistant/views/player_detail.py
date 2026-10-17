"""One player's pop-up: bio, season so far, week-by-week points, projection and past seasons.

Points are always scored with the connected league's own rules, from the same stat lines the
Players tab uses, so every category counts (a receiver's rushing yards, a quarterback's catches).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import GAME_COMPLETE
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.league.team_names import team_names
from sleeper_assistant.core.models.games import GameInfo
from sleeper_assistant.core.models.injury import InjuryInfo
from sleeper_assistant.core.models.matchup import MatchupRank
from sleeper_assistant.core.nfl.injury_status import injury_info
from sleeper_assistant.core.nfl.matchup_rank import DefenseTable, build_defense_table, matchup_rank
from sleeper_assistant.core.nfl.nfl_games import current_week, games_for_week
from sleeper_assistant.core.nfl.team_depth import TeamDepth, build_team_depth
from sleeper_assistant.core.nfl.team_stats import TeamStat, build_team_stats, stats_for_position
from sleeper_assistant.core.scoring.projections import score_projection, score_stats
from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerSeasonStatsRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
)
from sleeper_assistant.views.news import NewsEntryView, player_news
from sleeper_assistant.views.player_history import HistoryEvent, build_history

# volume numbers worth showing even when the league does not score them directly
_MAX_BYES = 2  # a team has one bye; more gaps than this means the schedule is not fully loaded
_VOLUME_KEYS = ("pass_att", "pass_cmp", "rush_att", "rec_tgt", "fga", "pts_allow")


class WeekLine(BaseModel):
    week: int
    team: str | None = None  # the NFL team he played for that week
    opponent: str | None = None
    home: bool | None = None
    points: float
    stats: dict[str, float]  # the stats that earned (or cost) points this week
    projected: float | None = None  # what was projected before kickoff; None = none was stored
    final: bool = (
        False  # the game is over, so the points can fairly be compared with the projection
    )
    rank: int | None = None  # his rank among players at his position that week (1 = best)


class ScheduleWeek(BaseModel):
    """One week of his team's season: who it plays, or that it is on a bye."""

    week: int
    opponent: str | None = None
    home: bool | None = None
    bye: bool = False
    matchup: MatchupRank | None = None  # the opponent's rank against his position


class SeasonLine(BaseModel):
    season: str
    games: int
    points: float
    rank: int | None = None  # within position that season
    teams: list[str] = []  # teams he played for that season, in order
    log: list[WeekLine] = []  # game by game, with opponents when the schedule is stored


class ProjectedLine(BaseModel):
    week: int
    points: float
    stats: dict[str, float]  # projected catches, yards, touchdowns and so on


class SeasonSummary(BaseModel):
    points: float
    games: int
    average: float | None = None
    rank: int | None = None  # within position, by points under this league's scoring


class PlayerDetail(BaseModel):
    player_id: str
    name: str
    position: str | None
    team: str | None
    injury: InjuryInfo | None = None
    game: GameInfo | None = None
    matchup: MatchupRank | None = None  # this week's opponent against his position
    team_stats: list[TeamStat] = []  # his team's numbers that matter for his position, ranked
    depth: TeamDepth | None = None  # his team's depth chart, for the Team tab
    bio: dict[str, Any] | None = None
    owner_roster_id: int | None = None
    owner_team: str | None = None
    owner_manager: str | None = None  # the owning manager's Sleeper username
    league_id: str | None = None  # so the page can link to the owning team's roster
    adds: int | None = None
    drops: int | None = None
    owned_pct: float | None = None  # ESPN-wide share of leagues that roster the player
    started_pct: float | None = None  # ESPN-wide share of leagues that start the player
    season: SeasonSummary
    projected: ProjectedLine | None = None
    schedule: list[ScheduleWeek] = []  # every week of the season, for the game log
    news: list[NewsEntryView] = []  # recent headlines that name him
    history: list[HistoryEvent] = []  # his adds and drops in this league, newest first
    weeks: list[WeekLine]
    past_seasons: list[SeasonLine]


def _game_log(  # noqa: PLR0913 - the season, the player and how to score him are all needed
    session: Session,
    season: str,
    player_id: str,
    scoring: Mapping[str, float],
    projections: Mapping[int, float] | None = None,
    *,
    past: bool = False,
) -> tuple[list[WeekLine], int]:
    """One season's games for a player, each with the team he played for and the opponent.

    The team is the one recorded for that week, so a player traded mid-season shows both teams
    and each game names the right opponent. A past season's games are all final.
    """
    rows = session.scalars(
        select(PlayerWeekStatsRow)
        .where(PlayerWeekStatsRow.season == season, PlayerWeekStatsRow.player_id == player_id)
        .order_by(PlayerWeekStatsRow.week)
    ).all()
    schedule: dict[str, dict[int, tuple[str, bool, bool]]] = {}
    lines: list[WeekLine] = []
    for row in rows:
        if row.stats.get("gp", 1.0) <= 0:
            continue  # he did not play that week: no game to list (not a game of zero points)
        team = row.team or ""
        if team not in schedule:  # one query per team he played for, not one per game
            schedule[team] = _opponents(session, season, row.team)
        opponents = schedule[team]
        opponent, home, over = opponents.get(row.week, (None, None, False))
        lines.append(
            WeekLine(
                week=row.week,
                team=row.team,
                opponent=opponent,
                home=home,
                final=over or past,
                points=score_stats(row.stats, scoring),
                stats=display_stats(row.stats, scoring),
                projected=(projections or {}).get(row.week),
            )
        )
    games = sum(1 for row in rows if row.stats.get("gp", 1.0) > 0)
    return lines, games


def display_stats(stats: Mapping[str, float], scoring: Mapping[str, float]) -> dict[str, float]:
    """Stats that matter for this league: those that score or cost points, plus basic volume."""
    keep = {k: v for k, v in stats.items() if v and (scoring.get(k) or k in _VOLUME_KEYS)}
    return {k: round(v, 2) for k, v in keep.items()}


def _rank(points: float, same_position: list[float]) -> int:
    """1 + how many players at the position scored more (tied players share a rank)."""
    return 1 + sum(1 for other in same_position if other > points)


def _opponents(
    session: Session, season: str, team: str | None
) -> dict[int, tuple[str, bool, bool]]:
    """Week -> (opponent, playing at home, game is over) for a team's games this season."""
    if not team:
        return {}
    games = session.scalars(
        select(NflGameRow).where(
            NflGameRow.season == season, (NflGameRow.home == team) | (NflGameRow.away == team)
        )
    )
    return {
        g.week: (
            (g.away, True, g.status == GAME_COMPLETE)
            if g.home == team
            else (g.home, False, g.status == GAME_COMPLETE)
        )
        for g in games
    }


def _schedule(
    session: Session, season: str, player: PlayerRow, defense: DefenseTable
) -> list[ScheduleWeek]:
    """Every week of the season for his team: the opponent and how hard it is, or a bye."""
    weeks = sorted(
        {w for (w,) in session.execute(select(NflGameRow.week).where(NflGameRow.season == season))}
    )
    games = _opponents(session, season, player.team)
    if not weeks or not games:
        return []  # without his team's games we cannot tell a bye from missing data
    if sum(1 for w in weeks if w not in games) > _MAX_BYES:
        return []  # that many gaps is missing data (or a team-code mismatch), not byes
    out: list[ScheduleWeek] = []
    for week in weeks:
        if week not in games:
            out.append(ScheduleWeek(week=week, bye=True))
            continue
        opponent, home, _over = games[week]
        out.append(
            ScheduleWeek(
                week=week,
                opponent=opponent,
                home=home,
                matchup=matchup_rank(defense, player.position, opponent),
            )
        )
    return out


def _expected_points(
    session: Session, season: str, player_id: str, scoring: Mapping[str, float]
) -> dict[int, float]:
    """His stored projection for each week, scored with the league's rules."""
    return {
        row.week: score_projection(row.stats, scoring)
        for row in session.scalars(
            select(PlayerProjectionRow).where(
                PlayerProjectionRow.season == season, PlayerProjectionRow.player_id == player_id
            )
        )
    }


def _rank_in_position(
    session: Session,
    season: str,
    player: PlayerRow,
    scoring: Mapping[str, float],
    weeks: list[WeekLine],
) -> tuple[int | None, dict[str, str | None]]:
    """His season rank among his position (and each game's rank), scored with the same rules.

    Fills ``rank`` on each week line; returns the season rank and every player's position.
    """
    position_of = {
        pid: pos for pid, pos in session.execute(select(PlayerRow.player_id, PlayerRow.position))
    }
    season_totals: dict[str, float] = defaultdict(float)
    week_peers: dict[int, list[float]] = defaultdict(list)  # week -> points of his position
    for pid, week, stats in session.execute(
        select(
            PlayerWeekStatsRow.player_id, PlayerWeekStatsRow.week, PlayerWeekStatsRow.stats
        ).where(PlayerWeekStatsRow.season == season)
    ):
        points = score_stats(stats, scoring)
        season_totals[pid] += points
        if player.position and position_of.get(pid) == player.position and stats.get("gp", 1) > 0:
            week_peers[week].append(points)
    for line in weeks:
        line.rank = _rank(line.points, week_peers.get(line.week, [])) if week_peers else None
    rank = None
    if weeks and player.position:
        peers = [t for pid, t in season_totals.items() if position_of.get(pid) == player.position]
        rank = _rank(season_totals.get(player.player_id, 0.0), peers)
    return rank, position_of


def _this_weeks_projection(
    session: Session, season: str, week: int | None, player_id: str, scoring: Mapping[str, float]
) -> ProjectedLine | None:
    if not week:
        return None
    row = session.get(PlayerProjectionRow, (season, week, player_id))
    if row is None:
        return None
    return ProjectedLine(
        week=week,
        points=score_projection(row.stats, scoring),
        stats=display_stats(row.stats, scoring),
    )


def build_player_detail(session: Session, league: LeagueRow, player_id: str) -> PlayerDetail | None:
    """The pop-up for one player in this league, or None when Sleeper has no such player."""
    player = session.get(PlayerRow, player_id)
    if player is None:
        return None
    scoring = league.scoring_settings
    season = league.season

    rosters = league_rosters(session, league.league_id)
    team_name, manager_name = team_names(session, rosters)
    owner = next(
        (r.roster_id for r in rosters if player_id in [*r.players, *r.reserve, *r.taxi]), None
    )
    expected = _expected_points(session, season, player_id, scoring)
    weeks, games = _game_log(session, season, player_id, scoring, expected)
    total = round(sum(w.points for w in weeks), 2)
    rank, position_of = _rank_in_position(session, season, player, scoring, weeks)

    week_now = current_week(session, season)
    trend = session.get(PlayerTrendRow, player_id)
    espn = session.get(PlayerOwnershipRow, player_id)
    game = games_for_week(session, season, week_now).get(player.team or "") if week_now else None
    defense = build_defense_table(session, season, scoring)
    return PlayerDetail(
        player_id=player_id,
        name=player_name(player),
        position=player.position,
        team=player.team,
        injury=injury_info({player_id: player}, player_id),
        game=game,
        depth=build_team_depth(session, league, player.team, rosters) if player.team else None,
        team_stats=stats_for_position(
            build_team_stats(session, season), player.team, player.position
        ),
        matchup=matchup_rank(defense, player.position, game.opponent if game else None),
        bio=player.bio,
        owner_roster_id=owner,
        owner_team=team_name.get(owner) if owner is not None else None,
        owner_manager=manager_name.get(owner) if owner is not None else None,
        league_id=league.league_id,
        adds=trend.adds if trend else None,
        drops=trend.drops if trend else None,
        owned_pct=espn.owned if espn else None,
        started_pct=espn.started if espn else None,
        season=SeasonSummary(
            points=total,
            games=games,
            average=round(total / games, 2) if games else None,
            rank=rank,
        ),
        projected=_this_weeks_projection(session, season, week_now, player_id, scoring),
        schedule=_schedule(session, season, player, defense),
        news=player_news(session, player_id),
        history=build_history(session, league, player_id, rosters),
        weeks=weeks,
        past_seasons=_past_seasons(session, scoring, player, position_of),
    )


def _past_seasons(
    session: Session,
    scoring: Mapping[str, float],
    player: PlayerRow,
    position_of: Mapping[str, str | None],
) -> list[SeasonLine]:
    rows = session.scalars(select(PlayerSeasonStatsRow)).all()
    seasons = sorted({r.season for r in rows}, reverse=True)
    out: list[SeasonLine] = []
    for season in seasons:
        scored = {r.player_id: score_stats(r.stats, scoring) for r in rows if r.season == season}
        mine = next(
            (r for r in rows if r.season == season and r.player_id == player.player_id), None
        )
        if mine is None:
            continue  # the player did not play that season
        peers = [pts for pid, pts in scored.items() if position_of.get(pid) == player.position]
        log, _ = _game_log(session, season, player.player_id, scoring, past=True)
        out.append(
            SeasonLine(
                season=season,
                games=mine.games,
                points=scored[player.player_id],
                rank=_rank(scored[player.player_id], peers) if player.position else None,
                teams=mine.teams or sorted({w.team for w in log if w.team}),
                log=log,
            )
        )
    return out
