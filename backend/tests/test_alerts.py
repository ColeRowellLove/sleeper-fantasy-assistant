"""The alert engine: detectors raise alerts, stored once per team per event, failures isolated."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant import alerts
from sleeper_assistant.alerts import (
    Detector,
    NewAlert,
    build_alerts,
    run_alerts,
    run_all_leagues,
)
from sleeper_assistant.db import AlertRow, LeagueRow, utcnow


def _league(session: Session, league_id: str = "L1", viewed: bool = True) -> LeagueRow:
    league = LeagueRow(
        league_id=league_id, name=league_id, season="2026", total_rosters=2, scoring_settings={},
        roster_positions=[], settings={}, last_viewed_at=utcnow() if viewed else None,
    )  # fmt: skip
    session.add(league)
    session.commit()
    return league


def _alert(roster_id: int = 1, key: str = "e1", **kw: object) -> NewAlert:
    base: dict[str, object] = {
        "roster_id": roster_id, "kind": "test", "dedupe_key": key, "title": f"Alert {key}",
        "why": "because of the numbers",
    }  # fmt: skip
    return NewAlert(**{**base, **kw})  # type: ignore[arg-type]


def _returns(*raised: NewAlert) -> Detector:
    return lambda _s, _l, _n: list(raised)


def test_a_raised_alert_is_stored_for_its_team(session: Session) -> None:
    league = _league(session)
    made = run_alerts(
        session, league, {"d": _returns(_alert(1, player_id="9", data={"slot": "RB"}))}
    )
    assert made == 1
    row = session.scalars(select(AlertRow)).one()
    assert (row.league_id, row.roster_id, row.kind, row.player_id) == ("L1", 1, "test", "9")
    assert (row.title, row.why, row.data) == ("Alert e1", "because of the numbers", {"slot": "RB"})


def test_the_same_event_never_alerts_a_team_twice_but_other_teams_and_events_do(
    session: Session,
) -> None:
    league = _league(session)
    detectors = {"d": _returns(_alert(1, "e1"), _alert(2, "e1"), _alert(1, "e2"))}
    assert run_alerts(session, league, detectors) == 3
    assert run_alerts(session, league, detectors) == 0  # run again: nothing new
    assert run_alerts(session, league, {"d": _returns(_alert(1, "e1"), _alert(1, "e3"))}) == 1
    assert session.scalars(select(AlertRow)).all().__len__() == 4


def test_an_event_raised_twice_in_one_run_is_stored_once(session: Session) -> None:
    league = _league(session)
    assert run_alerts(session, league, {"d": _returns(_alert(1, "e1"), _alert(1, "e1"))}) == 1


def test_a_failing_detector_is_logged_and_does_not_stop_the_others(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    league = _league(session)

    def broken(s: Session, lg: LeagueRow, now: object) -> list[NewAlert]:
        s.add(AlertRow(league_id=lg.league_id, roster_id=1, kind="x", dedupe_key="half",
                       title="half done", why="w", data={}, created_at=utcnow()))  # fmt: skip
        s.flush()
        raise RuntimeError("source down")

    detectors: dict[str, Detector] = {
        "a": _returns(_alert(1, "first")),
        "bad": broken,
        "z": _returns(_alert(1, "last")),
    }  # type: ignore[dict-item]
    with caplog.at_level("ERROR", logger="sleeper_assistant.alerts"):
        made = run_alerts(session, league, detectors)
    assert made == 2
    keys = {r.dedupe_key for r in session.scalars(select(AlertRow))}
    assert keys == {"first", "last"}  # the broken detector's half-done work was rolled back
    assert "alert detector bad failed" in caplog.text


def test_no_detectors_or_nothing_found_creates_nothing(session: Session) -> None:
    league = _league(session)
    assert run_alerts(session, league, {}) == 0
    assert run_alerts(session, league, {"d": _returns()}) == 0


def test_registering_adds_a_detector_once() -> None:
    @alerts.register("unit_test_only")
    def detect(_s: Session, _l: LeagueRow, _n: object) -> list[NewAlert]:
        return []

    try:
        assert alerts.DETECTORS["unit_test_only"] is detect
        with pytest.raises(ValueError, match="already registered"):
            alerts.register("unit_test_only")(detect)
    finally:
        alerts.DETECTORS.pop("unit_test_only", None)


def test_all_active_leagues_are_run_and_the_inactive_are_not(session: Session) -> None:
    _league(session, "L1")
    _league(session, "L2")
    _league(session, "L3", viewed=False)
    made = run_all_leagues(
        session, utcnow() - timedelta(days=1), {"d": _returns(_alert(1, "same"))}
    )
    assert made == 2  # one per active league; the key is only unique within a league
    assert {r.league_id for r in session.scalars(select(AlertRow))} == {"L1", "L2"}


def test_a_team_sees_its_own_recent_alerts_newest_first(session: Session) -> None:
    league = _league(session)
    now = utcnow()
    run_alerts(session, league, {"d": _returns(_alert(1, "old"))}, now - timedelta(days=3))
    run_alerts(session, league, {"d": _returns(_alert(1, "new"), _alert(2, "other"))}, now)
    run_alerts(session, league, {"d": _returns(_alert(1, "ancient"))}, now - timedelta(days=30))
    view = build_alerts(session, "L1", 1, now=now)
    assert [a.title for a in view.alerts] == [
        "Alert new",
        "Alert old",
    ]  # no other team, none older than 14 days
    assert build_alerts(session, "L1", 2, now=now).alerts[0].title == "Alert other"
    assert build_alerts(session, "L1", 3, now=now).alerts == []
    assert len(build_alerts(session, "L1", 1, limit=1, now=now).alerts) == 1
