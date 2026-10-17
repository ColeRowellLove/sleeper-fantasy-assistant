"""What every API route shares: the database session, the league in the path and cache headers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Response
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sleeper_assistant.db import LeagueRow, make_engine, make_session_factory
from sleeper_assistant.live_window import live_window_cached
from sleeper_assistant.sleeper import SleeperClient

# Read endpoints are identical for everyone and only change when a sync runs, so let the CDN
# serve them briefly instead of hitting the database on every page view.
READ_CACHE = "public, s-maxage=30, stale-while-revalidate=120"
# while a game is on, answers are only trusted for a few seconds so scores and stats stay fresh
READ_CACHE_LIVE = "public, s-maxage=10, stale-while-revalidate=5"

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


def read_cache(session: Session, season: str) -> str:
    """The Cache-Control for a read: a few seconds while a game is on, longer otherwise."""
    return READ_CACHE_LIVE if live_window_cached(session, season) else READ_CACHE


def get_league(league_id: LeagueId, session: SessionDep, response: Response) -> LeagueRow:
    """The connected league named in the path (404 when unknown); sets the read cache header."""
    row = session.get(LeagueRow, league_id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not connected yet")
    response.headers["Cache-Control"] = read_cache(session, row.season)
    return row


LeagueDep = Annotated[LeagueRow, Depends(get_league)]
