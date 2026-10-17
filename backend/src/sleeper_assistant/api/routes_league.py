"""Read-only league pages: settings, players, transactions, news, lineups, games and the tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, StringConstraints

from sleeper_assistant.alerts.engine import AlertsView, build_alerts
from sleeper_assistant.api.deps import LeagueDep, SessionDep
from sleeper_assistant.core.league.rankings import Rankings, build_rankings
from sleeper_assistant.core.league.start_sit import (
    MAX_COMPARE,
    BestLineup,
    Comparison,
    best_lineup,
    compare_players,
)
from sleeper_assistant.core.nfl.depth import TEAM_IDS
from sleeper_assistant.core.nfl.team_depth import TeamDepth, build_team_depth
from sleeper_assistant.core.sources.box_score import (
    BoxScore,
    BoxScoreError,
    box_score,
    link_players,
)
from sleeper_assistant.db import (
    RosterRow,
)
from sleeper_assistant.views.games import Games, build_games
from sleeper_assistant.views.lineup_accuracy import LineupAccuracy, build_lineup_accuracy
from sleeper_assistant.views.lineups import Lineups, build_lineups
from sleeper_assistant.views.news import NewsView, build_news
from sleeper_assistant.views.player_detail import PlayerDetail, build_player_detail
from sleeper_assistant.views.players import PlayersResponse, build_players
from sleeper_assistant.views.transactions import TransactionsView, build_transactions
from sleeper_assistant.views.waiver_wire import WaiverWire, build_waiver_wire

router = APIRouter()


class LeagueSettings(BaseModel):
    """Everything Sleeper reports about how the league is set up, as stored (read-only)."""

    league_id: str
    name: str
    season: str
    total_rosters: int
    settings: dict[str, Any]
    scoring_settings: dict[str, float]
    roster_positions: list[str]


@router.get("/api/leagues/{league_id}/settings")
def get_league_settings(row: LeagueDep) -> LeagueSettings:
    """The league's rules, scoring and roster positions exactly as Sleeper provides them."""
    return LeagueSettings(
        league_id=row.league_id,
        name=row.name,
        season=row.season,
        total_rosters=row.total_rosters,
        settings=row.settings,
        scoring_settings={k: float(v) for k, v in row.scoring_settings.items()},
        roster_positions=row.roster_positions,
    )


@router.get("/api/leagues/{league_id}/players")
def get_league_players(
    row: LeagueDep,
    session: SessionDep,
) -> PlayersResponse:
    """Every relevant NFL player as seen through this league (availability, trends, points)."""
    return build_players(session, row)


@router.get("/api/leagues/{league_id}/transactions")
def get_league_transactions(
    row: LeagueDep,
    session: SessionDep,
) -> TransactionsView:
    """The league's latest adds, drops, waiver claims and trades, newest first."""
    return build_transactions(session, row)


@router.get("/api/leagues/{league_id}/news")
def get_league_news(
    row: LeagueDep,
    session: SessionDep,
) -> NewsView:
    """Recent headlines about players and teams, from the configured public feeds."""
    return build_news(session, row)


PlayerId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,12}$")]


@router.get("/api/leagues/{league_id}/players/{player_id}")
def get_player_detail(
    row: LeagueDep,
    player_id: PlayerId,
    session: SessionDep,
) -> PlayerDetail:
    """One player's bio, season, weekly points, projection and past seasons in this league."""
    detail = build_player_detail(session, row, player_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return detail


PlayerIdParam = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]{1,12}$")]
TeamCode = Annotated[str, Path(pattern=r"^[A-Z]{2,3}$")]


@router.get("/api/leagues/{league_id}/teams/{team}")
def get_team_depth(
    row: LeagueDep,
    team: TeamCode,
    session: SessionDep,
) -> TeamDepth:
    """One NFL team's depth chart (offense, defense, special teams) as seen through this league."""
    if team not in TEAM_IDS:
        raise HTTPException(status_code=404, detail="Team not found")
    return build_team_depth(session, row, team)


@router.get("/api/leagues/{league_id}/lineups")
def get_league_lineups(
    row: LeagueDep,
    session: SessionDep,
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> Lineups:
    """Both teams' lineups (starters by slot, bench, points) per matchup for one week."""
    return build_lineups(session, row, week)


@router.get("/api/leagues/{league_id}/start-sit")
def get_start_sit(
    row: LeagueDep,
    session: SessionDep,
    player: Annotated[list[PlayerIdParam], Query(min_length=2, max_length=MAX_COMPARE)],
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> Comparison:
    """Compare two or more players for one lineup spot and say which to start."""
    return compare_players(session, row, player, week)


@router.get("/api/leagues/{league_id}/start-sit/lineup")
def get_best_lineup(
    row: LeagueDep,
    session: SessionDep,
    roster: Annotated[int, Query(ge=1, le=64)],
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> BestLineup:
    """The projected-best lineup for one roster and how it differs from today's starters."""
    result = best_lineup(session, row, roster, week)
    if result is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return result


@router.get("/api/leagues/{league_id}/games")
def get_games(
    row: LeagueDep,
    session: SessionDep,
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> Games:
    """Every NFL game of a week with score, line, conditions and the players in it."""
    return build_games(session, row, week)


@router.get("/api/leagues/{league_id}/games/{week}/{away}/{home}/box")
def get_box_score(
    row: LeagueDep,
    session: SessionDep,
    week: Annotated[int, Path(ge=1, le=18)],
    away: TeamCode,
    home: TeamCode,
) -> BoxScore:
    """The full ESPN box score of one game: every player and every stat category."""
    if away not in TEAM_IDS or home not in TEAM_IDS:
        raise HTTPException(status_code=404, detail="Team not found")
    try:
        box = box_score(row.season, week, home, away)
    except BoxScoreError as error:
        raise HTTPException(status_code=502, detail=f"Box score not available: {error}") from None
    return link_players(session, box.model_copy(deep=True))


@router.get("/api/leagues/{league_id}/alerts")
def get_alerts(
    row: LeagueDep,
    session: SessionDep,
    roster: Annotated[int, Query(ge=1, le=64)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertsView:
    """A team's recent alerts, newest first. Whether they have been read is the viewer's own
    business (kept in their browser), because anyone can open this public page."""
    if session.get(RosterRow, (row.league_id, roster)) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return build_alerts(session, row.league_id, roster, limit)


@router.get("/api/leagues/{league_id}/waiver-wire")
def get_waiver_wire(
    row: LeagueDep,
    session: SessionDep,
    roster: Annotated[int, Query(ge=1, le=64)],
) -> WaiverWire:
    """This waiver cycle's most recommended adds for one team, with the reasons."""
    if session.get(RosterRow, (row.league_id, roster)) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return build_waiver_wire(session, row, roster)


@router.get("/api/leagues/{league_id}/rankings")
def get_rankings(
    row: LeagueDep,
    session: SessionDep,
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
    sources: Annotated[str | None, Query(pattern=r"^[a-z,]{0,80}$")] = None,
) -> Rankings:
    """Weekly player rankings by position: a consensus of the chosen signals, with the spread."""
    chosen = [s for s in (sources or "").split(",") if s]
    return build_rankings(session, row, week, chosen)


@router.get("/api/leagues/{league_id}/accuracy")
def get_lineup_accuracy(
    row: LeagueDep,
    session: SessionDep,
) -> LineupAccuracy:
    """Sit vs start accuracy per team: actual points against the best lineup, finished weeks."""
    return build_lineup_accuracy(session, row)
