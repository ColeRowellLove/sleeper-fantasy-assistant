"""The alert engine: detectors raise alerts, stored once per team per event, failures isolated."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alerts import engine as alerts
from sleeper_assistant.alerts.engine import (
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
    with caplog.at_level("ERROR", logger="sleeper_assistant.alerts.engine"):
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


def test_a_run_that_overlaps_another_does_not_fail_or_lose_the_other_alerts(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    league = _league(session)

    def raced(s: Session, lg: LeagueRow, now: object) -> list[NewAlert]:
        # another worker stores one of the two events between our check and our insert
        with s.begin_nested():
            s.add(
                AlertRow(
                    league_id=lg.league_id, roster_id=1, kind="test", dedupe_key="e1",
                    title="from the other run", why="w", data={}, created_at=utcnow(),
                )
            )  # fmt: skip
        return [_alert(1, "e1"), _alert(1, "e2")]

    with caplog.at_level("ERROR", logger="sleeper_assistant.alerts.engine"):
        made = run_alerts(session, league, {"d": raced})
    assert caplog.text == ""  # not reported as a detector failure
    assert made == 1  # e1 was already told; e2 is new
    titles = {r.dedupe_key: r.title for r in session.scalars(select(AlertRow))}
    assert titles == {"e1": "from the other run", "e2": "Alert e2"}


def test_one_leagues_database_error_does_not_skip_the_others(
    session: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _league(session, "L1")
    _league(session, "L2")
    real = alerts.run_alerts

    def flaky(s: Session, lg: LeagueRow, *a: object, **k: object) -> int:
        if lg.league_id == "L1":
            raise RuntimeError("database error")
        return real(s, lg, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(alerts, "run_alerts", flaky)
    with caplog.at_level("ERROR", logger="sleeper_assistant.alerts.engine"):
        made = run_all_leagues(
            session, utcnow() - timedelta(days=1), {"d": _returns(_alert(1, "x"))}
        )
    assert made == 1
    assert {r.league_id for r in session.scalars(select(AlertRow))} == {"L2"}
    assert "alerts failed for league L1" in caplog.text


def test_alerts_older_than_the_keep_time_are_deleted(session: Session) -> None:
    league = _league(session)
    now = utcnow()
    run_alerts(session, league, {"d": _returns(_alert(1, "ancient"))}, now - timedelta(days=120))
    run_alerts(session, league, {"d": _returns(_alert(1, "recent"))}, now - timedelta(days=5))
    run_all_leagues(session, now - timedelta(days=1), {}, now)
    assert [r.dedupe_key for r in session.scalars(select(AlertRow))] == ["recent"]


def test_times_come_back_as_utc_even_when_the_database_drops_the_zone(session: Session) -> None:
    league = _league(session)
    run_alerts(session, league, {"d": _returns(_alert(1))})
    alert = build_alerts(session, "L1", 1).alerts[0]
    assert alert.created_at.tzinfo is not None
    assert alert.model_dump_json().count("Z") == 1 or "+00:00" in alert.model_dump_json()


def test_a_global_step_runs_once_before_the_leagues_and_a_failing_one_does_not_stop_the_run(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    _league(session, "L1")
    _league(session, "L2")
    order: list[str] = []

    def step(_s: Session, _n: object) -> None:
        order.append("step")

    def broken(_s: Session, _n: object) -> None:
        raise RuntimeError("tracker down")

    def detector(_s: Session, lg: LeagueRow, _n: object) -> list[NewAlert]:
        order.append(lg.league_id)
        return []

    alerts.PRE_RUN.update({"t_step": step, "t_broken": broken})
    try:
        with caplog.at_level("ERROR", logger="sleeper_assistant.alerts.engine"):
            run_all_leagues(session, utcnow() - timedelta(days=1), {"d": detector})
    finally:
        alerts.PRE_RUN.pop("t_step", None)
        alerts.PRE_RUN.pop("t_broken", None)
    assert order.count("step") == 1 and order.index("step") < order.index("L1")
    assert sorted(o for o in order if o != "step") == ["L1", "L2"]
    assert "alert step t_broken failed" in caplog.text


def test_registering_a_global_step_twice_is_refused() -> None:
    @alerts.register_pre_run("unit_test_step")
    def step(_s: Session, _n: object) -> None:
        return None

    try:
        with pytest.raises(ValueError, match="already registered"):
            alerts.register_pre_run("unit_test_step")(step)
    finally:
        alerts.PRE_RUN.pop("unit_test_step", None)
