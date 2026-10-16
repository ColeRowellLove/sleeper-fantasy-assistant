"""The waiver wire page: this cycle's most recommended adds for one team, with the reasons.

It ranks through ``alert_waiver.WaiverBoard``, the same code the waiver alert uses, so the page and
the alert agree. The cycle comes from the league's own waiver day (Sleeper's ``waiver_day_of_week``,
Tuesday when unset): the list is for the next waiver date on or after today (US Eastern) and its
projections and byes are for the first week that starts after it, so on the waiver day itself it is
rebuilt from the fresh data and last cycle's list is gone from this view.

Each suggestion shows its signals, not one blended score: the projection gain over the team's own
worst starter, Sleeper's trending adds, and an NFL depth chart opening. ``backing`` counts how many
of them point the same way, and ESPN's ownership is shown beside them as a plain number.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alert_waiver import EASTERN, WaiverBoard, coming_week, day_name, waiver_day
from sleeper_assistant.db import LeagueRow, PlayerOwnershipRow, utcnow

LIMIT = 25


class Signal(BaseModel):
    source: str
    backs: bool  # whether this source points to adding him
    detail: str  # the number or fact, in words


class WireEntry(BaseModel):
    player_id: str
    name: str
    position: str | None
    team: str | None
    projected: float
    gain: float
    slot: str
    over: str
    reason: str  # one line with the numbers behind it
    owned: float | None  # ESPN-wide percent of leagues that roster him
    backing: int  # how many of the signals back him
    signals: list[Signal]


class WaiverWire(BaseModel):
    league_id: str
    roster_id: int
    waiver_date: date
    waiver_day: str  # "Tuesday"
    week: int | None
    entries: list[WireEntry]
    note: str | None = None  # why the list is empty, when it is


def next_waiver_date(league: LeagueRow, now: datetime) -> date:
    """The waiver date on or after today in US Eastern: this cycle."""
    today = now.astimezone(EASTERN).date()
    sleeper_weekday = (today.weekday() + 1) % 7  # Python has Monday as 0; Sleeper has Sunday
    return today + timedelta(days=(waiver_day(league) - sleeper_weekday) % 7)


def build_waiver_wire(
    session: Session, league: LeagueRow, roster_id: int, now: datetime | None = None
) -> WaiverWire:
    moment = now or utcnow()
    waiver = next_waiver_date(league, moment)
    week = coming_week(session, league.season, waiver)
    wire = WaiverWire(
        league_id=league.league_id,
        roster_id=roster_id,
        waiver_date=waiver,
        waiver_day=day_name(waiver),
        week=week,
        entries=[],
    )
    if week is None:
        wire.note = "The NFL schedule is not loaded yet."
        return wire
    board = WaiverBoard(session, league, week)
    roster = next((r for r in board.rosters if r.roster_id == roster_id), None)
    if roster is None:
        wire.note = "That team is not in this league."
        return wire
    if not board.has_projections:
        wire.note = f"Week {week} projections are not out yet; check back later."
        return wire
    picks = board.pickups(roster, board.lineup(roster))[:LIMIT]
    owned = {
        row.player_id: row.owned
        for row in session.scalars(
            select(PlayerOwnershipRow).where(
                PlayerOwnershipRow.player_id.in_([p.player.player_id for p in picks])
            )
        )
    }
    for pick in picks:
        p = pick.player
        signals = [
            Signal(
                source="Sleeper projection",
                backs=True,
                detail=f"projected {pick.projected:.1f}, +{pick.gain:.1f} {pick.over}",
            ),
            Signal(
                source="Sleeper trending adds",
                backs=bool(pick.adds),
                detail=(
                    f"added in {pick.adds:,} leagues in the last day"
                    if pick.adds
                    else "not among the top 100 adds"
                ),
            ),
            Signal(
                source="NFL depth chart",
                backs=bool(pick.out_starter),
                detail=(
                    f"{pick.out_starter} is out ahead of him"
                    if pick.out_starter
                    else "no starter out ahead of him"
                ),
            ),
        ]
        backing = [s for s in signals if s.backs]
        wire.entries.append(
            WireEntry(
                player_id=p.player_id,
                name=p.full_name or p.player_id,
                position=p.position,
                team=p.team,
                projected=round(pick.projected, 1),
                gain=round(pick.gain, 1),
                slot=pick.slot,
                over=pick.over,
                reason="; ".join(s.detail for s in backing),
                owned=owned.get(p.player_id),
                backing=len(backing),
                signals=signals,
            )
        )
    if not wire.entries:
        wire.note = "Nobody available would improve this team's lineup this week."
    return wire
