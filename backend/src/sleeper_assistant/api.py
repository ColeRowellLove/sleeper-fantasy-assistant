"""FastAPI application."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator
from datetime import timedelta
from functools import lru_cache
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Response
from pydantic import BaseModel, StringConstraints, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from sleeper_assistant import __version__
from sleeper_assistant.crosswalk import build_crosswalk
from sleeper_assistant.dashboard import Dashboard, Lineups, build_dashboard, build_lineups
from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerRow,
    as_utc,
    make_engine,
    make_session_factory,
    utcnow,
)
from sleeper_assistant.depth import TEAM_IDS
from sleeper_assistant.ingest import sync_league, sync_players, sync_schedule
from sleeper_assistant.lineup_accuracy import LineupAccuracy, build_lineup_accuracy
from sleeper_assistant.player_detail import PlayerDetail, build_player_detail
from sleeper_assistant.players_view import PlayersResponse, build_players
from sleeper_assistant.rankings import Rankings, build_rankings
from sleeper_assistant.rules import LeagueRules, derive_rules
from sleeper_assistant.sleeper import SleeperClient, SleeperLeague, SleeperNotFoundError
from sleeper_assistant.start_sit import (
    MAX_COMPARE,
    BestLineup,
    Comparison,
    best_lineup,
    compare_players,
)
from sleeper_assistant.team_depth import TeamDepth, build_team_depth

log = logging.getLogger(__name__)

RESYNC_COOLDOWN = timedelta(seconds=60)  # connect reuses a sync newer than this
VIEW_TOUCH_INTERVAL = timedelta(hours=1)  # last_viewed_at is refreshed at most this often
# Read endpoints are identical for everyone and only change when a sync runs, so let the CDN
# serve them briefly instead of hitting the database on every page view.
READ_CACHE = "public, s-maxage=30, stale-while-revalidate=120"

app = FastAPI(title="Sleeper Fantasy Assistant", version=__version__)

Username = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.]{1,40}$")]
LeagueId = Annotated[str, Path(pattern=r"^\d{1,25}$")]


@lru_cache
def _engine() -> Engine:
    return make_engine()


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return make_session_factory(_engine())


def get_engine_factory() -> Callable[[], Engine]:
    """Returns the engine builder without calling it, so callers can handle its errors."""
    return _engine


def get_session() -> Iterator[Session]:
    with _session_factory()() as session:
        yield session


@lru_cache
def get_sleeper() -> SleeperClient:
    return SleeperClient()


SessionDep = Annotated[Session, Depends(get_session)]
SleeperDep = Annotated[SleeperClient, Depends(get_sleeper)]


class LeagueSummary(BaseModel):
    league_id: str
    name: str
    season: str
    total_rosters: int


class UserLeagues(BaseModel):
    """user_id lets the site remember which team is the user's (league users have no usernames)."""

    user_id: str
    display_name: str
    leagues: list[LeagueSummary]


class ConnectedLeague(LeagueSummary):
    rules: LeagueRules


def _summary(league: SleeperLeague) -> LeagueSummary:
    return LeagueSummary(
        league_id=league.league_id,
        name=league.name,
        season=league.season,
        total_rosters=league.total_rosters,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/health/db")
def health_db(
    engine_factory: Annotated[Callable[[], Engine], Depends(get_engine_factory)], response: Response
) -> dict[str, str | bool]:
    """Is the database reachable? Reports booleans, the URL scheme and error class names only.

    The engine is built inside the try block so a bad DATABASE_URL is reported, not a bare 500.
    """
    raw = os.environ.get("DATABASE_URL", "")
    result: dict[str, str | bool] = {
        "database_url_configured": bool(raw),
        # only what precedes "://" (e.g. "postgresql"); never the credentials or host
        "database_url_scheme": raw.split("://", 1)[0][:20] if "://" in raw else "none",
    }
    try:
        engine = engine_factory()
        result["dialect"] = engine.dialect.name
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        result["status"] = "ok"
    except Exception as exc:  # report the class only; messages can contain connection details
        response.status_code = 503
        result["status"] = "error"
        result["error"] = type(exc).__name__
    return result


@app.get("/api/users/{username}/leagues")
def list_user_leagues(
    username: Username,
    sleeper: SleeperDep,
    season: Annotated[str | None, Query(pattern=r"^\d{4}$")] = None,
) -> UserLeagues:
    """Step 1 of connecting: the leagues a Sleeper username belongs to (no password needed)."""
    try:
        user = sleeper.get_user(username)
        leagues = sleeper.get_leagues(user.user_id, season or sleeper.get_state().season)
    except SleeperNotFoundError:
        raise HTTPException(status_code=404, detail="Sleeper user not found") from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Sleeper is unavailable") from None
    return UserLeagues(
        user_id=user.user_id,
        display_name=user.display_name,
        leagues=[_summary(lg) for lg in leagues],
    )


@app.post("/api/leagues/{league_id}/connect")
def connect_league(
    league_id: LeagueId, session: SessionDep, sleeper: SleeperDep
) -> ConnectedLeague:
    """Step 2: sync the league now (seconds) and mark it active so it joins the sync pool."""
    row = session.get(LeagueRow, league_id)
    recently_synced = (
        row is not None
        and row.last_synced_at is not None
        and as_utc(row.last_synced_at) > utcnow() - RESYNC_COOLDOWN
    )
    if row is None or not recently_synced:
        try:
            row = sync_league(session, sleeper, league_id)
        except SleeperNotFoundError:
            raise HTTPException(status_code=404, detail="League not found") from None
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Sleeper is unavailable") from None
        except ValidationError:
            log.exception("unexpected Sleeper payload for league %s", league_id)
            raise HTTPException(
                status_code=502, detail="Unexpected response from Sleeper"
            ) from None
    _ensure_players(session, sleeper)
    _ensure_schedule(session, sleeper, row.season)
    row.last_viewed_at = utcnow()
    session.commit()
    return _connected(row)


def _ensure_schedule(session: Session, sleeper: SleeperClient, season: str) -> None:
    """Load the season schedule the first time (one small request) so bye weeks and game state show.

    The worker refreshes it afterwards; a failure here must not block connecting.
    """
    has_games = session.scalar(
        select(func.count()).select_from(NflGameRow).where(NflGameRow.season == season)
    )
    if has_games:
        return
    try:
        sync_schedule(session, sleeper, season)
    except IntegrityError:  # a concurrent first connect loaded the schedule; that is fine
        session.rollback()
    except (httpx.HTTPError, ValidationError):
        session.rollback()
        log.exception("could not load the NFL schedule; bye weeks and game state will be missing")


def _ensure_players(session: Session, sleeper: SleeperClient) -> None:
    """Load Sleeper's player DB (~5 MB) the first time, so rosters show names, not ids.

    After that the worker refreshes it daily; a failure here must not block connecting.
    """
    if (session.scalar(select(func.count()).select_from(PlayerRow)) or 0) > 0:
        return
    try:
        sync_players(session, sleeper)
        build_crosswalk(session)
    except IntegrityError:  # a concurrent first connect loaded the players; that is fine
        session.rollback()
    except (httpx.HTTPError, ValidationError):
        session.rollback()
        log.exception("could not load the Sleeper player database; names will show as ids")


class DashboardResponse(Dashboard):
    rules: LeagueRules


@app.get("/api/leagues/{league_id}")
def get_league_dashboard(
    league_id: LeagueId, session: SessionDep, response: Response
) -> DashboardResponse:
    """Standings, rosters and the league rules card for a connected league (read-only)."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    now = utcnow()
    # throttled: refreshing the page must not cost a database write every time
    if row.last_viewed_at is None or as_utc(row.last_viewed_at) < now - VIEW_TOUCH_INTERVAL:
        row.last_viewed_at = now
        session.commit()
    connected = _connected(row)
    response.headers["Cache-Control"] = READ_CACHE
    return DashboardResponse(**build_dashboard(session, row).model_dump(), rules=connected.rules)


class LeagueSettings(BaseModel):
    """Everything Sleeper reports about how the league is set up, as stored (read-only)."""

    league_id: str
    name: str
    season: str
    total_rosters: int
    settings: dict[str, Any]
    scoring_settings: dict[str, float]
    roster_positions: list[str]


@app.get("/api/leagues/{league_id}/settings")
def get_league_settings(
    league_id: LeagueId, session: SessionDep, response: Response
) -> LeagueSettings:
    """The league's rules, scoring and roster positions exactly as Sleeper provides them."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    response.headers["Cache-Control"] = READ_CACHE
    return LeagueSettings(
        league_id=row.league_id,
        name=row.name,
        season=row.season,
        total_rosters=row.total_rosters,
        settings=row.settings,
        scoring_settings={k: float(v) for k, v in row.scoring_settings.items()},
        roster_positions=row.roster_positions,
    )


@app.get("/api/leagues/{league_id}/players")
def get_league_players(
    league_id: LeagueId, session: SessionDep, response: Response
) -> PlayersResponse:
    """Every relevant NFL player as seen through this league (availability, trends, points)."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    response.headers["Cache-Control"] = READ_CACHE
    return build_players(session, row)


PlayerId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,12}$")]


@app.get("/api/leagues/{league_id}/players/{player_id}")
def get_player_detail(
    league_id: LeagueId, player_id: PlayerId, session: SessionDep, response: Response
) -> PlayerDetail:
    """One player's bio, season, weekly points, projection and past seasons in this league."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    detail = build_player_detail(session, row, player_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Player not found")
    response.headers["Cache-Control"] = READ_CACHE
    return detail


PlayerIdParam = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]{1,12}$")]
TeamCode = Annotated[str, Path(pattern=r"^[A-Z]{2,3}$")]


@app.get("/api/leagues/{league_id}/teams/{team}")
def get_team_depth(
    league_id: LeagueId, team: TeamCode, session: SessionDep, response: Response
) -> TeamDepth:
    """One NFL team's depth chart (offense, defense, special teams) as seen through this league."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    if team not in TEAM_IDS:
        raise HTTPException(status_code=404, detail="Team not found")
    response.headers["Cache-Control"] = READ_CACHE
    return build_team_depth(session, row, team)


@app.get("/api/leagues/{league_id}/lineups")
def get_league_lineups(
    league_id: LeagueId,
    session: SessionDep,
    response: Response,
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> Lineups:
    """Both teams' lineups (starters by slot, bench, points) per matchup for one week."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    response.headers["Cache-Control"] = READ_CACHE
    return build_lineups(session, row, week)


@app.get("/api/leagues/{league_id}/start-sit")
def get_start_sit(
    league_id: LeagueId,
    session: SessionDep,
    response: Response,
    player: Annotated[list[PlayerIdParam], Query(min_length=2, max_length=MAX_COMPARE)],
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> Comparison:
    """Compare two or more players for one lineup spot and say which to start."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    response.headers["Cache-Control"] = READ_CACHE
    return compare_players(session, row, player, week)


@app.get("/api/leagues/{league_id}/start-sit/lineup")
def get_best_lineup(
    league_id: LeagueId,
    session: SessionDep,
    response: Response,
    roster: Annotated[int, Query(ge=1, le=64)],
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> BestLineup:
    """The projected-best lineup for one roster and how it differs from today's starters."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    result = best_lineup(session, row, roster, week)
    if result is None:
        raise HTTPException(status_code=404, detail="Team not found")
    response.headers["Cache-Control"] = READ_CACHE
    return result


@app.get("/api/leagues/{league_id}/rankings")
def get_rankings(
    league_id: LeagueId,
    session: SessionDep,
    response: Response,
    week: Annotated[int | None, Query(ge=1, le=18)] = None,
) -> Rankings:
    """Weekly player rankings by position: a consensus of several signals, with the spread."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    response.headers["Cache-Control"] = READ_CACHE
    return build_rankings(session, row, week)


@app.get("/api/leagues/{league_id}/accuracy")
def get_lineup_accuracy(
    league_id: LeagueId, session: SessionDep, response: Response
) -> LineupAccuracy:
    """Sit vs start accuracy per team: actual points against the best lineup, finished weeks."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    response.headers["Cache-Control"] = READ_CACHE
    return build_lineup_accuracy(session, row)


def _connected(row: LeagueRow) -> ConnectedLeague:
    league = SleeperLeague(
        league_id=row.league_id,
        name=row.name,
        season=row.season,
        total_rosters=row.total_rosters,
        scoring_settings=row.scoring_settings,
        roster_positions=row.roster_positions,
        settings=row.settings,
    )
    return ConnectedLeague(**_summary(league).model_dump(), rules=derive_rules(league))
