"""The waiver targets alert: each team's best pickups, the day before the league's waiver day.

The waiver day is read from the league's own Sleeper settings (``waiver_day_of_week``, where 0 is
Sunday so Tuesday is 2) with Tuesday as the default when it is missing, and the day is judged in US
Eastern time, the clock waivers run on. On the day before, the first alert run raises one alert per
team (the dedupe key names the waiver date, so later runs and later days add nothing).

A target is an available player projected for the coming week, ranked by how much he would help
*that* team: his projected points (scored with the league's own rules) minus those of the team's
weakest starter-level player at his position. "Starter-level" means the team's k-th best player at
the position, where k is the league's number of starting spots a player of that position can fill;
a team with fewer players than that gains the whole projection ("fills an open starter spot"). Only
players with a projection are suggested, and players on a bye or ruled out are skipped.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alerts import NewAlert, register
from sleeper_assistant.dashboard import current_week, games_for_week, starter_slots
from sleeper_assistant.db import (
    LeagueRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    RosterRow,
)
from sleeper_assistant.lineup_slots import eligible_positions
from sleeper_assistant.projections import projected_points
from sleeper_assistant.team_depth import OUT_STATUSES, build_team_depth

EASTERN = ZoneInfo("America/New_York")
DEFAULT_WAIVER_DAY = 2  # Tuesday, with Sunday as 0 (Sleeper's numbering)
TARGETS = 5  # how many pickups an alert lists
MIN_GAIN = 1.0  # projected points a pickup must add to be worth a mention
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def waiver_day(league: LeagueRow) -> int:
    """The league's waiver weekday, 0 = Sunday .. 6 = Saturday; Tuesday when unset or invalid."""
    value = league.settings.get("waiver_day_of_week")
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 6:  # noqa: PLR2004
        return value
    return DEFAULT_WAIVER_DAY


def waiver_date_if_tomorrow(league: LeagueRow, now: datetime) -> date | None:
    """The coming waiver date when today (US Eastern) is the day before it, otherwise None."""
    today = now.astimezone(EASTERN).date()
    tomorrow = today + timedelta(days=1)
    sleeper_weekday = (tomorrow.weekday() + 1) % 7  # Python has Monday as 0; Sleeper has Sunday
    return tomorrow if sleeper_weekday == waiver_day(league) else None


def day_name(waiver: date) -> str:
    return _DAYS[(waiver.weekday() + 1) % 7]


def starter_level(slots: list[str], position: str) -> int:
    """How many starting spots a player of this position can fill in this league (at least 1)."""
    return max(1, sum(1 for slot in slots if position in eligible_positions(slot, position)))


def baseline(roster_points: list[tuple[str, float]], k: int) -> tuple[str | None, float, int]:
    """The team's weakest starter-level player at a position: (name or None, points, rank k).

    ``roster_points`` is the team's players at the position as (name, projected points). With fewer
    than k of them there is an open starter spot, worth nothing yet.
    """
    ranked = sorted(roster_points, key=lambda item: -item[1])
    if len(ranked) < k:
        return None, 0.0, len(ranked) + 1
    name, points = ranked[k - 1]
    return name, points, k


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


@register("waiver_targets")
def detect_waiver_targets(session: Session, league: LeagueRow, now: datetime) -> list[NewAlert]:
    waiver = waiver_date_if_tomorrow(league, now)
    week = current_week(session, league.season)
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
    projections = projected_points(
        session, league.season, week, league.scoring_settings, projected_ids
    )
    byes = {t for t, g in games_for_week(session, league.season, week).items() if g.state == "bye"}
    players = {
        p.player_id: p
        for p in session.scalars(
            select(PlayerRow).where(
                PlayerRow.player_id.in_(projected_ids), PlayerRow.position.in_(POSITIONS)
            )
        )
    }
    free = [
        p
        for pid, p in players.items()
        if pid not in taken
        and p.team is not None
        and p.team not in byes
        and (p.injury_status or "") not in OUT_STATUSES
        and projections.get(pid, 0.0) > 0
    ]
    trends = {t.player_id: t for t in session.scalars(select(PlayerTrendRow))}
    slots = starter_slots(league)
    depth_cache: dict[str, dict[str, str]] = {}
    when = f"{day_name(waiver)}, {waiver.strftime('%b')} {waiver.day}"

    raised: list[NewAlert] = []
    for roster in rosters:
        owned = {
            p.player_id: p
            for p in session.scalars(
                select(PlayerRow).where(PlayerRow.player_id.in_([*roster.players]))
            )
        }
        by_position: dict[str, list[tuple[str, float]]] = {}
        for pid, p in owned.items():
            if pid in roster.reserve or pid in roster.taxi or not p.position:
                continue
            by_position.setdefault(p.position, []).append(
                (p.full_name or pid, projections.get(pid, 0.0))
            )
        scored: list[tuple[float, PlayerRow, str]] = []
        for p in free:
            position = p.position or ""
            level = starter_level(slots, position)
            name, base, rank = baseline(by_position.get(position, []), level)
            gain = projections[p.player_id] - base
            if gain < MIN_GAIN:
                continue
            over = (
                f"over your {position}{rank} ({name})"
                if name
                else f"at {position}{rank}, an open starter spot"
            )
            scored.append((gain, p, over))
        scored.sort(key=lambda item: (-item[0], -projections[item[1].player_id], item[1].player_id))
        top = scored[:TARGETS]
        if not top:
            continue  # nothing useful for this team: no alert, nothing padded
        lines: list[str] = []
        targets: list[dict[str, object]] = []
        for gain, p, over in top:
            pid = p.player_id
            line = (
                f"{p.full_name or pid} ({p.position}, {p.team}): projected "
                f"{projections[pid]:.1f}, +{gain:.1f} {over}."
            )
            adds = trends[pid].adds if pid in trends else None
            if adds:
                line += f" Added in {adds:,} leagues in the last day."
            out_starter = _opening(session, league, p.team or "", depth_cache).get(pid)
            if out_starter:
                line += f" {out_starter} is out ahead of him."
            lines.append(line)
            targets.append(
                {
                    "player_id": pid,
                    "name": p.full_name or pid,
                    "position": p.position,
                    "team": p.team,
                    "projected": round(projections[pid], 1),
                    "gain": round(gain, 1),
                    "line": line,
                }
            )
        raised.append(
            NewAlert(
                roster_id=roster.roster_id,
                kind="waiver_targets",
                dedupe_key=f"waiver_targets:{league.league_id}:{waiver.isoformat()}",
                title=f"Top waiver targets for {when}",
                why=" ".join(f"{i}. {line}" for i, line in enumerate(lines, start=1)),
                data={"week": week, "waiver_date": waiver.isoformat(), "targets": targets},
            )
        )
    return raised
