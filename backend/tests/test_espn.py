"""ESPN ownership: parsing, matching players to Sleeper's, storing, and failing safely."""

import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.core.sources.espn import (
    Ownership,
    SleeperPerson,
    fetch_ownership,
    match_players,
    normalize_name,
    parse_ownership,
)
from sleeper_assistant.db import LeagueRow, PlayerOwnershipRow, PlayerRow, RosterRow
from sleeper_assistant.sync.player_data import sync_ownership
from sleeper_assistant.views.players import build_players


def _player(  # noqa: PLR0913, PLR0917
    pid: int, name: str, position: int, team: int, owned: Any, started: Any
) -> dict[str, Any]:
    return {
        "id": pid,
        "player": {
            "id": pid,
            "fullName": name,
            "defaultPositionId": position,
            "proTeamId": team,
            "ownership": {"percentOwned": owned, "percentStarted": started, "averageDraftPosition": 1.7},  # noqa: E501
        },
    }  # fmt: skip


PAYLOAD = {
    "players": [
        _player(4429795, "Jahmyr Gibbs", 2, 8, 99.93, 25.94),
        _player(4262921, "Puka Nacua", 3, 14, 99.9, 99.1),
        _player(-16026, "Seahawks D/ST", 16, 26, 80.5, 60.25),
        _player(111, "No Ownership", 3, 3, None, None),
    ]
}


def test_parse_reads_ids_names_teams_positions_and_percentages() -> None:
    rows = {r.name: r for r in parse_ownership(PAYLOAD)}
    gibbs = rows["Jahmyr Gibbs"]
    assert (gibbs.espn_id, gibbs.team, gibbs.position) == ("4429795", "DET", "RB")
    assert (gibbs.owned, gibbs.started) == (99.93, 25.94)
    assert rows["Puka Nacua"].team == "LAR"  # ESPN team 14 is the Rams
    seahawks = rows["Seahawks D/ST"]
    assert (seahawks.team, seahawks.position) == ("SEA", "DEF")  # the team is part of a D/ST id
    # a number ESPN leaves out is None, never 0
    assert (rows["No Ownership"].owned, rows["No Ownership"].started) == (None, None)


def test_parse_ignores_anything_that_is_not_the_expected_shape() -> None:
    assert parse_ownership(None) == []
    assert parse_ownership({"players": "nope"}) == []
    assert parse_ownership({"players": [None, 5, {"player": None}, {"player": {"id": "x"}}]}) == []
    no_name = {"players": [{"player": {"id": 1, "ownership": {"percentOwned": 5.0}}}]}
    assert parse_ownership(no_name) == []
    odd = _player(7, "Odd Numbers", 3, 3, "lots", True)  # text and booleans are not percentages
    assert [(r.owned, r.started) for r in parse_ownership({"players": [odd]})] == [(None, None)]


def test_names_are_compared_without_accents_punctuation_or_suffixes() -> None:
    assert normalize_name("D'Andre Swift") == normalize_name("DAndre Swift")
    assert normalize_name("Marvin Harrison Jr.") == normalize_name("Marvin Harrison")
    assert normalize_name("José Ramírez") == "jose ramirez"
    assert normalize_name("Amon-Ra St. Brown") == "amon ra st brown"
    assert normalize_name("Michael Pittman Jr") == "michael pittman"


def _espn(name: str, team: str | None, position: str, espn_id: str = "1") -> Ownership:
    return Ownership(espn_id, name, team, position, 50.0, 40.0)


def test_players_match_by_espn_id_first_then_by_name_team_and_position() -> None:
    espn = [_espn("Puka Nacua", "LAR", "WR", "10"), _espn("Jahmyr Gibbs", "DET", "RB", "20")]
    sleeper = [
        SleeperPerson("s1", "Someone Else", "LAR", "WR", "10"),  # matched by ESPN id alone
        SleeperPerson("s2", "Jahmyr Gibbs", "DET", "RB", None),  # matched by name, team, position
        SleeperPerson("s3", "Jahmyr Gibbs", "CHI", "RB", None),  # same name, other team: no match
        SleeperPerson("s4", None, "DET", "RB", None),  # nothing to go on
    ]
    got = match_players(espn, sleeper)
    assert set(got) == {"s1", "s2"}
    assert got["s1"].name == "Puka Nacua"


def test_a_name_that_matches_two_players_is_not_guessed() -> None:
    espn = [_espn("Mike Williams", "NYJ", "WR", "1"), _espn("Mike Williams", "NYJ", "WR", "2")]
    assert match_players(espn, [SleeperPerson("s1", "Mike Williams", "NYJ", "WR", None)]) == {}


def test_a_defense_matches_by_team() -> None:
    espn = [_espn("Seahawks D/ST", "SEA", "DEF", "-16026")]
    sleeper = [
        SleeperPerson("SEA", None, "SEA", "DEF", None),
        SleeperPerson("SF", None, "SF", "DEF", None),
    ]
    assert set(match_players(espn, sleeper)) == {"SEA"}  # the 49ers have no ESPN row here


def test_fetch_asks_for_the_top_players_and_raises_on_failure() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["filter"] = json.loads(request.headers["X-Fantasy-Filter"])
        return httpx.Response(200, content=json.dumps(PAYLOAD))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert len(fetch_ownership(http, "2026")) == 4
    assert "seasons/2026" in seen["url"] and "kona_player_info" in seen["url"]
    assert seen["filter"]["players"]["sortPercOwned"]["sortAsc"] is False

    down = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(503)))
    try:
        fetch_ownership(down, "2026")
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("a failed pull should raise")


def _people(session: Session) -> None:
    session.add_all(
        [
            PlayerRow(player_id="1", full_name="Jahmyr Gibbs", position="RB", team="DET", external_ids={}),  # noqa: E501
            PlayerRow(player_id="2", full_name="Puka Nacua", position="WR", team="LAR", external_ids={"espn": 4262921}),  # noqa: E501
            PlayerRow(player_id="3", full_name="No Match", position="WR", team="NE", external_ids={}),  # noqa: E501
        ]
    )  # fmt: skip
    session.commit()


def test_sync_stores_matched_players_and_replaces_old_numbers(session: Session) -> None:
    _people(session)
    assert sync_ownership(session, parse_ownership(PAYLOAD)) == 2
    rows = {r.player_id: (r.owned, r.started) for r in session.scalars(select(PlayerOwnershipRow))}
    assert rows == {"1": (99.93, 25.94), "2": (99.9, 99.1)}

    newer = {"players": [_player(4429795, "Jahmyr Gibbs", 2, 8, 90.0, 20.0)]}
    sync_ownership(session, parse_ownership(newer))
    session.expire_all()
    rows = {r.player_id: (r.owned, r.started) for r in session.scalars(select(PlayerOwnershipRow))}
    assert rows == {"1": (90.0, 20.0)}  # Nacua fell off ESPN's list, so his number is dropped


def test_an_empty_or_broken_pull_leaves_the_previous_numbers(session: Session) -> None:
    _people(session)
    sync_ownership(session, parse_ownership(PAYLOAD))
    assert sync_ownership(session, parse_ownership({"unexpected": True})) == 0
    session.expire_all()
    assert session.get(PlayerOwnershipRow, "1") is not None  # not wiped by a bad response


def test_players_tab_carries_the_espn_percentages_and_dashes_for_the_rest(
    session: Session,
) -> None:
    _people(session)
    sync_ownership(session, parse_ownership(PAYLOAD))
    league = LeagueRow(
        league_id="L1", name="F", season="2026", total_rosters=1,
        scoring_settings={}, roster_positions=[], settings={},
    )  # fmt: skip
    session.add(league)
    session.add(
        RosterRow(
            league_id="L1", roster_id=1, owner_id="u1", players=["3"], starters=[], reserve=[],
            taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
        )
    )  # fmt: skip
    session.commit()
    by_name = {p.name: p for p in build_players(session, league).players}
    assert (by_name["Jahmyr Gibbs"].owned_pct, by_name["Jahmyr Gibbs"].started_pct) == (
        99.93,
        25.94,
    )
    assert (by_name["No Match"].owned_pct, by_name["No Match"].started_pct) == (None, None)
