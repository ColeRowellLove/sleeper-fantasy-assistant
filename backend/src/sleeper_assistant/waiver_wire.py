"""The waiver wire page: this cycle's most recommended adds for one team, with the reasons.

It ranks through ``alert_waiver.WaiverBoard``, the same code the waiver alert uses, so the page and
the alert agree. The cycle comes from the league's own waiver day (Sleeper's ``waiver_day_of_week``,
Tuesday when unset): the list is for the next waiver date *after* today (US Eastern) and its
projections and byes are for the first week that starts after it. Waivers run on the waiver day, so
that morning the list starts over for the next cycle, rebuilt from fresh data.

Each suggestion is ranked by its projection gain over the team's own worst starter. Beside it are
the reasons for and against adding the player, each marked as such: trending adds, a starter out
ahead of them on the depth chart, a soft or tough matchup, recent form against the projection, an
injury designation. Only reasons that apply are listed (a missing depth chart opening is not a
mark against anyone). ESPN's ownership is shown as a plain fact. Nothing is blended into one score.
The list has views by position (the board caps each position by what a lineup can use, so one
defense does not fill the page), and ``top`` is the mixed best-of view.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alert_waiver import Pickup, WaiverBoard, capped
from sleeper_assistant.db import LeagueRow, NflGameRow, PlayerOwnershipRow, utcnow
from sleeper_assistant.player_names import player_name
from sleeper_assistant.waiver_calendar import EASTERN, coming_week, day_name, waiver_day

# how many of each position the page lists (a lineup can use more receivers than kickers)
WIRE_CAPS = {"QB": 6, "RB": 10, "WR": 10, "TE": 6, "K": 3, "DEF": 4}
TOP_COUNT = 10  # the mixed "Top" view
TOP_CAPS = {"QB": 2, "TE": 2, "K": 1, "DEF": 1}  # one slot each, so one defense in the mix
SOFT = 0.25  # the opponent is among the easiest quarter of teams for his position
TOUGH = 0.75  # ... or among the hardest quarter
FORM_GAP = 2.0  # points a game that his last three differ from his projection to be worth saying
LOW_PROJECTION = 6.0  # a skill player projected below this has little to offer


class Reason(BaseModel):
    stance: Literal["for", "against", "info"]
    label: str  # "Trending adds", "Tough matchup"
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
    owned: float | None  # ESPN-wide percent of leagues that roster them
    for_count: int
    against_count: int
    reasons: list[Reason]


class WaiverWire(BaseModel):
    league_id: str
    roster_id: int
    waiver_date: date
    waiver_day: str  # "Tuesday"
    week: int | None
    entries: list[WireEntry]  # best first; every position, capped per position
    top: list[str] = []  # player ids of the mixed best-of view
    note: str | None = None  # why the list is empty, when it is


def next_waiver_date(league: LeagueRow, now: datetime) -> date:
    """The next waiver date after today in US Eastern: this cycle. On the waiver day itself the
    waivers run, so the cycle is already the one a week later."""
    today = now.astimezone(EASTERN).date()
    sleeper_weekday = (today.weekday() + 1) % 7  # Python has Monday as 0; Sleeper has Sunday
    return today + timedelta(days=(waiver_day(league) - sleeper_weekday) % 7 or 7)


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:  # noqa: PLR2004
        return f"{n}th"
    return f"{n}{({1: 'st', 2: 'nd', 3: 'rd'}).get(n % 10, 'th')}"


def reasons_for(pick: Pickup, owned: float | None) -> list[Reason]:  # noqa: PLR0912
    """The reasons for and against adding this player, only those that apply."""
    out = [
        Reason(
            stance="for",
            label="Adds points",
            detail=f"projected {pick.projected:.1f}, +{pick.gain:.1f} {pick.over}",
        )
    ]
    if pick.adds:
        out.append(
            Reason(
                stance="for", label="Trending adds", detail=f"added in {pick.adds:,} leagues today"
            )
        )
    if pick.out_starter:
        out.append(
            Reason(
                stance="for",
                label="Starter out ahead",
                detail=f"{pick.out_starter} is out, so the role is open",
            )
        )
    m = pick.matchup
    if m is not None and m.teams:
        if m.side == "offense":  # a team defense: the opponent's offense, fewest points first
            text = f"{m.opponent} offense scores the {_ordinal(m.rank)}-fewest points of {m.teams}"
        else:
            text = f"{m.opponent} gives up the {_ordinal(m.rank)}-most points to this position"
        if m.rank <= m.teams * SOFT:
            out.append(Reason(stance="for", label="Soft matchup", detail=text))
        elif m.rank > m.teams * TOUGH:
            out.append(Reason(stance="against", label="Tough matchup", detail=text))
    if pick.form is not None:
        if pick.form - pick.projected >= FORM_GAP:
            out.append(
                Reason(
                    stance="for",
                    label="Hot lately",
                    detail=(
                        f"{pick.form:.1f} a game over the last three, "
                        f"above the {pick.projected:.1f} projection"
                    ),
                )
            )
        elif pick.projected - pick.form >= FORM_GAP:
            out.append(
                Reason(
                    stance="against",
                    label="Cold lately",
                    detail=(
                        f"{pick.form:.1f} a game over the last three, "
                        f"below the {pick.projected:.1f} projection"
                    ),
                )
            )
    if pick.status:
        out.append(Reason(stance="against", label="Injury", detail=f"listed {pick.status}"))
    if pick.projected < LOW_PROJECTION and (pick.player.position or "") not in ("K", "DEF"):
        out.append(
            Reason(
                stance="against", label="Low ceiling", detail=f"projects only {pick.projected:.1f}"
            )
        )
    if pick.drop:
        out.append(
            Reason(stance="info", label="Replaces", detail=f"takes the place of {pick.drop}")
        )
    if owned is not None:
        out.append(
            Reason(
                stance="info", label="Ownership", detail=f"owned in {owned:.0f}% of ESPN leagues"
            )
        )
    return out


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
    if not session.scalar(
        select(NflGameRow.game_id)
        .where(NflGameRow.season == league.season, NflGameRow.game_date >= waiver.isoformat())
        .limit(1)
    ):
        wire.week = None
        wire.note = "There are no games left this season, so there is nothing to add for."
        return wire
    board = WaiverBoard(session, league, week)
    roster = next((r for r in board.rosters if r.roster_id == roster_id), None)
    if roster is None:
        wire.note = "That team is not in this league."
        return wire
    if not board.has_projections:
        wire.note = f"Week {week} projections are not out yet; check back later."
        return wire
    picks = board.pickups(roster, board.lineup(roster), None, WIRE_CAPS, detail=True)
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
        reasons = reasons_for(pick, owned.get(p.player_id))
        wire.entries.append(
            WireEntry(
                player_id=p.player_id,
                name=player_name(p),
                position=p.position,
                team=p.team,
                projected=round(pick.projected, 1),
                gain=round(pick.gain, 1),
                slot=pick.slot,
                over=pick.over,
                reason="; ".join(r.detail for r in reasons if r.stance == "for"),
                owned=owned.get(p.player_id),
                for_count=sum(r.stance == "for" for r in reasons),
                against_count=sum(r.stance == "against" for r in reasons),
                reasons=reasons,
            )
        )
    wire.top = [x.player.player_id for x in capped(picks, TOP_CAPS, TOP_COUNT)]
    if not wire.entries:
        wire.note = "Nobody available would improve this team's lineup this week."
    return wire
