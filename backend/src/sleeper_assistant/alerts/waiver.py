"""The waiver targets alert: each team's best pickups, the day before the league's waiver day.

The waiver day is read from the league's own Sleeper settings (``waiver_day_of_week``, where 0 is
Sunday so Tuesday is 2) with Tuesday as the default when it is missing, and the day is judged in US
Eastern time, the clock waivers run on. On the day before, the first alert run raises one alert per
team (the dedupe key names the waiver date, so later runs and later days add nothing).

The week is the coming one: the first whose games all start on or after the waiver date, so on the
Monday evening of Monday Night Football it is already next week's projections and byes.

A target is an available player projected for that week, ranked by how much he would help *that*
team. The team's best lineup is built from its healthy players (not on injured reserve, a bye or
ruled out) with the league's own slots, flex and superflex included, and the pickup is compared with
the weakest starter he could replace: any player in a slot his position can fill, or an open slot
that is worth nothing yet. His gain is his projected points (scored with the league's rules) minus
that player's. Only players with a projection are suggested, players on a bye, ruled out or doubtful
are skipped, and the first run before 9 am Eastern waits so the overnight syncs have landed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from sleeper_assistant.alerts import advice as alert_advice
from sleeper_assistant.alerts.engine import NewAlert, needs_advice, register
from sleeper_assistant.alerts.helpers import alert_key
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.league.waiver_board import Pickup, WaiverBoard
from sleeper_assistant.core.nfl.waiver_calendar import (
    coming_week,
    day_name,
    waiver_date_if_tomorrow,
)
from sleeper_assistant.db import (
    LeagueRow,
    PlayerRow,
    RosterRow,
)

KIND = "waiver_targets"
TARGETS = 5  # how many pickups an alert lists
ALERT_CAPS = {"QB": 2, "TE": 2, "K": 1, "DEF": 1}  # one slot each: do not list four defenses


def _advice(  # noqa: PLR0913, PLR0917
    session: Session,
    league: LeagueRow,
    roster: RosterRow,
    top: list[Pickup],
    projections: dict[str, float],
    slots: list[str],
    week: int,
    key: str,
    now: datetime,
    lineup: list[tuple[str, str]],
    players: dict[str, PlayerRow],
) -> dict[str, object] | None:
    """The model's ranking of the computed pickups for this roster, or None (also None when this
    team's alert already has advice, so the model is asked once per event)."""
    if alert_advice.client() is None or not needs_advice(
        session, league.league_id, roster.roster_id, key, now
    ):
        return None
    options = [
        alert_advice.option(x.player, "pickup", x.projected, gain=round(x.gain, 1), over=x.over)
        for x in top
    ]
    starters = {pid for _, pid in lineup}
    droppable = {
        pid
        for pid in roster.players
        if pid in players and pid not in starters and pid not in roster.reserve
    }
    facts: dict[str, object] = {
        "week": week,
        "league_slots": slots,
        "roster": alert_advice.roster_facts(session, roster, projections, slots),
        "droppable": sorted(droppable),
        "options": options,
    }
    return alert_advice.advise("waiver.v1", facts, options, droppable)


@register(KIND)
def detect_waiver_targets(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    waiver = waiver_date_if_tomorrow(league, now)
    week = coming_week(session, league.season, waiver) if waiver else None
    if waiver is None or week is None:
        return []
    board = WaiverBoard(session, league, week)
    if not board.has_projections:
        return []  # nothing is projected yet: say nothing now, the next run tries again
    when = f"{day_name(waiver)}, {waiver.strftime('%b')} {waiver.day}"

    raised: list[NewAlert] = []
    for roster in board.rosters:
        lineup = board.lineup(roster)
        top = board.pickups(roster, lineup, TARGETS, ALERT_CAPS)
        if not top:
            continue  # nothing useful for this team: no alert, nothing padded
        lines: list[str] = []
        targets: list[dict[str, object]] = []
        for pick in top:
            p, pid = pick.player, pick.player.player_id
            name = player_name(p)
            detail = (
                f"({p.position}, {p.team}): projected {pick.projected:.1f}, "
                f"+{pick.gain:.1f} {pick.over}."
            )
            if pick.adds:
                detail += f" Added in {pick.adds:,} leagues in the last day."
            if pick.out_starter:
                detail += f" {pick.out_starter} is out ahead of him."
            lines.append(f"{name} {detail}")
            targets.append(
                {
                    "player_id": pid,
                    "name": name,
                    "position": p.position,
                    "team": p.team,
                    "projected": round(pick.projected, 1),
                    "gain": round(pick.gain, 1),
                    "detail": detail,
                    "line": f"{name} {detail}",
                }
            )
        key = alert_key(KIND, league.league_id, waiver.isoformat())
        advice = _advice(
            session,
            league,
            roster,
            top,
            board.projections,
            board.slots,
            week,
            key,
            now,
            lineup,
            board.players,
        )
        raised.append(
            NewAlert(
                roster_id=roster.roster_id,
                kind=KIND,
                dedupe_key=key,
                title=f"Top waiver targets for {when}",
                why=" ".join(f"{i}. {line}" for i, line in enumerate(lines, start=1)),
                data={
                    "week": week,
                    "waiver_date": waiver.isoformat(),
                    "targets": targets,
                    **({"advice": advice} if advice else {}),
                },
            )
        )
    return raised
