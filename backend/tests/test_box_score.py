import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from sleeper_assistant.core.sources import box_score as module
from sleeper_assistant.core.sources.box_score import (
    BoxScore,
    BoxScoreError,
    BoxTeam,
    find_event_id,
    link_players,
    parse_summary,
)
from sleeper_assistant.db import PlayerRow

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "espn_summary_sample.json").read_text())


def test_every_readable_category_becomes_a_table_and_the_rest_are_skipped() -> None:
    box = parse_summary(FIXTURE, home="KC", away="WAS")  # ESPN's WSH is our WAS
    assert [t.team for t in box.teams] == ["WAS", "KC"]  # away first
    assert box.final is True
    was = box.teams[0]
    assert [t.key for t in was.tables] == ["passing", "defensive"]  # empty punting is dropped
    passing, defensive = was.tables
    assert passing.columns == ["C/ATT", "YDS", "TD", "INT"]
    assert passing.totals == ["20/30", "250", "2", "0"]
    assert [r.name for r in defensive.rows] == ["Bobby Wagner"]  # the short row is dropped
    assert defensive.rows[0].position == "LB" and defensive.totals is None
    assert box.teams[1].tables[0].title == "Rushing"


def test_a_summary_with_nothing_readable_raises() -> None:
    for bad in (None, [], {}, {"boxscore": {"players": []}}, {"boxscore": {"players": [{}]}}):
        with pytest.raises(BoxScoreError):
            parse_summary(bad, "KC", "WAS")


def test_the_event_is_found_by_its_two_teams() -> None:
    board = {
        "events": [
            {
                "id": "401",
                "competitions": [
                    {
                        "competitors": [
                            {"homeAway": "home", "team": {"abbreviation": "KC"}},
                            {"homeAway": "away", "team": {"abbreviation": "WSH"}},
                        ]
                    }
                ],
            },
            {"id": "x"},
        ]
    }
    assert find_event_id(board, "KC", "WAS") == "401"
    assert find_event_id(board, "WAS", "KC") is None
    assert find_event_id({}, "KC", "WAS") is None


def test_players_are_linked_only_when_the_name_and_team_match_one_player(
    session: Session,
) -> None:
    session.add_all(
        [
            PlayerRow(player_id="p1", full_name="Jayden Daniels", team="WAS", external_ids={}),
            PlayerRow(player_id="p2", full_name="Bobby Wagner", team="WAS", external_ids={}),
            PlayerRow(player_id="p3", full_name="Bobby Wagner", team="WAS", external_ids={}),
        ]
    )
    session.commit()
    box = link_players(session, parse_summary(FIXTURE, "KC", "WAS"))
    rows = {r.name: r.player_id for t in box.teams for tb in t.tables for r in tb.rows}
    assert rows["Jayden Daniels"] == "p1"
    assert rows["Bobby Wagner"] is None  # two players share the name: no guess
    assert rows["Isiah Pacheco"] is None


def test_the_box_score_is_cached_and_a_fetch_failure_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    live = BoxScore(home="KC", away="WAS", final=False, teams=[BoxTeam(team="KC", tables=[])])

    def fetcher(season: str, week: int, home: str, away: str) -> BoxScore:
        calls.append(week)
        return live

    module.reset_cache()
    monkeypatch.setattr(module, "FETCHER", fetcher)
    module.box_score("2026", 7, "KC", "WAS", now=100.0)
    module.box_score("2026", 7, "KC", "WAS", now=105.0)  # within the live window
    module.box_score("2026", 7, "KC", "WAS", now=120.0)  # a live game is asked for again
    assert calls == [7, 7]
    module.reset_cache()


def test_fetching_reports_an_unreachable_or_unlisted_game(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "scoreboard" in str(request.url):
            return httpx.Response(200, json={"events": []})
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    real = httpx.Client
    monkeypatch.setattr(module.httpx, "Client", lambda **kw: real(transport=transport, **kw))
    with pytest.raises(BoxScoreError, match="does not list"):
        module.fetch_box_score("2026", 7, "KC", "WAS")

    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(down)
    with pytest.raises(BoxScoreError, match="could not be reached"):
        module.fetch_box_score("2026", 7, "KC", "WAS")
