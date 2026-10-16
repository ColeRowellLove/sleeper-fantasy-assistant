import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sleeper_assistant.api import app, get_session, get_sleeper
from sleeper_assistant.db import Base, LeagueRow, make_session_factory
from sleeper_assistant.sleeper import BASE_URL, SleeperClient

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "sleeper_league.json").read_text()
)


def _routes_original() -> dict[str, Any]:
    routes: dict[str, Any] = {
        "/state/nfl": FIXTURE["state"],
        "/user/cole": FIXTURE["users"][0],
        "/user/nobody": None,
        "/user/u1/leagues/nfl/2026": [FIXTURE["league"]],
        "/league/L1": FIXTURE["league"],
        "/league/L1/users": FIXTURE["users"],
        "/league/L1/rosters": FIXTURE["rosters"],
        "/league/999": None,
        "/players/nfl": FIXTURE["players"],
        "/schedule/nfl/regular/2026": FIXTURE["schedule"],
    }
    routes["/league/1"] = FIXTURE["league"] | {"league_id": "1"}
    routes["/league/1/users"] = FIXTURE["users"]
    routes["/league/1/rosters"] = FIXTURE["rosters"]
    for week, items in FIXTURE["matchups"].items():
        routes[f"/league/1/matchups/{week}"] = items
    for week, items in FIXTURE["transactions"].items():
        routes[f"/league/1/transactions/{week}"] = items
    return routes


FAILING: set[str] = set()  # paths a test wants Sleeper to answer with a 503
OVERRIDES: dict[str, Any] = {}  # paths a test wants Sleeper to answer differently


@pytest.fixture(autouse=True)
def _reset_sleeper_faults() -> Iterator[None]:
    yield
    FAILING.clear()
    OVERRIDES.clear()


def _routes() -> dict[str, Any]:
    return {**_routes_original(), **OVERRIDES}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path.removeprefix("/v1")
    routes = _routes()
    if path == "/user/down" or path in FAILING:
        return httpx.Response(503)
    if path in routes:
        # content= (not json=) so a None route is sent as the literal JSON null Sleeper returns
        return httpx.Response(200, content=json.dumps(routes[path]))
    return httpx.Response(404)


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)

    def _session() -> Iterator[Session]:
        with factory() as s:
            yield s

    sleeper = SleeperClient(
        httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(_handler))
    )
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_sleeper] = lambda: sleeper
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def test_list_leagues_for_username(client: TestClient) -> None:
    resp = client.get("/api/users/cole/leagues")
    assert resp.status_code == 200
    assert resp.json() == {
        "user_id": "u1",
        "display_name": "Cole",
        "leagues": [
            {"league_id": "L1", "name": "Family League", "season": "2026", "total_rosters": 2}
        ],
    }


def test_unknown_user_is_404(client: TestClient) -> None:
    assert client.get("/api/users/nobody/leagues").status_code == 404


def test_sleeper_down_is_502(client: TestClient) -> None:
    assert client.get("/api/users/down/leagues").status_code == 502


@pytest.mark.parametrize("bad", ["a b", "x" * 41, "../etc"])
def test_username_is_validated(client: TestClient, bad: str) -> None:
    assert client.get(f"/api/users/{bad}/leagues").status_code in (404, 422)


def test_season_is_validated(client: TestClient) -> None:
    assert client.get("/api/users/cole/leagues?season=20x6").status_code == 422


def test_connect_syncs_and_marks_active(client: TestClient) -> None:
    resp = client.post("/api/leagues/1/connect")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Family League"
    assert body["rules"]["uses_faab"] is True
    assert body["rules"]["trade_deadline_week"] == 11

    session = app.dependency_overrides[get_session]()
    league = session.__next__().get(LeagueRow, "1")  # type: ignore[attr-defined]
    assert league is not None
    assert league.last_viewed_at is not None
    assert league.last_synced_at is not None


def test_connect_unknown_league_is_404(client: TestClient) -> None:
    assert client.post("/api/leagues/999/connect").status_code == 404


def test_connect_rejects_non_numeric_league_id(client: TestClient) -> None:
    assert client.post("/api/leagues/abc/connect").status_code == 422


def test_connect_twice_within_cooldown_syncs_once(client: TestClient) -> None:
    calls: list[str] = []
    original = app.dependency_overrides[get_sleeper]()
    counting = httpx.Client(
        base_url=BASE_URL,
        transport=httpx.MockTransport(lambda r: (calls.append(r.url.path), _handler(r))[1]),
    )
    app.dependency_overrides[get_sleeper] = lambda: SleeperClient(counting)
    del original

    assert client.post("/api/leagues/1/connect").status_code == 200
    first = len(calls)
    assert first > 0
    assert client.post("/api/leagues/1/connect").status_code == 200
    assert len(calls) == first  # cooldown: second connect made no Sleeper requests


def test_unexpected_sleeper_payload_is_502(client: TestClient) -> None:
    bad = SleeperClient(
        httpx.Client(
            base_url=BASE_URL,
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"league_id": 1})),
        )
    )
    app.dependency_overrides[get_sleeper] = lambda: bad
    assert client.post("/api/leagues/1/connect").status_code == 502


def test_dashboard_after_connect(client: TestClient) -> None:
    assert client.get("/api/leagues/1").status_code == 404  # not connected yet

    client.post("/api/leagues/1/connect")
    resp = client.get("/api/leagues/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Family League"
    assert body["rules"]["uses_faab"] is True
    assert [s["team"] for s in body["standings"]] == ["Cole", "Dad Bods"]  # chosen name, trimmed
    assert [s["manager"] for s in body["standings"]] == ["Cole", "Dad"]  # username fallback
    assert body["standings"][0]["points_for"] == 120.42
    assert [s["streak"] for s in body["standings"]] == ["2W", None]  # a missing streak is None
    first = body["rosters"][0]["players"][0]
    assert body["week"] == 2  # current NFL week, from the schedule loaded on connect
    assert first["game"] == {
        "state": "upcoming",
        "date": "2026-09-20",
        "kickoff": None,
        "team": "SF",
        "team_score": None,  # not started: no score
        "opponent_score": None,
        "period_text": None,
        "elapsed": 0.0,  # not started: none of the game is played
        "opponent": "CHI",
        "home": True,
        "conditions": None,  # nflverse has not been synced in this test
    }
    bye = next(p for p in body["rosters"][0]["players"] if p["name"] == "Justin Jefferson")
    assert bye["game"]["state"] == "bye"  # MIN has no game in week 2
    assert first["status"] == "starter"
    assert first["name"] == "Christian McCaffrey"  # player DB loaded on first connect
    assert first["position"] == "RB"
    assert first["team"] == "SF"


def test_dashboard_rejects_bad_league_id(client: TestClient) -> None:
    assert client.get("/api/leagues/abc").status_code == 422


def test_dashboard_view_timestamp_is_throttled(client: TestClient) -> None:
    client.post("/api/leagues/1/connect")
    session = next(app.dependency_overrides[get_session]())
    league = session.get(LeagueRow, "1")
    assert league is not None
    recent = league.last_viewed_at
    assert recent is not None

    client.get("/api/leagues/1")
    session.refresh(league)
    assert league.last_viewed_at == recent  # within the hour: not rewritten

    league.last_viewed_at = recent - timedelta(hours=2)
    session.commit()
    client.get("/api/leagues/1")
    session.refresh(league)
    assert league.last_viewed_at is not None
    assert league.last_viewed_at > recent - timedelta(hours=1)  # stale: refreshed


def test_lineups_endpoint(client: TestClient) -> None:
    assert client.get("/api/leagues/1/lineups").status_code == 404  # not connected yet

    client.post("/api/leagues/1/connect")
    current = client.get("/api/leagues/1/lineups").json()

    # defaults to the current NFL week (week 2 is the first with an unfinished game)
    assert current["week"] == 2
    assert current["current_week"] == 2
    assert current["weeks"] == [1, 2, 3]  # includes the upcoming week 3 pairing

    played = client.get("/api/leagues/1/lineups?week=1").json()
    team = played["matchups"][0]["teams"][0]
    assert team["team"] == "Cole"
    assert team["starters"][0]["name"] == "Christian McCaffrey"
    assert team["starters"][0]["points"] == 20.5
    assert team["starters"][0]["game"]["state"] == "final"  # week 1 is complete

    upcoming = client.get("/api/leagues/1/lineups?week=3").json()
    assert upcoming["week"] == 3
    assert upcoming["matchups"][0]["teams"][0]["starters"][0]["game"]["state"] == "upcoming"

    assert client.get("/api/leagues/1/lineups?week=99").status_code == 422


def test_read_endpoints_are_briefly_cacheable_but_errors_are_not(client: TestClient) -> None:
    assert "cache-control" not in client.get("/api/leagues/1").headers  # 404: never cached
    client.post("/api/leagues/1/connect")

    for path in ("/api/leagues/1", "/api/leagues/1/lineups"):
        cache = client.get(path).headers["cache-control"]
        assert "s-maxage=30" in cache
        assert "public" in cache


def test_league_settings_endpoint_returns_what_sleeper_provides(client: TestClient) -> None:
    assert client.get("/api/leagues/1/settings").status_code == 404  # not connected yet
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/settings").json()
    assert body["name"] == "Family League"
    assert body["season"] == "2026"
    assert body["roster_positions"] == FIXTURE["league"]["roster_positions"]
    assert body["settings"] == FIXTURE["league"]["settings"]
    assert body["scoring_settings"] == {
        k: float(v) for k, v in FIXTURE["league"]["scoring_settings"].items()
    }


def test_connect_still_works_when_the_player_database_is_down(
    client: TestClient,
) -> None:
    FAILING.update({"/players/nfl"})
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1").json()
    assert body["name"] == "Family League"  # the league loads; names fall back to ids


def test_connect_still_works_when_the_schedule_is_down(
    client: TestClient,
) -> None:
    FAILING.update({"/schedule/nfl/regular/2026"})
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1").json()
    assert body["week"] is None  # without a schedule there is no current week, and no crash


def test_connect_reports_a_sleeper_outage_as_502(
    client: TestClient,
) -> None:
    FAILING.update({"/league/1"})
    assert client.post("/api/leagues/1/connect").status_code == 502


def test_connect_reports_an_unknown_league_as_404(client: TestClient) -> None:
    assert client.post("/api/leagues/999/connect").status_code == 404


def test_connect_reports_a_malformed_sleeper_payload_as_502(client: TestClient) -> None:
    broken = dict(FIXTURE["league"], league_id="1", total_rosters="many")
    OVERRIDES["/league/1"] = broken
    assert client.post("/api/leagues/1/connect").status_code == 502


def test_players_endpoint_lists_who_is_rostered_in_this_league(client: TestClient) -> None:
    assert client.get("/api/leagues/1/players").status_code == 404  # not connected yet
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/players").json()
    assert body["league_id"] == "1"
    assert {p["owner_team"] for p in body["players"]} <= {"Cole", "Dad Bods", None}
    assert any(
        p["owner_roster_id"] == 1 for p in body["players"]
    )  # the roster's players are listed


def test_player_detail_endpoint(client: TestClient) -> None:
    assert client.get("/api/leagues/1/players/4034").status_code == 404  # league not connected
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/players/4034").json()
    assert body["player_id"] == "4034"
    assert body["owner_roster_id"] == 1  # on the first roster
    assert client.get("/api/leagues/1/players/doesnotexist").status_code == 404
    assert (
        client.get("/api/leagues/1/players/bad id!").status_code == 422
    )  # rejected, not looked up


def test_start_sit_endpoints(client: TestClient) -> None:
    assert client.get("/api/leagues/1/start-sit?player=1&player=2").status_code == 404
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/start-sit?player=4034&player=4035").json()
    assert body["league_id"] == "1" and len(body["candidates"]) == 2
    assert client.get("/api/leagues/1/start-sit?player=4034").status_code == 422  # needs two
    assert client.get("/api/leagues/1/start-sit?player=bad id&player=2").status_code == 422
    lineup = client.get("/api/leagues/1/start-sit/lineup?roster=1").json()
    assert lineup["roster_id"] == 1 and isinstance(lineup["lineup"], list)
    assert client.get("/api/leagues/1/start-sit/lineup?roster=40").status_code == 404


def test_games_endpoint(client: TestClient) -> None:
    assert client.get("/api/leagues/1/games").status_code == 404  # league not connected
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/games?week=2").json()
    assert body["league_id"] == "1" and isinstance(body["games"], list)
    assert client.get("/api/leagues/1/games?week=99").status_code == 422


def test_rankings_endpoint(client: TestClient) -> None:
    assert client.get("/api/leagues/1/rankings").status_code == 404  # league not connected
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/rankings?week=2").json()
    assert body["league_id"] == "1" and isinstance(body["players"], list)
    assert "projection" in body["signals"]
    assert client.get("/api/leagues/1/rankings?week=99").status_code == 422


def test_lineup_accuracy_endpoint(client: TestClient) -> None:
    assert client.get("/api/leagues/1/accuracy").status_code == 404  # league not connected
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/accuracy").json()
    assert body["league_id"] == "1"
    assert [t["roster_id"] for t in body["teams"]] == [1, 2]
    assert body["teams"][0]["points"] == 120.42
    assert body["teams"][0]["potential"] is None  # the recorded league has no potential points
    assert body["teams"][0]["accuracy"] is None


def test_team_depth_endpoint(client: TestClient) -> None:
    assert client.get("/api/leagues/1/teams/SF").status_code == 404  # league not connected yet
    assert client.post("/api/leagues/1/connect").status_code == 200
    body = client.get("/api/leagues/1/teams/SF").json()
    assert body["team"] == "SF" and body["groups"] == []  # nothing stored yet: empty, not an error
    assert client.get("/api/leagues/1/teams/ZZZ").status_code == 404  # not an NFL team
    assert client.get("/api/leagues/1/teams/sf").status_code == 422  # rejected, not looked up
