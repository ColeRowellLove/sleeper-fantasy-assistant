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

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant import alert_advice
from sleeper_assistant.alerts import NewAlert, already_told, register
from sleeper_assistant.dashboard import current_week, games_for_week, starter_slots
from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    RosterRow,
)
from sleeper_assistant.lineup_slots import assign_lineup, eligible_positions
from sleeper_assistant.projections import projected_points
from sleeper_assistant.team_depth import OUT_STATUSES, build_team_depth

EASTERN = ZoneInfo("America/New_York")
DEFAULT_WAIVER_DAY = 2  # Tuesday, with Sunday as 0 (Sleeper's numbering)
TARGETS = 5  # how many pickups an alert lists
MIN_GAIN = 1.0  # projected points a pickup must add to be worth a mention
FIRST_HOUR = 9  # no alert before 9 am Eastern, so the overnight syncs have landed
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
NOT_PLAYABLE = OUT_STATUSES | {"Doubtful"}  # someone who probably will not play is no pickup
_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def waiver_day(league: LeagueRow) -> int:
    """The league's waiver weekday, 0 = Sunday .. 6 = Saturday; Tuesday when unset or invalid."""
    value = league.settings.get("waiver_day_of_week")
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 6:  # noqa: PLR2004
        return value
    return DEFAULT_WAIVER_DAY


def waiver_date_if_tomorrow(league: LeagueRow, now: datetime) -> date | None:
    """The coming waiver date when it is the day before it (US Eastern, from 9 am), else None."""
    local = now.astimezone(EASTERN)
    tomorrow = local.date() + timedelta(days=1)
    sleeper_weekday = (tomorrow.weekday() + 1) % 7  # Python has Monday as 0; Sleeper has Sunday
    if sleeper_weekday != waiver_day(league) or local.hour < FIRST_HOUR:
        return None
    return tomorrow


def day_name(waiver: date) -> str:
    return _DAYS[(waiver.weekday() + 1) % 7]


def coming_week(session: Session, season: str, waiver: date) -> int | None:
    """The first week whose games all start on or after the waiver date.

    On the Monday evening of Monday Night Football the current week is still being played; the
    waiver pickups are for the week after, so that is the one projected and checked for byes.
    """
    first_day: dict[int, str] = {}
    for week, day in session.execute(
        select(NflGameRow.week, NflGameRow.game_date).where(NflGameRow.season == season)
    ):
        if day:
            first_day[week] = min(day, first_day.get(week, day))
    later = sorted(w for w, day in first_day.items() if day >= waiver.isoformat())
    return later[0] if later else current_week(session, season)


def replaced_by(
    slots: list[str],
    lineup: list[tuple[str, str]],
    points: dict[str, float],
    position: str,
) -> tuple[str, float, str | None]:
    """What a pickup at ``position`` would take the place of: (slot, points, player id or None).

    ``lineup`` is the team's best lineup as (slot, player_id) pairs. Among the slots the position
    can fill, an empty one is replaced first (worth 0, no player), otherwise the starter with the
    fewest projected points. A league with no slot for the position gets the position itself.
    """
    remaining = list(lineup)
    options: list[tuple[float, str, str | None]] = []
    for slot in slots:
        if position not in eligible_positions(slot, position):
            continue
        holder = next((pid for s, pid in remaining if s == slot), None)
        if holder is None:
            options.append((0.0, slot, None))
        else:
            remaining.remove((slot, holder))
            options.append((points.get(holder, 0.0), slot, holder))
    if not options:
        return position, 0.0, None
    value, slot, holder = min(options, key=lambda option: option[0])
    return slot, value, holder


def _opening(
    session: Session, league: LeagueRow, team: str, cache: dict[str, dict[str, str]]
) -> dict[str, str]:
    """For a team: player_id of the man next in line -> the name of the out starter ahead of him."""
    if team not in cache:
        found: dict[str, str] = {}
        for group in build_team_depth(session, league, team).groups:
            for slot in group.slots:
                starter = slot.players[0] if slot.players else None
                for player in slot.players:
                    if player.next_up and player.player_id and starter:
                        found[player.player_id] = starter.name
        cache[team] = found
    return cache[team]


def _advice(  # noqa: PLR0913, PLR0917
    session: Session,
    league: LeagueRow,
    roster: RosterRow,
    top: list[tuple[float, PlayerRow, str]],
    projections: dict[str, float],
    slots: list[str],
    week: int,
    key: str,
    lineup: list[tuple[str, str]],
    players: dict[str, PlayerRow],
) -> dict[str, object] | None:
    """The model's ranking of the computed pickups for this roster, or None (also None when this
    team already has the alert, so the model is asked once per event)."""
    if already_told(session, league.league_id, roster.roster_id, key):
        return None
    options = [
        alert_advice.option(p, "pickup", projections[p.player_id], gain=round(gain, 1), over=over)
        for gain, p, over in top
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


@register("waiver_targets")
def detect_waiver_targets(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    waiver = waiver_date_if_tomorrow(league, now)
    week = coming_week(session, league.season, waiver) if waiver else None
    if waiver is None or week is None:
        return []
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    taken = {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]}
    projected_ids = set(
        session.scalars(
            select(PlayerProjectionRow.player_id).where(
                PlayerProjectionRow.season == league.season, PlayerProjectionRow.week == week
            )
        )
    )
    if not projected_ids:
        return []  # nothing is projected yet: say nothing now, the next run tries again
    projections = projected_points(
        session, league.season, week, league.scoring_settings, projected_ids
    )
    byes = {t for t, g in games_for_week(session, league.season, week).items() if g.state == "bye"}
    players = {
        p.player_id: p
        for p in session.scalars(
            select(PlayerRow).where(
                PlayerRow.player_id.in_(projected_ids | taken), PlayerRow.position.in_(POSITIONS)
            )
        )
    }

    def playable(p: PlayerRow) -> bool:
        return (
            p.team is not None
            and p.team not in byes
            and (p.injury_status or "") not in NOT_PLAYABLE
        )

    free = [
        p
        for pid, p in players.items()
        if pid not in taken
        and pid in projected_ids
        and playable(p)
        and projections.get(pid, 0.0) > 0
    ]
    trends = {
        t.player_id: t
        for t in session.scalars(
            select(PlayerTrendRow).where(PlayerTrendRow.player_id.in_([p.player_id for p in free]))
        )
    }
    slots = starter_slots(league)
    depth_cache: dict[str, dict[str, str]] = {}
    when = f"{day_name(waiver)}, {waiver.strftime('%b')} {waiver.day}"

    raised: list[NewAlert] = []
    for roster in rosters:
        # the team's best lineup from the players who could actually play this week
        healthy = [
            (pid, players[pid].position or "", projections.get(pid, 0.0))
            for pid in roster.players
            if pid in players
            and pid not in roster.reserve
            and pid not in roster.taxi
            and playable(players[pid])
        ]
        lineup = assign_lineup(slots, healthy)
        scored: list[tuple[float, PlayerRow, str]] = []
        for p in free:
            slot, base, holder = replaced_by(slots, lineup, projections, p.position or "")
            gain = projections[p.player_id] - base
            if gain < MIN_GAIN:
                continue
            if holder is None:
                over = f"at an open {slot} spot"
            else:
                over = f"over {players[holder].full_name or holder} at {slot}"
            scored.append((gain, p, over))
        scored.sort(key=lambda item: (-item[0], -projections[item[1].player_id], item[1].player_id))
        top = scored[:TARGETS]
        if not top:
            continue  # nothing useful for this team: no alert, nothing padded
        lines: list[str] = []
        targets: list[dict[str, object]] = []
        for gain, p, over in top:
            pid = p.player_id
            name = p.full_name or pid
            detail = (
                f"({p.position}, {p.team}): projected {projections[pid]:.1f}, +{gain:.1f} {over}."
            )
            adds = trends[pid].adds if pid in trends else None
            if adds:
                detail += f" Added in {adds:,} leagues in the last day."
            out_starter = _opening(session, league, p.team or "", depth_cache).get(pid)
            if out_starter:
                detail += f" {out_starter} is out ahead of him."
            lines.append(f"{name} {detail}")
            targets.append(
                {
                    "player_id": pid,
                    "name": name,
                    "position": p.position,
                    "team": p.team,
                    "projected": round(projections[pid], 1),
                    "gain": round(gain, 1),
                    "detail": detail,
                    "line": f"{name} {detail}",
                }
            )
        key = f"waiver_targets:{league.league_id}:{waiver.isoformat()}"
        advice = _advice(
            session, league, roster, top, projections, slots, week, key, lineup, players
        )
        raised.append(
            NewAlert(
                roster_id=roster.roster_id,
                kind="waiver_targets",
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
