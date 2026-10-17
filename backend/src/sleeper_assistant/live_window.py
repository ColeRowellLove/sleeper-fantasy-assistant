"""Whether an NFL game could be on right now, from the stored schedule.

Everything that should speed up during live games (the read caches, the worker's stat and schedule
syncs, the in-job refresh loop) asks this one question, so they agree. A game is "on" while Sleeper
says it is in progress, or from an hour before its kickoff until five hours after (see
``live.window_open``). Outside that, the slower, cheaper schedules apply and quiet days cost
nothing.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import GAME_LIVE
from sleeper_assistant.db import NflGameRow
from sleeper_assistant.live import WINDOW_AFTER, WINDOW_BEFORE, window_open

# a game still marked in progress this long after kickoff is stale (a missed sync, a suspended game)
STALE_IN_GAME = timedelta(hours=8)


def live_window_open(
    session: Session, season: str | None = None, now: datetime | None = None
) -> bool:
    """True while a game of the season (any season when None) is on, about to be or just was.

    A game Sleeper still calls "in progress" counts only for ``STALE_IN_GAME`` after its kickoff, so
    a missed schedule sync or a suspended game cannot keep the fast schedules on for ever.
    """
    moment = now or datetime.now(UTC)
    query = select(NflGameRow.kickoff, NflGameRow.status).where(
        (
            (NflGameRow.status == GAME_LIVE)
            & ((NflGameRow.kickoff.is_(None)) | (NflGameRow.kickoff >= moment - STALE_IN_GAME))
        )
        | (
            (NflGameRow.kickoff >= moment - WINDOW_AFTER)
            & (NflGameRow.kickoff <= moment + WINDOW_BEFORE)
        )
    )
    if season is not None:
        query = query.where(NflGameRow.season == season)
    rows = session.execute(query).all()
    return window_open(
        [kickoff for kickoff, _ in rows], any(status == GAME_LIVE for _, status in rows), moment
    )


_cache: dict[str | None, tuple[float, bool]] = {}
CACHE_SECONDS = 15.0


def reset_cache() -> None:
    _cache.clear()


def live_window_cached(session: Session, season: str | None = None) -> bool:
    """``live_window_open`` remembered for a few seconds, so each read does not repeat the scan.

    The answer changes at most every few minutes; a viewer hitting many endpoints gets one query.
    """
    moment = time.monotonic()
    hit = _cache.get(season)
    if hit is not None and moment - hit[0] < CACHE_SECONDS:
        return hit[1]
    answer = live_window_open(session, season)
    _cache[season] = (moment, answer)
    return answer
