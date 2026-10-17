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

from dataclasses import dataclass, replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant import alert_advice
from sleeper_assistant.alerts import NewAlert, needs_advice, register
from sleeper_assistant.db import (
    LeagueRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    RosterRow,
)
from sleeper_assistant.lineup_slots import assign_lineup, eligible_positions, starter_slots
from sleeper_assistant.matchup_rank import (
    DefenseTable,
    MatchupRank,
    build_defense_table,
    matchup_rank,
)
from sleeper_assistant.nfl_games import games_for_week
from sleeper_assistant.projections import projected_points
from sleeper_assistant.rankings import recent_form
from sleeper_assistant.team_depth import OUT_STATUSES, build_team_depth
from sleeper_assistant.waiver_calendar import coming_week, day_name, waiver_date_if_tomorrow

TARGETS = 5  # how many pickups an alert lists
ALERT_CAPS = {"QB": 2, "TE": 2, "K": 1, "DEF": 1}  # one slot each: do not list four defenses
MIN_GAIN = 1.0  # projected points a pickup must add to be worth a mention
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
NOT_PLAYABLE = OUT_STATUSES | {"Doubtful"}  # someone who probably will not play is no pickup


def display_name(p: PlayerRow) -> str:
    """A player's name for people: a team defense is "CLE defense", not just "CLE"."""
    if p.position == "DEF" and p.team:
        return f"{p.team} defense"
    return p.full_name or p.player_id


def capped(picks: list[Pickup], caps: dict[str, int], limit: int | None = None) -> list[Pickup]:
    """The best-first ``picks`` with at most ``caps[position]`` of a position, then the best
    ``limit``: only one defense can start, so a list of four is not four defenses."""
    counts: dict[str, int] = {}
    kept: list[Pickup] = []
    for pick in picks:
        position = pick.player.position or ""
        if counts.get(position, 0) >= caps.get(position, len(picks)):
            continue
        counts[position] = counts.get(position, 0) + 1
        kept.append(pick)
    return kept[:limit]


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


@dataclass(frozen=True)
class Pickup:
    """An available player and what he would add to one team."""

    player: PlayerRow
    projected: float
    gain: float  # projected points over the player (or empty slot) he would replace
    slot: str
    over: str  # "over Second Receiver at WR" or "at an open RB spot"
    adds: int | None  # Sleeper leagues that added him in the last day
    out_starter: str | None  # the out starter ahead of him on his NFL depth chart
    matchup: MatchupRank | None = None  # how the opponent's defense ranks against his position
    form: float | None = None  # points a game over his last three, under this league's scoring
    status: str | None = None  # his injury designation (Questionable, ...) if any
    drop: str | None = None  # the player he would take the place of, if any


class WaiverBoard:
    """The week's available players with projections, ready to rank for any team of the league.

    Built once per league and week; the waiver alert and the waiver wire page both rank through
    ``pickups`` so they agree.
    """

    def __init__(self, session: Session, league: LeagueRow, week: int) -> None:
        self.session, self.league, self.week = session, league, week
        self.rosters = list(
            session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
        )
        taken = {pid for r in self.rosters for pid in [*r.players, *r.reserve, *r.taxi]}
        projected_ids = set(
            session.scalars(
                select(PlayerProjectionRow.player_id).where(
                    PlayerProjectionRow.season == league.season,
                    PlayerProjectionRow.week == week,
                )
            )
        )
        self.has_projections = bool(projected_ids)
        self.projections = projected_points(
            session, league.season, week, league.scoring_settings, projected_ids
        )
        self.games = games_for_week(session, league.season, week)
        self.byes = {t for t, g in self.games.items() if g.state == "bye"}
        self._defense: DefenseTable | None = None
        self._form: dict[str, float] | None = None
        self.players = {
            p.player_id: p
            for p in session.scalars(
                select(PlayerRow).where(
                    PlayerRow.player_id.in_(projected_ids | taken),
                    PlayerRow.position.in_(POSITIONS),
                )
            )
        }
        self.free = [
            p
            for pid, p in self.players.items()
            if pid not in taken
            and pid in projected_ids
            and self.playable(p)
            and self.projections.get(pid, 0.0) > 0
        ]
        self.trends = {
            t.player_id: t
            for t in session.scalars(
                select(PlayerTrendRow).where(
                    PlayerTrendRow.player_id.in_([p.player_id for p in self.free])
                )
            )
        }
        self.slots = starter_slots(league.roster_positions)
        self._depth: dict[str, dict[str, str]] = {}

    @property
    def defense(self) -> DefenseTable:
        """The defense-rank table, built the first time it is needed (the alert never needs it)."""
        if self._defense is None:
            self._defense = build_defense_table(
                self.session, self.league.season, self.league.scoring_settings
            )
        return self._defense

    @property
    def form(self) -> dict[str, float]:
        """Each player's recent points a game, built the first time it is needed."""
        if self._form is None:
            self._form = recent_form(
                self.session, self.league.season, self.week, self.league.scoring_settings
            )
        return self._form

    def playable(self, p: PlayerRow) -> bool:
        return (
            p.team is not None
            and p.team not in self.byes
            and (p.injury_status or "") not in NOT_PLAYABLE
        )

    def lineup(self, roster: RosterRow) -> list[tuple[str, str]]:
        """The team's best lineup from the players who could actually play this week."""
        healthy = [
            (pid, self.players[pid].position or "", self.projections.get(pid, 0.0))
            for pid in roster.players
            if pid in self.players
            and pid not in roster.reserve
            and pid not in roster.taxi
            and self.playable(self.players[pid])
        ]
        return assign_lineup(self.slots, healthy)

    def pickups(
        self,
        roster: RosterRow,
        lineup: list[tuple[str, str]],
        limit: int | None = None,
        caps: dict[str, int] | None = None,
        detail: bool = False,
    ) -> list[Pickup]:
        """The available players who would help this team by ``MIN_GAIN`` or more, best first
        (at most ``caps[position]`` of a position, then the best ``limit``; the depth chart is
        only read for those)."""
        found: list[Pickup] = []
        for p in self.free:
            slot, base, holder = replaced_by(self.slots, lineup, self.projections, p.position or "")
            gain = self.projections[p.player_id] - base
            if gain < MIN_GAIN:
                continue
            if holder is None:
                over = f"at an open {slot} spot"
            else:
                over = f"over {display_name(self.players[holder])} at {slot}"
            trend = self.trends.get(p.player_id)
            found.append(
                Pickup(
                    p,
                    self.projections[p.player_id],
                    gain,
                    slot,
                    over,
                    trend.adds if trend else None,
                    None,
                    None,
                    None,
                    p.injury_status or None,
                    display_name(self.players[holder]) if holder else None,
                )
            )
        found.sort(key=lambda x: (-x.gain, -x.projected, x.player.player_id))
        if caps is not None:
            found = capped(found, caps)
        return [self._fill(pick, detail) for pick in found[:limit]]

    def _fill(self, pick: Pickup, detail: bool) -> Pickup:
        """Add what is only worth reading for the picks that are kept: the depth chart opening,
        and (for the page, not the alert) the matchup and recent form."""
        p = pick.player
        opening = _opening(self.session, self.league, p.team or "", self._depth).get(p.player_id)
        if not detail:
            return replace(pick, out_starter=opening)
        game = self.games.get(p.team or "")
        return replace(
            pick,
            out_starter=opening,
            matchup=matchup_rank(self.defense, p.position or "", game.opponent if game else None),
            form=self.form.get(p.player_id),
        )


@register("waiver_targets")
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
            name = display_name(p)
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
        key = f"waiver_targets:{league.league_id}:{waiver.isoformat()}"
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
