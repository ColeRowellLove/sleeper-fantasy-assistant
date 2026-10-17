import httpx

from sleeper_assistant.core.sources.sleeper import BASE_URL, SleeperClient


def _client(handler: httpx.MockTransport) -> SleeperClient:
    return SleeperClient(httpx.Client(base_url=BASE_URL, transport=handler))


def test_get_user() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, json={"user_id": "1", "username": "cole", "display_name": "Cole"}
        )
    )
    user = _client(transport).get_user("cole")
    assert user.user_id == "1"
    assert user.display_name == "Cole"


def test_get_leagues() -> None:
    payload = [
        {"league_id": "9", "name": "Family", "season": "2026", "total_rosters": 10},
    ]
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    leagues = _client(transport).get_leagues("1", "2026")
    assert [lg.name for lg in leagues] == ["Family"]
    assert leagues[0].total_rosters == 10
