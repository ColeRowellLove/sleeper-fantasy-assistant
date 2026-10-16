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
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerSeasonStatsRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    RosterRow,
)
from sleeper_assistant.matchup_rank import MatchupRank, build_defense_table, matchup_rank
from sleeper_assistant.players_view import _name
from sleeper_assistant.projections import score_projection, score_stats

# volume numbers worth showing even when the league does not score them directly
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
    weeks: list[WeekLine]
    past_seasons: list[SeasonLine]


def _game_log(  # noqa: PLR0913
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
        opponents = schedule.setdefault(row.team or "", _opponents(session, season, row.team))
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
            (g.away, True, g.status == "complete")
            if g.home == team
            else (g.home, False, g.status == "complete")
        )
        for g in games
    }


def build_player_detail(session: Session, league: LeagueRow, player_id: str) -> PlayerDetail | None:
    """The pop-up for one player in this league, or None when Sleeper has no such player."""
    player = session.get(PlayerRow, player_id)
    if player is None:
        return None
    scoring = league.scoring_settings
    season = league.season

    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    team_name, manager_name = _team_names(session, rosters)
    owner = next(
        (r.roster_id for r in rosters if player_id in [*r.players, *r.reserve, *r.taxi]), None
    )

    expected = {
        row.week: score_projection(row.stats, scoring)
        for row in session.scalars(
            select(PlayerProjectionRow).where(
                PlayerProjectionRow.season == season, PlayerProjectionRow.player_id == player_id
            )
        )
    }
    weeks, games = _game_log(session, season, player_id, scoring, expected)
    total = round(sum(w.points for w in weeks), 2)
    weekly = bool(weeks)

    # rank among everyone at this position this season, scored with the same rules
    position_of = {
        pid: pos for pid, pos in session.execute(select(PlayerRow.player_id, PlayerRow.position))
    }
    season_totals: dict[str, float] = defaultdict(float)
    for pid, stats in session.execute(
        select(PlayerWeekStatsRow.player_id, PlayerWeekStatsRow.stats).where(
            PlayerWeekStatsRow.season == season
        )
    ):
        season_totals[pid] += score_stats(stats, scoring)
    rank = None
    if weekly and player.position:
        peers = [t for pid, t in season_totals.items() if position_of.get(pid) == player.position]
        rank = _rank(season_totals.get(player_id, 0.0), peers)

    week_now = current_week(session, season)
    projected = None
    if week_now:
        row = session.get(PlayerProjectionRow, (season, week_now, player_id))
        if row is not None:
            projected = ProjectedLine(
                week=week_now,
                points=score_projection(row.stats, scoring),
                stats=display_stats(row.stats, scoring),
            )

    trend = session.get(PlayerTrendRow, player_id)
    espn = session.get(PlayerOwnershipRow, player_id)
    game = games_for_week(session, season, week_now).get(player.team or "") if week_now else None
    return PlayerDetail(
        player_id=player_id,
        name=_name(player),
        position=player.position,
        team=player.team,
        injury=_injury({player_id: player}, player_id),
        game=game,
        matchup=matchup_rank(
            build_defense_table(session, season, scoring),
            player.position,
            game.opponent if game else None,
        ),
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
        projected=projected,
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
