"""Lineup move alert: a bench player projects clearly higher than the starter he could replace.

For each team the projected-best legal lineup (the Start/Sit tool's, which reads the league's own
slots and projections) is compared with the current starters. Every swap worth more than
``MIN_GAIN`` projected points is told once. Swaps are skipped when either player's game has started
(the spot is locked), and when the starter is out or on a bye (those alerts already say so). Told
in the last ``TELL_BEFORE`` before the week's first game, when the lineup is nearly final.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alerts import NewAlert, register
from sleeper_assistant.dashboard import current_week
from sleeper_assistant.db import LeagueRow, NflGameRow, RosterRow
from sleeper_assistant.start_sit import Candidate, best_lineup, candidate_line

MIN_GAIN = 3.0  # projected points a swap must add, so small differences are not noise
TELL_BEFORE = timedelta(days=2)  # said this long before the week's first game
_LOCKED = {"live", "final"}


def _first_game(session: Session, season: str, week: int) -> date | None:
    days = session.scalars(
        select(NflGameRow.game_date).where(NflGameRow.season == season, NflGameRow.week == week)
    ).all()
    return min((date.fromisoformat(d[:10]) for d in days if d), default=None)


def _locked(candidate: Candidate) -> bool:
    return candidate.game is not None and candidate.game.state in _LOCKED


@register("lineup_move")
def detect_lineup_move(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    week = current_week(session, league.season)
    if not week:
        return []
    first = _first_game(session, league.season, week)
    if first is None or now.date() < first - TELL_BEFORE:
        return []  # the lineup is not being set yet
    raised: list[NewAlert] = []
    rosters = session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    for roster in rosters:
        best = best_lineup(session, league, roster.roster_id, week)
        if best is None:
            continue
        for change in best.changes:
            if change.gain < MIN_GAIN or change.sit.out is not None:
                continue  # too small, or the starter is out or on a bye (told elsewhere)
            if _locked(change.start) or _locked(change.sit):
                continue
            start, sit = change.start, change.sit
            raised.append(
                NewAlert(
                    roster_id=roster.roster_id,
                    kind="lineup_move",
                    dedupe_key=(
                        f"lineup_move:{start.player_id}:{sit.player_id}:{league.season}:{week}"
                    ),
                    title=(
                        f"Start {start.name} over {sit.name}: +{change.gain:.1f} projected points"
                    ),
                    why=(
                        f"{start.name} ({start.position}) {candidate_line(start)}; "
                        f"{sit.name} ({sit.position}) {candidate_line(sit)}."
                    ),
                    player_id=start.player_id,
                    data={
                        "week": week,
                        "start": start.player_id,
                        "sit": sit.player_id,
                        "gain": change.gain,
                    },
                )
            )
    return raised
