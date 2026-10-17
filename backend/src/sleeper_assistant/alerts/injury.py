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

from sleeper_assistant.alerts import advice as alert_advice
from sleeper_assistant.alerts.engine import NewAlert, needs_advice, register, register_pre_run
from sleeper_assistant.alerts.helpers import alert_key, player_tag
from sleeper_assistant.core.league.lineup_slots import eligible_positions, starter_slots
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.nfl.injury_status import UNLIKELY_TO_PLAY
from sleeper_assistant.core.nfl.nfl_games import current_week, games_for_week
from sleeper_assistant.core.nfl.team_depth import build_team_depth
from sleeper_assistant.core.scoring.projections import projected_points
from sleeper_assistant.db import LeagueRow, PlayerInjuryRow, PlayerRow, RosterRow, as_utc

KIND = "injury_out"
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


@dataclass(frozen=True)
class Spot:
    """Where the player who is out sits on one team: whose roster, which slot, which player."""

    roster: RosterRow
    slot: str
    out: PlayerRow
    byes: frozenset[str] = frozenset()  # NFL teams not playing: their players cannot fill the slot


@dataclass(frozen=True)
class NextUp:
    """The man first in line on the NFL depth chart behind a player who is out."""

    player_id: str | None
    name: str
    owner_roster_id: int | None  # the fantasy team in this league that has him; None = available
    owner_team: str | None


SWITCH_MARGIN = 2.0  # projected points a bench player must beat the owned next man up by


def _can_start(p: PlayerRow) -> bool:
    """On an NFL team and not out or doubtful: someone who could be started."""
    return p.team is not None and (p.injury_status or "") not in UNLIKELY_TO_PLAY


def _bench_options(session: Session, spot: Spot) -> list[PlayerRow]:
    """The team's healthy bench players who can fill the slot."""
    roster = spot.roster
    parked = set(roster.reserve) | set(roster.taxi) | set(roster.starters)
    bench = [pid for pid in roster.players if pid not in parked and pid != spot.out.player_id]
    allowed = eligible_positions(spot.slot, spot.out.position or "")
    return [
        p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(bench)))
        if p.position in allowed and _can_start(p) and p.team not in spot.byes
    ]


def _best_bench(options: list[PlayerRow], projections: dict[str, float]) -> PlayerRow | None:
    projected = [p for p in options if p.player_id in projections]
    return max(projected, key=lambda p: projections[p.player_id]) if projected else None


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
        owner = (
            "already in your starting lineup"
            if nu.player_id in roster.starters
            else ("already on your bench")
        )
    else:
        owner = f"on {nu.owner_team}" if nu.owner_team else "rostered"
    return f"Next on the {team} depth chart: {nu.name} ({owner})."


def suggested_switch(
    session: Session, spot: Spot, nu: NextUp | None, projections: dict[str, float]
) -> tuple[str | None, bool]:
    """The switch to make, and whether it names the next man up (so he is not said twice).

    The next man up when he is on this team's bench and fits, unless a bench player projects
    clearly better (more than ``SWITCH_MARGIN`` ahead, or he has no projection and the other does).
    """
    options = _bench_options(session, spot)
    best = _best_bench(options, projections)
    owned = next((p for p in options if nu and p.player_id == nu.player_id), None)
    if nu and owned is not None:
        mine = projections.get(owned.player_id)
        ahead = (
            best is not None
            and best.player_id != owned.player_id
            and (mine is None or projections[best.player_id] - mine > SWITCH_MARGIN)
        )
        if not ahead:
            number = f", projected {mine:.1f}" if mine is not None else ""
            return (
                f"Suggested switch: {nu.name} ({owned.position}, next up on the {spot.out.team} "
                f"depth chart and already on your bench{number}).",
                True,
            )
    if not options:
        return "Nobody on your bench can play that slot this week.", False
    if best is None:
        return None, False  # candidates exist but none has a projection: say nothing, not a guess
    return (
        f"Best replacement on your bench: {player_name(best)} "
        f"({best.position}, projected {projections[best.player_id]:.1f}).",
        False,
    )


@dataclass
class _Week:
    """What every ruled-out alert of one league run shares."""

    league: LeagueRow
    week: int | None
    slots: list[str]
    projections: dict[str, float]
    byes: set[str]
    taken: set[str]  # every player any team of the league has


def _advice(
    session: Session, ctx: _Week, spot: Spot, nu: NextUp | None
) -> dict[str, object] | None:
    """The model's pick of a replacement among the legal options, or None (no model, no options,
    or an answer that failed its checks)."""
    if alert_advice.client() is None or not ctx.week:
        return None  # no model: skip building the facts
    options = [
        alert_advice.option(p, "bench", ctx.projections.get(p.player_id))
        for p in _bench_options(session, spot)
    ]
    positions = eligible_positions(spot.slot, spot.out.position or "")
    options += alert_advice.free_agents(
        session, ctx.league, ctx.week, ctx.taken, set(positions), ctx.byes
    )
    for o in options:
        o["next_up"] = bool(nu and nu.player_id and o["player_id"] == nu.player_id)
    roster = spot.roster
    parked = {*roster.reserve, *roster.taxi, *roster.starters, spot.out.player_id}
    droppable = {pid for pid in roster.players if pid not in parked}
    facts: dict[str, object] = {
        "week": ctx.week,
        "player_out": alert_advice.option(spot.out, "out", ctx.projections.get(spot.out.player_id)),
        "slot": spot.slot,
        "league_slots": ctx.slots,
        "roster": alert_advice.roster_facts(session, spot.roster, ctx.projections, ctx.slots),
        "droppable": sorted(droppable),
        "next_up_on_depth_chart": nu.name if nu else None,
        "options": options,
    }
    return alert_advice.advise("ruled_out.v1", facts, options, droppable)


def _all(roster: RosterRow) -> list[str]:
    """Every player a team has, in any spot."""
    return [*roster.players, *roster.reserve, *roster.taxi]


def _what_it_means(
    session: Session, ctx: _Week, roster: RosterRow, player: PlayerRow, nu: NextUp | None
) -> tuple[list[str], str | None, bool]:
    """The sentences telling one team what the injury means for it, the slot he starts in (if he
    starts) and whether he starts."""
    pid = player.player_id
    starts = pid in roster.starters
    index = roster.starters.index(pid) if starts else -1
    slot = ctx.slots[index] if 0 <= index < len(ctx.slots) else None
    part = f" with a {player.injury_body_part.lower()} injury" if player.injury_body_part else ""
    sentences = [f"{player_name(player)} was ruled out{part}."]
    said_next_up = False
    if starts and slot:
        mine = ctx.projections.get(pid)
        where = f"He starts at {slot} for you" + (f" in week {ctx.week}" if ctx.week else "")
        sentences.append(where + (f" (projected {mine:.1f})." if mine is not None else "."))
        switch, said_next_up = suggested_switch(
            session, Spot(roster, slot, player, frozenset(ctx.byes)), nu, ctx.projections
        )
        if switch:
            sentences.append(switch)
    elif starts:
        sentences.append("He is in your starting lineup.")
    elif pid in roster.reserve:
        sentences.append("He is already on your injured reserve.")
    elif pid in roster.taxi:
        sentences.append("He is on your taxi squad.")
    else:
        sentences.append("He is on your bench.")
    if nu and player.team and not said_next_up:
        sentences.append(_where_is_next_up(nu, player.team, roster))
    return sentences, slot, starts


def _week_context(
    session: Session,
    league: LeagueRow,
    rosters: list[RosterRow],
    next_ups: dict[str, NextUp | None],
) -> _Week:
    week = current_week(session, league.season)
    # one projection lookup for everyone who matters (the team's players and each next man up)
    wanted = {pid for r in rosters for pid in _all(r)}
    wanted |= {nu.player_id for nu in next_ups.values() if nu and nu.player_id}
    projections = (
        projected_points(session, league.season, week, league.scoring_settings, wanted)
        if week
        else {}
    )
    byes = (
        {t for t, g in games_for_week(session, league.season, week).items() if g.state == "bye"}
        if week
        else set()
    )
    return _Week(
        league=league,
        week=week,
        slots=starter_slots(league.roster_positions),
        projections=projections,
        byes=byes,
        taken={pid for r in rosters for pid in _all(r)},
    )


@register(KIND)
def detect_ruled_out(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    news = _ruled_out(session, now)
    if not news:
        return []
    rosters = league_rosters(session, league.league_id)
    # only players some team in this league has matter: no depth chart work for the rest
    rostered = [
        (injury, player, [r for r in rosters if player.player_id in _all(r)])
        for injury, player in news
    ]
    rostered = [item for item in rostered if item[2]]
    next_ups = {player.player_id: _next_up(session, league, player) for _, player, _ in rostered}
    ctx = _week_context(session, league, rosters, next_ups)
    raised: list[NewAlert] = []
    for injury, player, owners in rostered:
        nu = next_ups[player.player_id]
        ruled_at = as_utc(injury.changed_at).isoformat() if injury.changed_at else ""
        key = alert_key(KIND, player.player_id, ruled_at)
        for roster in owners:
            sentences, slot, starts = _what_it_means(session, ctx, roster, player, nu)
            advice = None
            if (
                starts
                and slot
                and ctx.week
                and needs_advice(session, league.league_id, roster.roster_id, key, now)
            ):
                advice = _advice(session, ctx, Spot(roster, slot, player, frozenset(ctx.byes)), nu)
            raised.append(
                NewAlert(
                    roster_id=roster.roster_id,
                    kind=KIND,
                    dedupe_key=key,
                    title=f"{player_tag(player)} was ruled out",
                    why=" ".join(sentences),
                    player_id=player.player_id,
                    data={
                        "week": ctx.week,
                        "slot": slot,
                        "starter": starts,
                        "previous": injury.previous,
                        "next_up": nu.player_id if nu else None,
                        **({"advice": advice} if advice else {}),
                    },
                )
            )
    return raised
