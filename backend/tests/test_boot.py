"""Boot loading: a username or a league id loads the league; nothing loads the sample league."""

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.boot import boot, leagues_for_user, load_leagues
from sleeper_assistant.db import LeagueRow, NflGameRow, PlayerRow
from sleeper_assistant.sample_league import LEAGUE_ID
from sleeper_assistant.sleeper import BASE_URL, SleeperClient
from test_api_connect import FAILING, FIXTURE, _handler


def _with_user_league(request: httpx.Request) -> httpx.Response:
    """The shared fixture's user belongs to L1, which has no matchups; point it at league 1."""
    if "/user/u1/leagues/nfl/" in request.url.path:
        return httpx.Response(200, json=[FIXTURE["league"] | {"league_id": "1"}])
    return _handler(request)


def _sleeper() -> SleeperClient:
    transport = httpx.MockTransport(_with_user_league)
    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=transport))


def test_a_username_loads_each_of_its_leagues_players_and_schedule(session: Session) -> None:
    assert leagues_for_user(_sleeper(), "cole") == ["1"]
    assert boot(session, _sleeper(), "cole", None) == 1
    league = session.get(LeagueRow, "1")
    assert league is not None and league.last_viewed_at is not None  # the worker keeps it fresh
    assert session.scalars(select(PlayerRow)).first() is not None
    assert session.scalars(select(NflGameRow)).first() is not None


def test_a_league_id_loads_just_that_league(session: Session) -> None:
    assert boot(session, _sleeper(), None, "1") == 1
    assert session.get(LeagueRow, "1") is not None


def test_a_league_sleeper_does_not_know_is_skipped_not_fatal(session: Session) -> None:
    assert load_leagues(session, _sleeper(), ["999", "1"]) == ["1"]


def test_with_nothing_given_an_empty_database_gets_the_sample_league(session: Session) -> None:
    assert boot(session, _sleeper(), None, None) == 1
    assert session.get(LeagueRow, LEAGUE_ID) is not None
    assert boot(session, _sleeper(), None, None) == 0  # already has a league: nothing to do


def test_an_unknown_username_loads_nothing_and_does_not_crash(session: Session) -> None:
    assert boot(session, _sleeper(), "nobody", None) == 0


def test_one_league_failing_does_not_stop_the_others(session: Session) -> None:
    FAILING.add("/league/999")
    assert load_leagues(session, _sleeper(), ["999", "1"]) == ["1"]


def test_the_sample_league_is_not_seeded_over_existing_players(session: Session) -> None:
    session.add(PlayerRow(player_id="s1", full_name="x", position="QB", team="SF", external_ids={}))
    session.commit()
    assert boot(session, _sleeper(), None, None) == 0
