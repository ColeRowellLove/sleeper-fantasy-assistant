"""What every alert detector needs: the "is it time to say it" window, event keys and labels."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import LeagueRow, NflGameRow, PlayerRow
from sleeper_assistant.nfl_games import current_week
from sleeper_assistant.player_names import player_name


def alert_key(kind: str, *parts: object) -> str:
    """The dedupe key of an event: its kind, then what makes this occurrence unique.

    Name the occurrence (a week, a date), not just the subject, so the same player alerts again
    the next time it happens.
    """
    return ":".join([kind, *(str(p) for p in parts)])


def first_game_date(session: Session, season: str, week: int) -> date | None:
    """The day of the week's first NFL game, or None when no game has a date."""
    days = session.scalars(
        select(NflGameRow.game_date).where(NflGameRow.season == season, NflGameRow.week == week)
    ).all()
    return min((date.fromisoformat(d[:10]) for d in days if d), default=None)


def lineup_week(
    session: Session, league: LeagueRow, now: datetime, tell_before: timedelta
) -> int | None:
    """The current week once it is within ``tell_before`` of its first game, else None.

    Earlier than that the lineup is not being set yet, so an alert about it would only be noise.
    """
    week = current_week(session, league.season)
    if not week:
        return None
    first = first_game_date(session, league.season, week)
    if first is None or now.date() < first - tell_before:
        return None
    return week


def player_tag(player: PlayerRow) -> str:
    """ "Name (POS, TEAM)": how an alert's title names a player."""
    return f"{player_name(player)} ({player.position}, {player.team})"
