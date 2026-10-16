"""The waiver wire page: this cycle's adds for one team, ranked like the waiver alert."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from sleeper_assistant.alert_waiver import detect_waiver_targets
from sleeper_assistant.alerts import run_alerts
from sleeper_assistant.db import AlertRow, PlayerOwnershipRow, PlayerProjectionRow, utcnow
from sleeper_assistant.waiver_wire import build_waiver_wire, next_waiver_date
from test_alert_waiver import MONDAY_EVENING, _league, _setup

SUNDAY = datetime(2026, 10, 18, 16, 0, tzinfo=UTC)


def test_the_cycle_resets_on_the_waiver_day_in_eastern_time() -> None:
    league = _league()  # Tuesday by default
    assert next_waiver_date(league, SUNDAY) == date(2026, 10, 20)
    assert next_waiver_date(league, MONDAY_EVENING) == date(2026, 10, 20)  # Monday 7pm ET
    # Tuesday 12:30am ET (04:30 UTC) is the waiver day: the list is already the next cycle's
    assert next_waiver_date(league, datetime(2026, 10, 20, 4, 30, tzinfo=UTC)) == date(2026, 10, 27)
    assert next_waiver_date(league, datetime(2026, 10, 21, 3, 0, tzinfo=UTC)) == date(2026, 10, 27)
    assert next_waiver_date(_league(waiver_day_of_week=4), SUNDAY) == date(2026, 10, 22)


def test_the_list_has_the_same_players_in_the_same_order_as_the_alert(session: Session) -> None:
    league = _setup(session)
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    alert = session.query(AlertRow).filter_by(roster_id=1).one()
    wire = build_waiver_wire(session, league, 1, MONDAY_EVENING)
    assert [e.player_id for e in wire.entries] == [
        t["player_id"]
        for t in alert.data["targets"]  # type: ignore[union-attr]
    ]
    assert (wire.waiver_day, wire.waiver_date, wire.week) == ("Tuesday", date(2026, 10, 20), 7)


def test_each_entry_shows_its_signals_and_how_many_back_it(session: Session) -> None:
    league = _setup(session)
    session.add(
        PlayerOwnershipRow(player_id="fa_wr", owned=41.5, started=12.0, fetched_at=utcnow())
    )
    session.commit()
    wire = build_waiver_wire(session, league, 1, MONDAY_EVENING)
    horton = next(e for e in wire.entries if e.player_id == "fa_wr")
    assert (horton.projected, horton.gain, horton.owned) == (11.4, 3.4, 41.5)
    assert horton.backing == 1  # trending adds; no depth chart opening
    assert [(s.source, s.backs) for s in horton.signals] == [
        ("Sleeper trending adds", True),
        ("NFL depth chart", False),
    ]
    assert (
        "added in 8,200 leagues" in horton.reason and "+3.4 over Second Receiver" in horton.reason
    )
    back = next(e for e in wire.entries if e.player_id == "fa_rb")
    assert back.backing == 0 and back.owned is None


def test_only_available_playable_players_appear(session: Session) -> None:
    league = _setup(session)
    wire = build_waiver_wire(session, league, 1, MONDAY_EVENING)
    ids = {e.player_id for e in wire.entries}
    assert ids.isdisjoint({"wr1", "wr2", "fa_out", "fa_bye", "fa_none", "fa_low"})


def test_empty_lists_say_why(session: Session) -> None:
    league = _setup(session)
    assert (
        "nobody available"
        in (build_waiver_wire(session, league, 2, MONDAY_EVENING).note or "").lower()
    )
    assert (
        build_waiver_wire(session, league, 9, MONDAY_EVENING).note
        == "That team is not in this league."
    )
    session.query(PlayerProjectionRow).delete()
    session.commit()
    assert "projections are not out" in (
        build_waiver_wire(session, league, 1, MONDAY_EVENING).note or ""
    )


def test_no_schedule_means_a_note_not_a_crash(session: Session) -> None:
    league = _league()
    session.add(league)
    session.commit()
    assert (
        build_waiver_wire(session, league, 1, MONDAY_EVENING).note
        == "The NFL schedule is not loaded yet."
    )


def test_when_no_games_are_left_the_page_says_so(session: Session) -> None:
    league = _setup(session)
    late = datetime(2027, 3, 1, 15, 0, tzinfo=UTC)
    wire = build_waiver_wire(session, league, 1, late)
    assert wire.entries == [] and wire.week is None
    assert "no games left" in (wire.note or "")
