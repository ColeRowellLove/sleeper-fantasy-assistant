"""Whether an NFL game could be on right now, from the stored schedule.

Everything that should speed up during live games (the read caches, the worker's stat and schedule
syncs, the in-job refresh loop) asks this one question, so they agree. A game is "on" while Sleeper
says it is in progress, or from an hour before its kickoff until five hours after (see
``live.window_open``). Outside that, the slower, cheaper schedules apply and quiet days cost
nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import NflGameRow
from sleeper_assistant.live import WINDOW_AFTER, WINDOW_BEFORE, window_open


def live_window_open(
    session: Session, season: str | None = None, now: datetime | None = None
) -> bool:
    """True while a game of the season (any season when None) is on, about to be or just was."""
    moment = now or datetime.now(UTC)
    query = select(NflGameRow.kickoff, NflGameRow.status).where(
        (NflGameRow.status == "in_game")
        | (
            (NflGameRow.kickoff >= moment - WINDOW_AFTER)
            & (NflGameRow.kickoff <= moment + WINDOW_BEFORE)
        )
    )
    if season is not None:
        query = query.where(NflGameRow.season == season)
    rows = session.execute(query).all()
    return window_open(
        [kickoff for kickoff, _ in rows], any(status == "in_game" for _, status in rows), moment
    )
