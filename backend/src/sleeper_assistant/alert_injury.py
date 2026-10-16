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
    """Record every active player's injury status; note when it changes."""
    known = {row.player_id: row for row in session.scalars(select(PlayerInjuryRow))}
    for player_id, raw in session.execute(
        select(PlayerRow.player_id, PlayerRow.injury_status).where(PlayerRow.team.is_not(None))
    ):
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
        and (p.injury_status or "") not in OUT_STATUSES
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


def _next_up(session: Session, league: LeagueRow, out: PlayerRow) -> str | None:
    """Who is first in line behind him on the NFL depth chart, and whether he is free to add."""
    if out.team is None:
        return None
    chart = build_team_depth(session, league, out.team)
    for group in chart.groups:
        for slot in group.slots:
            if not any(p.player_id == out.player_id for p in slot.players):
                continue
            for player in slot.players:
                if player.next_up:
                    status = (
                        "available" if player.owner_roster_id is None else f"on {player.owner_team}"
                    )
                    return f"Next on the {out.team} depth chart: {player.name} ({status})."
    return None


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
    raised: list[NewAlert] = []
    for status, player in news:
        owners = [r for r in rosters if player.player_id in [*r.players, *r.reserve, *r.taxi]]
        if not owners:
            continue
        name = player.full_name or player.player_id
        part = (
            f" with a {player.injury_body_part.lower()} injury" if player.injury_body_part else ""
        )
        depth = _next_up(session, league, player)
        ruled_at = as_utc(status.changed_at).isoformat() if status.changed_at else ""
        for roster in owners:
            starts = player.player_id in roster.starters
            index = roster.starters.index(player.player_id) if starts else -1
            slot = slots[index] if 0 <= index < len(slots) else None
            projections = (
                projected_points(
                    session, league.season, week, league.scoring_settings,
                    [*roster.players, player.player_id],
                )
                if week
                else {}
            )  # fmt: skip
            sentences = [f"{name} was ruled out{part}."]
            if starts and slot:
                mine = projections.get(player.player_id)
                where = f"He starts at {slot} for you" + (f" in week {week}" if week else "")
                sentences.append(where + (f" (projected {mine:.1f})." if mine is not None else "."))
                replacement = _replacement(session, roster, slot, player, projections)
                if replacement:
                    sentences.append(replacement)
            elif player.player_id in roster.reserve:
                sentences.append("He is already on your injured reserve.")
            elif player.player_id in roster.taxi:
                sentences.append("He is on your taxi squad.")
            else:
                sentences.append("He is on your bench.")
            if depth:
                sentences.append(depth)
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
                        "previous": status.previous,
                    },
                )
            )
    return raised
