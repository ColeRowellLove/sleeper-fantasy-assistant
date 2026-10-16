"""Injury alerts. The first: a player is ruled out.

Two parts. ``track_injuries`` runs once per alert run and records each player's injury status,
keeping the previous status and when it changed, so "ruled out" is a real comparison and not a
guess. The first time a player is seen nothing is said (it only records what is already out).
``detect_ruled_out`` then runs for every league: for each player ruled Out in the last 48 hours it
tells every team that has him, and for a starter says where he starts, the best healthy replacement
on that team's bench and who is next on the NFL depth chart. Nothing is made up: a missing
projection or depth chart just leaves that part of the sentence out.

Only Sleeper's ``Out`` counts as "ruled out"; Doubtful, Questionable and the IR-type designations
are other events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alerts import NewAlert, register, register_pre_run
from sleeper_assistant.dashboard import current_week, starter_slots
from sleeper_assistant.db import LeagueRow, PlayerInjuryRow, PlayerRow, RosterRow, as_utc
from sleeper_assistant.lineup_slots import eligible_positions
from sleeper_assistant.projections import projected_points
from sleeper_assistant.team_depth import OUT_STATUSES, build_team_depth

OUT = "Out"
RECENT_RULING = timedelta(hours=48)  # a ruling older than this is no longer news
_NO_STATUS = {"", "NA"}  # Sleeper's markers for "nothing to report"


def _clean(status: str | None) -> str | None:
    return None if status is None or status in _NO_STATUS else status


@register_pre_run("injury_status")
def track_injuries(session: Session, now: datetime) -> None:
    """Record every player's injury status (also those without a team, so a player who is cut and
    signed again is compared with his own last status); note when it changes."""
    known = {row.player_id: row for row in session.scalars(select(PlayerInjuryRow))}
    for player_id, raw in session.execute(select(PlayerRow.player_id, PlayerRow.injury_status)):
        status = _clean(raw)
        row = known.get(player_id)
        if row is None:
            # first sight: remember it, but do not call it news
            session.add(PlayerInjuryRow(player_id=player_id, status=status, seen_at=now))
        elif row.status != status:
            row.previous, row.status, row.changed_at, row.seen_at = row.status, status, now, now


def _ruled_out(session: Session, now: datetime) -> list[tuple[PlayerInjuryRow, PlayerRow]]:
    rows = session.scalars(
        select(PlayerInjuryRow).where(
            PlayerInjuryRow.status == OUT, PlayerInjuryRow.changed_at.is_not(None)
        )
    )
    fresh = [r for r in rows if r.changed_at and as_utc(r.changed_at) >= now - RECENT_RULING]
    players = {
        p.player_id: p
        for p in session.scalars(
            select(PlayerRow).where(PlayerRow.player_id.in_([r.player_id for r in fresh]))
        )
    }
    return [(r, players[r.player_id]) for r in fresh if r.player_id in players]


def _replacement(
    session: Session,
    roster: RosterRow,
    slot: str,
    out: PlayerRow,
    projections: dict[str, float],
) -> str | None:
    """A sentence about the best healthy bench player who can fill the slot, or None."""
    parked = set(roster.reserve) | set(roster.taxi) | set(roster.starters)
    bench = [pid for pid in roster.players if pid not in parked and pid != out.player_id]
    fit = [
        p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(bench)))
        if p.position in eligible_positions(slot, out.position or "")
        and p.team is not None  # on an NFL team
        and (p.injury_status or "") not in OUT_STATUSES
        and p.injury_status != "Doubtful"  # not someone who probably will not play either
    ]
    if not fit:
        return "Nobody on your bench fits that slot."
    projected = [p for p in fit if p.player_id in projections]
    if not projected:
        return None  # candidates exist but none has a projection: say nothing rather than guess
    best = max(projected, key=lambda p: projections[p.player_id])
    return (
        f"Best replacement on your bench: {best.full_name or best.player_id} "
        f"({best.position}, projected {projections[best.player_id]:.1f})."
    )


@dataclass(frozen=True)
class NextUp:
    """The man first in line on the NFL depth chart behind a player who is out."""

    player_id: str | None
    name: str
    owner_roster_id: int | None  # the fantasy team in this league that has him; None = available
    owner_team: str | None


def _next_up(session: Session, league: LeagueRow, out: PlayerRow) -> NextUp | None:
    """Who is first in line behind him on the NFL depth chart, and who owns him in this league."""
    if out.team is None:
        return None
    chart = build_team_depth(session, league, out.team)
    for group in chart.groups:
        for slot in group.slots:
            if not any(p.player_id == out.player_id for p in slot.players):
                continue
            for player in slot.players:
                if player.next_up:
                    return NextUp(
                        player.player_id, player.name, player.owner_roster_id, player.owner_team
                    )
    return None


def _where_is_next_up(nu: NextUp, team: str, roster: RosterRow) -> str:
    """The depth chart sentence, aware of whose roster the next man up is on."""
    if nu.owner_roster_id is None:
        owner = "available"
    elif nu.owner_roster_id == roster.roster_id:
        if nu.player_id in roster.reserve:
            return (
                f"Next on the {team} depth chart is {nu.name}, who is on your injured reserve "
                "and cannot start yet."
            )
        if nu.player_id in roster.taxi:
            return (
                f"Next on the {team} depth chart is {nu.name}, who is on your taxi squad "
                "and cannot start yet."
            )
        owner = "already on your bench"
    else:
        owner = f"on {nu.owner_team}" if nu.owner_team else "rostered"
    return f"Next on the {team} depth chart: {nu.name} ({owner})."


def _suggested_switch(  # noqa: PLR0913, PLR0917
    session: Session,
    roster: RosterRow,
    slot: str,
    out: PlayerRow,
    nu: NextUp | None,
    projections: dict[str, float],
) -> str | None:
    """The switch to make: the owned next man up when he fits, otherwise the best bench player."""
    if nu and nu.player_id and nu.owner_roster_id == roster.roster_id:
        mine = session.get(PlayerRow, nu.player_id)
        on_bench = nu.player_id not in set(roster.reserve) | set(roster.taxi) | set(roster.starters)
        if (
            mine is not None
            and on_bench
            and mine.team is not None
            and mine.position in eligible_positions(slot, out.position or "")
            and (mine.injury_status or "") not in OUT_STATUSES
            and mine.injury_status != "Doubtful"
        ):
            projected = projections.get(nu.player_id)
            number = f", projected {projected:.1f}" if projected is not None else ""
            return (
                f"Suggested switch: {nu.name} ({mine.position}, next up on the {out.team} depth "
                f"chart and already on your bench{number})."
            )
    return _replacement(session, roster, slot, out, projections)


@register("injury_out")
def detect_ruled_out(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    news = _ruled_out(session, now)
    if not news:
        return []
    week = current_week(session, league.season)
    slots = starter_slots(league)
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    next_ups = {player.player_id: _next_up(session, league, player) for _, player in news}
    # one projection lookup for everyone who matters (the team's players and each next man up)
    wanted = {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]}
    wanted |= {nu.player_id for nu in next_ups.values() if nu and nu.player_id}
    projections = (
        projected_points(session, league.season, week, league.scoring_settings, wanted)
        if week
        else {}
    )
    raised: list[NewAlert] = []
    for injury, player in news:
        owners = [r for r in rosters if player.player_id in [*r.players, *r.reserve, *r.taxi]]
        if not owners:
            continue
        name = player.full_name or player.player_id
        part = (
            f" with a {player.injury_body_part.lower()} injury" if player.injury_body_part else ""
        )
        nu = next_ups[player.player_id]
        ruled_at = as_utc(injury.changed_at).isoformat() if injury.changed_at else ""
        for roster in owners:
            starts = player.player_id in roster.starters
            index = roster.starters.index(player.player_id) if starts else -1
            slot = slots[index] if 0 <= index < len(slots) else None
            sentences = [f"{name} was ruled out{part}."]
            if starts and slot:
                mine = projections.get(player.player_id)
                where = f"He starts at {slot} for you" + (f" in week {week}" if week else "")
                sentences.append(where + (f" (projected {mine:.1f})." if mine is not None else "."))
                switch = _suggested_switch(session, roster, slot, player, nu, projections)
                if switch:
                    sentences.append(switch)
            elif starts:
                sentences.append("He is in your starting lineup.")
            elif player.player_id in roster.reserve:
                sentences.append("He is already on your injured reserve.")
            elif player.player_id in roster.taxi:
                sentences.append("He is on your taxi squad.")
            else:
                sentences.append("He is on your bench.")
            if nu and player.team and not sentences[-1].startswith("Suggested switch"):
                sentences.append(_where_is_next_up(nu, player.team, roster))
            raised.append(
                NewAlert(
                    roster_id=roster.roster_id,
                    kind="injury_out",
                    dedupe_key=f"injury_out:{player.player_id}:{ruled_at}",
                    title=f"{name} ({player.position}, {player.team}) was ruled out",
                    why=" ".join(sentences),
                    player_id=player.player_id,
                    data={
                        "week": week,
                        "slot": slot,
                        "starter": starts,
                        "previous": injury.previous,
                        "next_up": nu.player_id if nu else None,
                    },
                )
            )
    return raised
