"""Bye week alert: a starter's team has no game this week.

Told once per player per week to the team that starts him, with the slot and the best healthy
bench player who could take it (the same suggestion the ruled-out alert makes, skipping bench
players who are also on a bye). Without a schedule for the week nothing is said: with no games we
cannot tell a bye from missing data.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alerts.engine import NewAlert, register
from sleeper_assistant.alerts.helpers import alert_key, lineup_week, player_tag
from sleeper_assistant.alerts.injury import Spot, suggested_switch
from sleeper_assistant.core.league.lineup_slots import starter_slots
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.nfl.nfl_games import games_for_week
from sleeper_assistant.core.scoring.projections import projected_points
from sleeper_assistant.db import LeagueRow, PlayerRow

KIND = "bye_week"
TELL_BEFORE = timedelta(days=3)  # said this long before the week's first game, not the week before


@register(KIND)
def detect_bye_week(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    week = lineup_week(session, league, now, TELL_BEFORE)
    if not week:
        return []  # no current week, or too early: the lineup is not being set yet
    byes = frozenset(
        team for team, game in games_for_week(session, league.season, week).items()
        if game.state == "bye"
    )  # fmt: skip
    if not byes:
        return []
    slots = starter_slots(league.roster_positions)
    rosters = league_rosters(session, league.league_id)
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
            name = player_name(player)
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
                    kind=KIND,
                    dedupe_key=alert_key(KIND, pid, league.season, week),
                    title=f"{player_tag(player)} is on a bye in week {week}",
                    why=" ".join(sentences),
                    player_id=pid,
                    data={"week": week, "slot": slot},
                )
            )
    return raised
