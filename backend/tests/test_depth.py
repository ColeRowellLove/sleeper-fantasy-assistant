"""Team depth charts: parsing ESPN, matching to Sleeper, the Sleeper fallback, and the page data."""

# ruff: noqa: E501  (fixtures with long player rows are easier to read on one line)

import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from sleeper_assistant.core.nfl.depth import (
    Entry,
    RosterPlayer,
    attach_sleeper_ids,
    chart_from_sleeper,
    fetch_depth_chart,
    parse_depth_chart,
    slot_label,
    slot_order,
)
from sleeper_assistant.core.nfl.team_depth import TeamRecord, build_team_depth, team_record
from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerRow,
    RosterRow,
    TeamDepthChartRow,
    utcnow,
)
from sleeper_assistant.sync.depth_sync import sync_depth_charts


def _athletes(*names: str, injury: str | None = None) -> dict[str, Any]:
    athletes = []
    for i, name in enumerate(names):
        athlete: dict[str, Any] = {"id": str(100 + i), "displayName": name, "injuries": []}
        if injury and i == 0:
            athlete["injuries"] = [{"status": injury}]
        athletes.append(athlete)
    return {"athletes": athletes, "position": {"abbreviation": "X"}}


PAYLOAD = {
    "depthchart": [
        {
            "name": "3WR 1TE",
            "positions": {
                "qb": _athletes("Sam Darnold", "Drew Lock"),
                "wr1": _athletes("Jaxon Smith-Njigba", "Tory Horton", injury="Out"),
                "lt": _athletes("Charles Cross"),
                "rb": _athletes(),  # nobody listed: the slot is left out
            },
        },
        {"name": "Base 3-4 D", "positions": {"lde": _athletes("Leonard Williams"), "ss": _athletes("Coby Bryant")}},
        {"name": "Special Teams", "positions": {"pk": _athletes("Jason Myers"), "kr": _athletes("Rashid Shaheed")}},
        {"name": "3WR 1TE", "positions": {"qb": _athletes("Someone Later")}},  # a second look: ignored
    ]
}  # fmt: skip


def test_parse_groups_every_slot_and_keeps_depth_order() -> None:
    chart = parse_depth_chart(PAYLOAD)
    assert set(chart["offense"]) == {"qb", "wr1", "lt"}  # an empty slot is not listed
    assert [e.name for e in chart["offense"]["qb"]] == [
        "Sam Darnold",
        "Drew Lock",
    ]  # first look wins
    assert set(chart["defense"]) == {"lde", "ss"}
    assert set(chart["special"]) == {"pk", "kr"}
    assert chart["offense"]["wr1"][0].injury == "Out"  # ESPN's own status is kept
    assert chart["offense"]["wr1"][1].injury is None


def test_parse_survives_anything_that_is_not_a_chart() -> None:
    for junk in (None, [], {"depthchart": "no"}, {"depthchart": [None, {"positions": 3}]}):
        chart = parse_depth_chart(junk)
        assert chart == {"offense": {}, "defense": {}, "special": {}}
    odd = {"depthchart": [{"name": "X", "positions": {"qb": {"athletes": [{"id": 1}, "x", None]}}}]}
    assert parse_depth_chart(odd)["offense"] == {}  # no usable player in the slot


def test_unknown_slots_keep_their_formations_group_and_a_readable_label() -> None:
    odd = {
        "depthchart": [{"name": "Special Teams", "positions": {"gunner": _athletes("A Gunner")}}]
    }
    assert "gunner" in parse_depth_chart(odd)["special"]
    assert slot_label("special", "gunner") == "GUNNER"
    assert slot_label("offense", "lt") == "Left tackle"
    assert slot_order("offense", "qb") < slot_order("offense", "lt") < slot_order("offense", "zzz")


def test_fetch_asks_for_the_right_team_and_raises_on_failure() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=json.dumps(PAYLOAD))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert fetch_depth_chart(http, "SEA")["offense"]["qb"][0].name == "Sam Darnold"
    assert seen[0].endswith("/teams/26/depthcharts")  # ESPN's id for Seattle

    down = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(503)))
    try:
        fetch_depth_chart(down, "SEA")
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("a failed request should raise")


def _roster() -> list[RosterPlayer]:
    return [
        RosterPlayer("s1", "Sam Darnold", "SEA", None, "QB", 1),
        RosterPlayer("s2", "Jaxon Smith-Njigba", "SEA", "100", "LWR", 1),
        RosterPlayer("s3", "Tory Horton", "SEA", None, "SWR", 2),
        RosterPlayer("s4", "Drew Lock", "NYG", None, "QB", 2),  # a different team: not a match
        RosterPlayer("s5", "Twin Name", "SEA", None, None, None),
        RosterPlayer("s6", "Twin Name", "SEA", None, None, None),
    ]


def test_players_match_by_espn_id_then_by_name_within_the_team() -> None:
    chart = {
        "offense": {
            "qb": [Entry("1", "Sam Darnold"), Entry("2", "Drew Lock"), Entry("3", "Twin Name")],
            "wr1": [Entry("100", "Different Name")],
        },
        "defense": {},
        "special": {},
    }
    got = attach_sleeper_ids(chart, "SEA", _roster())["offense"]
    assert [e.sleeper_id for e in got["qb"]] == [
        "s1",
        None,
        None,
    ]  # Lock is on another team; Twin is ambiguous
    assert got["wr1"][0].sleeper_id == "s2"  # matched by ESPN id despite the name


def test_sleepers_own_chart_is_the_fallback_and_has_no_line_or_returners() -> None:
    chart = chart_from_sleeper(_roster())
    assert [e.name for e in chart["offense"]["qb"]] == ["Sam Darnold", "Drew Lock"]
    assert chart["offense"]["wr3"][0].name == "Tory Horton"  # Sleeper's SWR is the third receiver
    assert "lt" not in chart["offense"] and "kr" not in chart["special"]
    assert chart["offense"]["qb"][0].sleeper_id == "s1"


def _players(session: Session) -> None:
    session.add_all(
        [
            PlayerRow(player_id="s1", full_name="Sam Darnold", position="QB", team="SEA", external_ids={}),
            PlayerRow(
                player_id="s2", full_name="Jaxon Smith-Njigba", position="WR", team="SEA", external_ids={},
                injury_status="Out", injury_body_part="Hamstring",
            ),
            PlayerRow(player_id="s3", full_name="Tory Horton", position="WR", team="SEA", external_ids={}),
            PlayerRow(
                player_id="s9", full_name="Jason Myers", position="K", team="SEA", external_ids={},
                bio={"depth_chart_position": "K", "depth_chart_order": 1},
            ),
        ]
    )  # fmt: skip
    session.commit()


def _client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sync_stores_espn_charts_with_sleeper_ids(session: Session) -> None:
    _players(session)
    http = _client(lambda _r: httpx.Response(200, content=json.dumps(PAYLOAD)))
    assert sync_depth_charts(session, http, ["SEA"]) == 1
    row = session.get(TeamDepthChartRow, "SEA")
    assert row is not None and row.source == "ESPN"
    qb = row.chart["offense"]["qb"]
    assert qb[0] == {"name": "Sam Darnold", "espn_id": "100", "sleeper_id": "s1", "injury": None}


def test_a_failed_espn_pull_keeps_the_last_good_chart(session: Session) -> None:
    _players(session)
    sync_depth_charts(
        session, _client(lambda _r: httpx.Response(200, content=json.dumps(PAYLOAD))), ["SEA"]
    )
    before = session.get(TeamDepthChartRow, "SEA")
    assert before is not None
    stamp = before.fetched_at
    assert sync_depth_charts(session, _client(lambda _r: httpx.Response(503)), ["SEA"]) == 0
    session.expire_all()
    after = session.get(TeamDepthChartRow, "SEA")
    assert after is not None and after.source == "ESPN" and after.fetched_at == stamp


def test_with_no_espn_chart_at_all_a_team_falls_back_to_sleepers(session: Session) -> None:
    _players(session)
    assert sync_depth_charts(session, _client(lambda _r: httpx.Response(503)), ["SEA"]) == 1
    row = session.get(TeamDepthChartRow, "SEA")
    assert row is not None and row.source == "Sleeper"
    assert row.chart["special"]["pk"][0]["name"] == "Jason Myers"


def test_a_team_with_nothing_anywhere_stores_nothing(session: Session) -> None:
    assert sync_depth_charts(session, _client(lambda _r: httpx.Response(503)), ["KC"]) == 0
    assert session.get(TeamDepthChartRow, "KC") is None


def _league(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="F", season="2026", total_rosters=1,
        scoring_settings={}, roster_positions=[], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            RosterRow(
                league_id="L1", roster_id=1, owner_id="u1", players=["s3"], starters=[], reserve=[],
                taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
            ),
            NflGameRow(
                game_id="g1", season="2026", week=6, home="SEA", away="DEN",
                game_date="2026-10-18", status="pre_game",
            ),
        ]
    )  # fmt: skip
    session.commit()
    return league


def test_the_team_page_shows_injuries_ownership_and_who_is_next(session: Session) -> None:
    _players(session)
    sync_depth_charts(
        session, _client(lambda _r: httpx.Response(200, content=json.dumps(PAYLOAD))), ["SEA"]
    )
    page = build_team_depth(session, _league(session), "SEA")
    assert page.source == "ESPN" and page.updated_at is not None
    assert [g.group for g in page.groups] == ["offense", "defense", "special"]
    assert page.game is not None and page.game.opponent == "DEN"

    offense = {s.slot: s for s in page.groups[0].slots}
    assert [s.slot for s in page.groups[0].slots] == ["qb", "wr1", "lt"]  # reading order
    assert offense["qb"].skill and not offense["lt"].skill
    wr1 = offense["wr1"]
    assert [(p.label, p.depth) for p in wr1.players] == [("Starter", 1), ("2nd string", 2)]
    assert wr1.players[0].injury is not None and wr1.players[0].injury.status == "Out"
    assert wr1.players[0].injury.body_part == "Hamstring"  # Sleeper's detail wins over ESPN's text
    assert wr1.note == "Jaxon Smith-Njigba is out: next up is Tory Horton"
    assert wr1.players[1].next_up and not wr1.players[0].next_up
    assert (wr1.players[1].owner_roster_id, wr1.players[1].owner_team) == (1, "Team 1")
    assert offense["qb"].players[0].owner_roster_id is None  # available in this league
    assert offense["qb"].note is None  # a healthy starter needs no note


def test_next_up_skips_other_players_who_are_also_out(session: Session) -> None:
    _players(session)
    chart = {"offense": {"qb": [
        {"name": "A", "sleeper_id": None, "espn_id": "1", "injury": "Out"},
        {"name": "B", "sleeper_id": None, "espn_id": "2", "injury": "Out"},
        {"name": "C", "sleeper_id": None, "espn_id": "3", "injury": None},
    ], "rb": [{"name": "Solo", "sleeper_id": None, "espn_id": "4", "injury": "Out"}]}, "defense": {}, "special": {}}  # fmt: skip
    session.add(TeamDepthChartRow(team="SEA", source="ESPN", chart=chart, fetched_at=utcnow()))
    session.commit()
    slots = {s.slot: s for s in build_team_depth(session, _league(session), "SEA").groups[0].slots}
    assert slots["qb"].note == "A is out: next up is C"
    assert [p.next_up for p in slots["qb"].players] == [False, False, True]
    assert slots["rb"].note == "Solo is out and no healthy player is listed behind him"


def test_a_doubtful_starter_is_flagged_without_naming_a_replacement(session: Session) -> None:
    chart = {"offense": {"qb": [
        {"name": "A", "sleeper_id": None, "espn_id": "1", "injury": "Doubtful"},
        {"name": "B", "sleeper_id": None, "espn_id": "2", "injury": None},
    ]}, "defense": {}, "special": {}}  # fmt: skip
    session.add(TeamDepthChartRow(team="SEA", source="ESPN", chart=chart, fetched_at=utcnow()))
    session.commit()
    slot = build_team_depth(session, _league(session), "SEA").groups[0].slots[0]
    assert slot.note == "A is doubtful" and not slot.players[1].next_up


def test_a_team_with_no_stored_chart_is_an_empty_page_not_an_error(session: Session) -> None:
    page = build_team_depth(session, _league(session), "KC")
    assert page.groups == [] and page.source is None and page.updated_at is None


def _result(  # noqa: PLR0913, PLR0917
    game_id: str,
    week: int,
    home: str,
    away: str,
    score: tuple[int | None, int | None],
    status: str = "complete",
) -> NflGameRow:
    return NflGameRow(
        game_id=game_id, season="2026", week=week, home=home, away=away, game_date="2026-09-13",
        status=status, home_score=score[0], away_score=score[1],
    )  # fmt: skip


def test_the_record_counts_wins_losses_and_ties_from_finished_games(session: Session) -> None:
    session.add_all(
        [
            _result("1", 1, "SEA", "DEN", (24, 17)),  # win at home
            _result("2", 2, "LAR", "SEA", (30, 20)),  # loss on the road
            _result("3", 3, "SEA", "SF", (10, 10)),  # tie
            _result("4", 4, "KC", "SEA", (3, 6)),  # win on the road
            _result("5", 5, "SEA", "ARI", (None, None), status="pre_game"),  # not played: ignored
            _result("6", 1, "KC", "DEN", (1, 2)),  # someone else's game
        ]
    )
    session.commit()
    assert team_record(session, "2026", "SEA") == TeamRecord(wins=2, losses=1, ties=1)
    assert team_record(session, "2026", "KC") == TeamRecord(wins=0, losses=2, ties=0)


def test_no_record_when_a_finished_game_has_no_score_or_none_is_finished(session: Session) -> None:
    session.add_all(
        [
            _result("1", 1, "SEA", "DEN", (24, 17)),
            _result("2", 2, "LAR", "SEA", (None, None)),  # finished, but the score is not stored
            _result("3", 1, "KC", "DEN", (None, None), status="pre_game"),
        ]
    )
    session.commit()
    assert team_record(session, "2026", "SEA") is None  # one unscored game could make it wrong
    assert team_record(session, "2026", "KC") is None  # nothing finished yet
    assert team_record(session, "2026", "ZZZ") is None
