from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from sleeper_assistant.core.nfl_games import games_for_week
from sleeper_assistant.db import NflGameRow, utcnow
from sleeper_assistant.sync import jobs
from sleeper_assistant.sync.job_schedule import enqueue_kickoff_sync_if_due
from sleeper_assistant.sync.kickoffs import parse_conditions, parse_kickoffs, sync_kickoffs

CSV = """season,game_type,week,gameday,gametime,home_team,away_team
2026,REG,6,2026-10-18,13:00,SF,DAL
2026,REG,6,2026-10-18,16:25,LA,SEA
2026,REG,7,2026-10-25,,MIN,CHI
2026,POST,1,2027-01-10,16:30,SF,DAL
2025,REG,6,2025-10-19,13:00,SF,DAL
"""


def _http(body: str = CSV, status: int = 200) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(status, text=body)))


def test_parse_converts_eastern_to_utc_and_maps_the_rams() -> None:
    kickoffs = parse_kickoffs(CSV, "2026")
    # October is daylight time (UTC-4); the Rams are LAR on Sleeper but LA on nflverse
    assert kickoffs[(6, "SF", "DAL")] == datetime(2026, 10, 18, 17, 0, tzinfo=UTC)
    assert kickoffs[(6, "LAR", "SEA")] == datetime(2026, 10, 18, 20, 25, tzinfo=UTC)
    assert len(kickoffs) == 2  # no playoffs, no other season, no game without a time


def test_parse_handles_standard_time() -> None:
    csv_text = "season,game_type,week,gameday,gametime,home_team,away_team\n"
    csv_text += "2026,REG,11,2026-11-15,13:00,SF,DAL\n"  # after the clocks go back
    assert parse_kickoffs(csv_text, "2026")[(11, "SF", "DAL")] == datetime(
        2026, 11, 15, 18, 0, tzinfo=UTC
    )


def test_parse_skips_malformed_rows() -> None:
    csv_text = "season,game_type,week,gameday,gametime,home_team,away_team\n"
    csv_text += "2026,REG,x,2026-10-18,13:00,SF,DAL\n2026,REG,6,not-a-date,13:00,SF,DAL\n"
    assert parse_kickoffs(csv_text, "2026") == {}


def _game(gid: str, week: int, home: str, away: str) -> NflGameRow:
    return NflGameRow(
        game_id=gid, season="2026", week=week, home=home, away=away,
        game_date="2026-10-18", status="pre_game",
    )  # fmt: skip


def test_sync_stores_kickoffs_and_dashboard_exposes_them(session: Session) -> None:
    session.add_all(
        [_game("1", 6, "SF", "DAL"), _game("2", 6, "LAR", "SEA"), _game("3", 7, "MIN", "CHI")]
    )
    session.commit()

    assert sync_kickoffs(session, _http(), "2026") == 2  # week 7 has no time yet

    games = games_for_week(session, "2026", 6)
    assert games["SF"].kickoff == "2026-10-18T17:00:00Z"
    assert games["DAL"].kickoff == "2026-10-18T17:00:00Z"
    assert games["LAR"].kickoff == "2026-10-18T20:25:00Z"
    assert games_for_week(session, "2026", 7)["MIN"].kickoff is None


def test_sync_updates_a_moved_game_in_place(session: Session) -> None:
    session.add(_game("1", 6, "SF", "DAL"))
    session.commit()
    sync_kickoffs(session, _http(), "2026")
    moved = CSV.replace("2026-10-18,13:00,SF,DAL", "2026-10-19,20:15,SF,DAL")
    sync_kickoffs(session, _http(moved), "2026")
    session.expire_all()
    row = session.get(NflGameRow, "1")
    assert row is not None and row.kickoff is not None
    assert row.kickoff.replace(tzinfo=UTC) == datetime(2026, 10, 20, 0, 15, tzinfo=UTC)


def test_failed_download_raises_and_leaves_existing_times(session: Session) -> None:
    session.add(_game("1", 6, "SF", "DAL"))
    session.commit()
    sync_kickoffs(session, _http(), "2026")
    try:
        sync_kickoffs(session, _http("nope", status=503), "2026")
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("expected the failed download to raise")
    assert games_for_week(session, "2026", 6)["SF"].kickoff is not None


def test_kickoff_refresh_is_daily(session: Session) -> None:
    now = utcnow()
    assert enqueue_kickoff_sync_if_due(session, now)
    job = jobs.claim_next(session, now + timedelta(seconds=1))
    assert job is not None
    jobs.complete(session, job, now)
    assert not enqueue_kickoff_sync_if_due(session, now + timedelta(hours=23))
    assert enqueue_kickoff_sync_if_due(session, now + timedelta(hours=25))


WEATHER_CSV = """season,game_type,week,gameday,gametime,home_team,away_team,roof,surface,temp,wind,spread_line,total_line,stadium
2026,REG,6,2026-10-18,13:00,SF,DAL,outdoors,grass,53,15.0,-3.5,44.5,Levi's Stadium
2026,REG,6,2026-10-18,16:25,LA,SEA,dome,fieldturf,,,NA,,SoFi Stadium
2026,REG,7,2026-10-25,,MIN,CHI,,,oops,,2,,
2026,POST,1,2027-01-10,16:30,SF,DAL,outdoors,grass,40,5,1,40,Levi's Stadium
2025,REG,6,2025-10-19,13:00,SF,DAL,outdoors,grass,70,2,1,40,Levi's Stadium
"""  # noqa: E501


def test_parse_conditions_reads_weather_roof_and_lines_and_tolerates_blanks() -> None:
    found = parse_conditions(WEATHER_CSV, "2026")
    assert len(found) == 3  # no playoffs, no other season
    outdoor = found[(6, "SF", "DAL")]
    assert (outdoor.roof, outdoor.surface, outdoor.temp, outdoor.wind) == (
        "outdoors",
        "grass",
        53,
        15,
    )
    assert (outdoor.spread_line, outdoor.total_line, outdoor.stadium) == (
        -3.5,
        44.5,
        "Levi's Stadium",
    )
    dome = found[(6, "LAR", "SEA")]  # nflverse says LA, Sleeper says LAR
    assert (dome.roof, dome.temp, dome.wind, dome.spread_line) == ("dome", None, None, None)
    junk = found[(7, "MIN", "CHI")]
    assert (junk.roof, junk.temp, junk.spread_line) == (None, None, 2.0)  # "oops" is not a number


def test_sync_stores_conditions_and_games_show_them_from_each_teams_side(session: Session) -> None:
    session.add_all(
        [
            NflGameRow(game_id="a", season="2026", week=6, home="SF", away="DAL",
                       game_date="2026-10-18", status="pre_game"),
            NflGameRow(game_id="b", season="2026", week=7, home="MIN", away="CHI",
                       game_date="2026-10-25", status="pre_game"),
        ]
    )  # fmt: skip
    session.commit()
    sync_kickoffs(session, _http(WEATHER_CSV), "2026")
    games = games_for_week(session, "2026", 6)
    home, away = games["SF"].conditions, games["DAL"].conditions
    assert home is not None and away is not None
    assert (home.roof, home.temp, home.wind, home.total) == ("outdoors", 53, 15, 44.5)
    assert home.spread == 3.5  # nflverse -3.5: the road team is favoured, so the home side is +3.5
    assert away.spread == -3.5
    assert games_for_week(session, "2026", 7)["MIN"].conditions is not None  # a line alone is kept


def test_a_game_with_nothing_published_has_no_conditions(session: Session) -> None:
    session.add(
        NflGameRow(game_id="a", season="2026", week=6, home="SF", away="DAL",
                   game_date="2026-10-18", status="pre_game")
    )  # fmt: skip
    session.commit()
    assert games_for_week(session, "2026", 6)["SF"].conditions is None
