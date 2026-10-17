"""The league's waiver calendar: its weekday, when to tell managers, and the week it is for."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import EASTERN
from sleeper_assistant.core.nfl.nfl_games import current_week
from sleeper_assistant.db import LeagueRow, NflGameRow

DEFAULT_WAIVER_DAY = 2  # Tuesday, with Sunday as 0 (Sleeper's numbering)
FIRST_HOUR = 9  # no alert before 9 am Eastern, so the overnight syncs have landed
_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def waiver_day(league: LeagueRow) -> int:
    """The league's waiver weekday, 0 = Sunday .. 6 = Saturday; Tuesday when unset or invalid."""
    value = league.settings.get("waiver_day_of_week")
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 6:  # noqa: PLR2004
        return value
    return DEFAULT_WAIVER_DAY


def waiver_date_if_tomorrow(league: LeagueRow, now: datetime) -> date | None:
    """The coming waiver date when it is the day before it (US Eastern, from 9 am), else None."""
    local = now.astimezone(EASTERN)
    tomorrow = local.date() + timedelta(days=1)
    sleeper_weekday = (tomorrow.weekday() + 1) % 7  # Python has Monday as 0; Sleeper has Sunday
    if sleeper_weekday != waiver_day(league) or local.hour < FIRST_HOUR:
        return None
    return tomorrow


def day_name(waiver: date) -> str:
    return _DAYS[(waiver.weekday() + 1) % 7]


def coming_week(session: Session, season: str, waiver: date) -> int | None:
    """The first week whose games all start on or after the waiver date.

    On the Monday evening of Monday Night Football the current week is still being played; the
    waiver pickups are for the week after, so that is the one projected and checked for byes.
    """
    first_day: dict[int, str] = {}
    for week, day in session.execute(
        select(NflGameRow.week, NflGameRow.game_date).where(NflGameRow.season == season)
    ):
        if day:
            first_day[week] = min(day, first_day.get(week, day))
    later = sorted(w for w, day in first_day.items() if day >= waiver.isoformat())
    return later[0] if later else current_week(session, season)
