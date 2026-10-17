"""The waiver wire page: this cycle's adds for one team, ranked like the waiver alert."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from sleeper_assistant.alerts.engine import run_alerts
from sleeper_assistant.alerts.waiver import detect_waiver_targets
from sleeper_assistant.core.league.waiver_board import Pickup
from sleeper_assistant.core.nfl.matchup_rank import MatchupRank
from sleeper_assistant.db import (
    AlertRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerWeekStatsRow,
    utcnow,
)
from sleeper_assistant.views.waiver_wire import build_waiver_wire, next_waiver_date, reasons_for
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


def test_each_entry_lists_only_the_reasons_that_apply_marked_for_or_against(
    session: Session,
) -> None:
    league = _setup(session)
    session.add(
        PlayerOwnershipRow(player_id="fa_wr", owned=41.5, started=12.0, fetched_at=utcnow())
    )
    session.commit()
    wire = build_waiver_wire(session, league, 1, MONDAY_EVENING)
    horton = next(e for e in wire.entries if e.player_id == "fa_wr")
    assert (horton.projected, horton.gain, horton.owned) == (11.4, 3.4, 41.5)
    stances = [(r.label, r.stance) for r in horton.reasons]
    assert ("Adds points", "for") in stances and ("Trending adds", "for") in stances
    assert ("Ownership", "info") in stances
    # no depth chart opening: that is simply absent, never listed as a mark against him
    assert all(r.label != "Starter out ahead" for r in horton.reasons)
    assert all(r.stance != "against" or r.label != "Starter out ahead" for r in horton.reasons)
    assert horton.for_count == 2 and horton.against_count == 0
    assert (
        "added in 8,200 leagues" in horton.reason and "+3.4 over Second Receiver" in horton.reason
    )
    back = next(e for e in wire.entries if e.player_id == "fa_rb")
    assert back.owned is None and not any(r.label == "Ownership" for r in back.reasons)


def test_a_questionable_player_and_a_cold_streak_count_against(session: Session) -> None:
    league = _setup(session)
    session.get(PlayerRow, "fa_wr").injury_status = "Questionable"  # type: ignore[union-attr]
    session.add(
        PlayerWeekStatsRow(season="2026", week=5, player_id="fa_wr", team="SF",
                           stats={"gp": 1, "rec_yd": 20.0}, fetched_at=utcnow())
    )  # fmt: skip
    session.commit()
    wire = build_waiver_wire(session, league, 1, MONDAY_EVENING)
    horton = next(e for e in wire.entries if e.player_id == "fa_wr")
    against = {r.label for r in horton.reasons if r.stance == "against"}
    assert {"Injury", "Cold lately"} <= against
    assert horton.against_count == len(against)


def test_a_soft_or_tough_matchup_is_a_reason(session: Session) -> None:
    player = PlayerRow(player_id="p", full_name="P", position="WR", team="SF", external_ids={})
    base = {"player": player, "projected": 12.0, "gain": 4.0, "slot": "WR", "over": "over X at WR",
            "adds": None, "out_starter": None}  # fmt: skip

    def labels(rank: int) -> set[str]:
        m = MatchupRank(opponent="JAX", rank=rank, teams=32, points=20.0, games=5)
        return {r.label for r in reasons_for(Pickup(**base, matchup=m), None)}

    assert "Soft matchup" in labels(3)
    assert "Tough matchup" in labels(30)
    assert not {"Soft matchup", "Tough matchup"} & labels(16)


def test_one_defense_does_not_fill_the_list_and_defenses_are_named(session: Session) -> None:
    league = _setup(session)
    for code in ("CLE", "NYJ", "TEN", "CAR", "DEN"):
        session.add(PlayerRow(player_id=f"d_{code}", full_name=code, position="DEF", team=code,
                              external_ids={}))  # fmt: skip
        session.add(_proj_def(f"d_{code}", code))
    session.commit()
    wire = build_waiver_wire(session, league, 1, MONDAY_EVENING)
    defenses = [e for e in wire.entries if e.position == "DEF"]
    assert 0 < len(defenses) <= 4  # capped, however many are free
    assert defenses[0].name.endswith(" defense")  # "CLE defense", not just "CLE"
    top_defenses = [e for e in wire.entries if e.player_id in wire.top and e.position == "DEF"]
    assert len(top_defenses) <= 1  # the mixed view has one slot's worth
    assert len(wire.top) <= 10


def _proj_def(pid: str, team: str) -> PlayerProjectionRow:
    return PlayerProjectionRow(
        season="2026", week=7, player_id=pid, team=team, stats={"rec_yd": 90.0}, fetched_at=utcnow()
    )  # fmt: skip  (scored: 9.0 points)


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
