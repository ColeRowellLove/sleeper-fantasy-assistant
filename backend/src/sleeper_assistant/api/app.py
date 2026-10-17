"""FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Response
from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Engine

from sleeper_assistant import __version__
from sleeper_assistant.api.deps import (
    LeagueDep,
    LeagueId,
    SessionDep,
    SleeperDep,
    get_engine_factory,
)
from sleeper_assistant.api.routes_league import router
from sleeper_assistant.core.league.rules import LeagueRules, derive_rules
from sleeper_assistant.core.sources.sleeper import SleeperLeague, SleeperNotFoundError
from sleeper_assistant.db import (
    LeagueRow,
    as_utc,
    utcnow,
)
from sleeper_assistant.settings import load_settings
from sleeper_assistant.sync.ingest import finish_connect, sync_league
from sleeper_assistant.views.dashboard import Dashboard, build_dashboard

log = logging.getLogger(__name__)

RESYNC_COOLDOWN = timedelta(seconds=60)  # connect reuses a sync newer than this
VIEW_TOUCH_INTERVAL = timedelta(hours=1)  # last_viewed_at is refreshed at most this often
app = FastAPI(title="Sleeper Fantasy Assistant", version=__version__)
app.include_router(router)

Username = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.]{1,40}$")]


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
    raw = load_settings().database_url_raw
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
    finish_connect(session, sleeper, row)
    return _connected(row)


class DashboardResponse(Dashboard):
    rules: LeagueRules


@app.get("/api/leagues/{league_id}")
def get_league_dashboard(row: LeagueDep, session: SessionDep) -> DashboardResponse:
    """Standings, rosters and the league rules card for a connected league (read-only)."""
    now = utcnow()
    # throttled: refreshing the page must not cost a database write every time
    if row.last_viewed_at is None or as_utc(row.last_viewed_at) < now - VIEW_TOUCH_INTERVAL:
        row.last_viewed_at = now
        session.commit()
    connected = _connected(row)
    return DashboardResponse(**build_dashboard(session, row).model_dump(), rules=connected.rules)


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
