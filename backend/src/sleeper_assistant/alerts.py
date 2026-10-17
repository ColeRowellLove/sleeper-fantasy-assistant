"""The alert engine: detectors look at synced data and raise alerts for a team, once per event.

A detector is a function ``(session, league, now) -> list[NewAlert]``. Detectors register by name
(see ``register``); the engine runs every one of them for a league, stores what they raise, and
never lets one failing detector stop the others. An alert is stored once per (league, team, dedupe
key), so running the engine again and again about the same event creates nothing more.

A detector's dedupe key must name the *occurrence*, not just the subject:
``injury_out:<player>:<week>`` alerts again the next time he is ruled out, whereas
``injury_out:<player>`` would never alert that team about him a second time. Old alerts are pruned
after ``KEEP``, so keys only need to be unique within that time.

A detector module follows the same pattern as the others: a ``KIND`` constant used for the
registered name, the alert's ``kind`` and its key (``alert_key(KIND, ...)``); the window check
``lineup_week`` when the alert is only useful close to kickoff; ``player_tag`` for how a title
names a player; and a ``why`` that is one line with the numbers behind it (see ``alert_helpers``).

How an alert reaches a person outside the app (email, push, SMS) is a separate step on top of the
stored alerts; this module only decides *what* is worth saying and says it once.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sleeper_assistant.db import AlertRow, LeagueRow, as_utc, utcnow

log = logging.getLogger(__name__)

RECENT = timedelta(days=14)  # the app shows alerts this recent
KEEP = timedelta(days=90)  # older alerts are deleted
ADVICE_RETRY = timedelta(hours=3)  # an alert still without model advice is retried this long


class NewAlert(BaseModel):
    """What a detector raises. The ``dedupe_key`` names the event: one alert per team per key."""

    roster_id: int
    kind: str
    dedupe_key: str
    title: str
    why: str  # one line with the numbers behind it
    player_id: str | None = None
    data: dict[str, object] = Field(default_factory=dict)


Detector = Callable[[Session, LeagueRow, datetime], list[NewAlert]]

# global steps that run once per run, before any league's detectors (for example recording a change
# that every league's detector then reads); they are not league-specific
PreRun = Callable[[Session, datetime], None]

DETECTORS: dict[str, Detector] = {}
PRE_RUN: dict[str, PreRun] = {}


def register(name: str) -> Callable[[Detector], Detector]:
    """Add a detector to the engine under a unique name (a decorator)."""

    def add(detector: Detector) -> Detector:
        if name in DETECTORS:
            raise ValueError(f"alert detector {name!r} is already registered")
        DETECTORS[name] = detector
        return detector

    return add


def register_pre_run(name: str) -> Callable[[PreRun], PreRun]:
    """Add a global step that runs once before the detectors of a whole run (a decorator)."""

    def add(step: PreRun) -> PreRun:
        if name in PRE_RUN:
            raise ValueError(f"alert step {name!r} is already registered")
        PRE_RUN[name] = step
        return step

    return add


def store_new(session: Session, league: LeagueRow, raised: list[NewAlert], now: datetime) -> int:
    """Save the alerts whose event has not alerted that team before; returns how many were new."""
    if not raised:
        return 0
    keys = {a.dedupe_key for a in raised}
    seen: dict[tuple[int, str], AlertRow | None] = {
        (row.roster_id, row.dedupe_key): row
        for row in session.scalars(
            select(AlertRow).where(
                AlertRow.league_id == league.league_id, AlertRow.dedupe_key.in_(keys)
            )
        )
    }
    created = 0
    for alert in raised:
        marker = (alert.roster_id, alert.dedupe_key)
        if marker in seen:
            existing = seen[marker]
            if (
                existing is not None
                and alert.data.get("advice")
                and not (existing.data or {}).get("advice")
            ):
                existing.data = {**(existing.data or {}), "advice": alert.data["advice"]}
            continue  # already told, or raised twice in the same run
        seen[marker] = None
        try:
            with session.begin_nested():  # a run that overlaps this one may insert the same event
                session.add(
                    AlertRow(
                        league_id=league.league_id,
                        roster_id=alert.roster_id,
                        kind=alert.kind,
                        dedupe_key=alert.dedupe_key,
                        player_id=alert.player_id,
                        title=alert.title,
                        why=alert.why,
                        data=alert.data,
                        created_at=now,
                    )
                )
                session.flush()
        except IntegrityError:
            continue  # someone else just told that team; not a failure
        created += 1
    return created


def needs_advice(
    session: Session, league_id: str, roster_id: int, dedupe_key: str, now: datetime
) -> bool:
    """Whether the model should be asked about this event for this team.

    Yes for a new event, and for one stored without advice (the model failed or was throttled) for
    ``ADVICE_RETRY`` after it was raised; no once it has advice, or after that window.
    """
    row = session.scalars(
        select(AlertRow).where(
            AlertRow.league_id == league_id,
            AlertRow.roster_id == roster_id,
            AlertRow.dedupe_key == dedupe_key,
        )
    ).first()
    if row is None:
        return True
    return not (row.data or {}).get("advice") and as_utc(row.created_at) >= now - ADVICE_RETRY


def run_alerts(
    session: Session,
    league: LeagueRow,
    detectors: Mapping[str, Detector] | None = None,
    now: datetime | None = None,
) -> int:
    """Run every detector for one league and store the new alerts. A failing detector is logged
    and skipped (its half-done work rolled back); the others still run. Returns alerts created."""
    moment = now or utcnow()
    created = 0
    for name, detector in (DETECTORS if detectors is None else detectors).items():
        try:
            with session.begin_nested():
                created += store_new(session, league, detector(session, league, moment), moment)
        except Exception:  # one broken detector must not silence the rest
            log.exception("alert detector %s failed for league %s", name, league.league_id)
    session.commit()
    return created


def run_all_leagues(
    session: Session,
    active_since: datetime,
    detectors: Mapping[str, Detector] | None = None,
    now: datetime | None = None,
) -> int:
    """Run the engine for every league viewed since ``active_since`` (the ones the worker syncs)."""
    moment = now or utcnow()
    for name, step in PRE_RUN.items():
        try:
            step(session, moment)
            session.commit()
        except Exception:  # a failed global step is logged; the detectors still run
            session.rollback()
            log.exception("alert step %s failed", name)
    leagues = list(
        session.scalars(select(LeagueRow).where(LeagueRow.last_viewed_at >= active_since))
    )
    created = 0
    for league in leagues:
        try:
            created += run_alerts(session, league, detectors, moment)
        except Exception:  # a database error on one league must not skip the others
            session.rollback()
            log.exception("alerts failed for league %s", league.league_id)
    session.execute(
        delete(AlertRow)
        .where(AlertRow.created_at < moment - KEEP)
        .execution_options(synchronize_session=False)  # decided in SQL, not by comparing objects
    )
    session.commit()
    return created


class AlertItem(BaseModel):
    id: int
    kind: str
    title: str
    why: str
    player_id: str | None
    created_at: datetime
    data: dict[str, object]


class AlertsView(BaseModel):
    league_id: str
    roster_id: int
    alerts: list[AlertItem]  # newest first, the last 14 days


def build_alerts(
    session: Session, league_id: str, roster_id: int, limit: int = 50, now: datetime | None = None
) -> AlertsView:
    """A team's recent alerts, newest first."""
    since = (now or utcnow()) - RECENT
    rows = session.scalars(
        select(AlertRow)
        .where(
            AlertRow.league_id == league_id,
            AlertRow.roster_id == roster_id,
            AlertRow.created_at >= since,
        )
        .order_by(AlertRow.created_at.desc(), AlertRow.id.desc())
        .limit(limit)
    )
    return AlertsView(
        league_id=league_id,
        roster_id=roster_id,
        alerts=[
            AlertItem(
                id=r.id,
                kind=r.kind,
                title=r.title,
                why=r.why,
                player_id=r.player_id,
                created_at=as_utc(r.created_at),
                data=r.data or {},
            )
            for r in rows
        ],
    )
