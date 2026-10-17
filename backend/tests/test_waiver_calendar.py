from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from sleeper_assistant.core.lineup_slots import starter_slots
from sleeper_assistant.core.waiver_calendar import (
    coming_week,
    day_name,
    waiver_date_if_tomorrow,
    waiver_day,
)
from sleeper_assistant.db import LeagueRow, NflGameRow


def _league(settings: dict[str, object]) -> LeagueRow:
    return LeagueRow(
        league_id="1", name="x", season="2026", total_rosters=2, scoring_settings={},
        roster_positions=[], settings=settings,
    )  # fmt: skip


def test_the_waiver_day_is_the_leagues_own_or_tuesday() -> None:
    assert waiver_day(_league({"waiver_day_of_week": 4})) == 4
    for bad in (None, 9, -1, True, "3"):
        assert waiver_day(_league({"waiver_day_of_week": bad})) == 2


def test_the_day_before_waivers_is_told_from_nine_am_eastern() -> None:
    league = _league({"waiver_day_of_week": 2})  # Tuesday
    monday_noon = datetime(2026, 10, 19, 16, 0, tzinfo=UTC)  # 12:00 Eastern
    monday_early = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)  # 8:00 Eastern
    assert waiver_date_if_tomorrow(league, monday_noon) == date(2026, 10, 20)
    assert waiver_date_if_tomorrow(league, monday_early) is None
    assert waiver_date_if_tomorrow(league, datetime(2026, 10, 20, 16, 0, tzinfo=UTC)) is None
    assert day_name(date(2026, 10, 20)) == "Tuesday"


def test_the_coming_week_is_the_first_one_starting_on_or_after_the_waiver(
    session: Session,
) -> None:
    for i, (week, day) in enumerate([(7, "2026-10-18"), (8, "2026-10-25")]):
        session.add(
            NflGameRow(
                game_id=f"g{i}", season="2026", week=week, home="A", away="B",
                status="pre_game", game_date=day,
            )
        )  # fmt: skip
    session.commit()
    assert coming_week(session, "2026", date(2026, 10, 20)) == 8


def test_starters_leave_out_the_bench_ir_and_taxi() -> None:
    assert starter_slots(["QB", "RB", "FLEX", "BN", "BN", "IR", "TAXI"]) == ["QB", "RB", "FLEX"]
