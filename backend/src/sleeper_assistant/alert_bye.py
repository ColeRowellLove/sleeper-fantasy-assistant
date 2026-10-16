"""Bye week alert: a starter's team has no game this week.

Told once per player per week to the team that starts him, with the slot and the best healthy
bench player who could take it (the same suggestion the ruled-out alert makes, skipping bench
players who are also on a bye). Without a schedule for the week nothing is said: with no games we
cannot tell a bye from missing data.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alert_injury import Spot, suggested_switch
from sleeper_assistant.alerts import NewAlert, register
from sleeper_assistant.dashboard import current_week, games_for_week, starter_slots
from sleeper_assistant.db import LeagueRow, NflGameRow, PlayerRow, RosterRow
from sleeper_assistant.projections import projected_points

TELL_BEFORE = timedelta(days=3)  # said this long before the week's first game, not the week before


def _first_game(session: Session, season: str, week: int) -> date | None:
    days = session.scalars(
        select(NflGameRow.game_date).where(NflGameRow.season == season, NflGameRow.week == week)
    ).all()
    return min((date.fromisoformat(d[:10]) for d in days if d), default=None)


@register("bye_week")
def detect_bye_week(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    week = current_week(session, league.season)
    if not week:
        return []
    first = _first_game(session, league.season, week)
    if first is None or now.date() < first - TELL_BEFORE:
        return []  # too early to be useful: the lineup is not being set yet
    byes = frozenset(
        team for team, game in games_for_week(session, league.season, week).items()
        if game.state == "bye"
    )  # fmt: skip
    if not byes:
        return []
    slots = starter_slots(league)
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    starting = {pid for r in rosters for pid in r.starters}
    players = {
        p.player_id: p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(starting)))
        if p.team in byes
    }
    if not players:
        return []
    wanted = {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]}
    projections = projected_points(session, league.season, week, league.scoring_settings, wanted)
    raised: list[NewAlert] = []
    for roster in rosters:
        for index, pid in enumerate(roster.starters):
            player = players.get(pid)
            if player is None:
                continue
            slot = slots[index] if index < len(slots) else None
            name = player.full_name or pid
            sentences = [f"{name} ({player.team}) is on a bye in week {week}."]
            if slot:
                sentences.append(f"He is in your {slot} spot and will score nothing.")
                switch, _ = suggested_switch(
                    session, Spot(roster, slot, player, byes), None, projections
                )
                if switch:
                    sentences.append(switch)
            raised.append(
                NewAlert(
                    roster_id=roster.roster_id,
                    kind="bye_week",
                    dedupe_key=f"bye_week:{pid}:{league.season}:{week}",
                    title=f"{name} ({player.position}, {player.team}) is on a bye in week {week}",
                    why=" ".join(sentences),
                    player_id=pid,
                    data={"week": week, "slot": slot},
                )
            )
    return raised
