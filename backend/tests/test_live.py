"""Live game status: ESPN's scoreboard parsed, cached, overlaid on Sleeper's schedule."""

# ruff: noqa: E501  (scoreboard fixtures read better on one line)

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from sleeper_assistant import live
from sleeper_assistant.dashboard import games_for_week
from sleeper_assistant.db import NflGameRow
from sleeper_assistant.kickoffs import parse_scores, sync_kickoffs
from sleeper_assistant.live import (
    LiveGame,
    Situation,
    current_games,
    describe,
    parse_scoreboard,
    window_open,
)


def _event(  # noqa: PLR0913
    home: str, away: str, state: str, *, period: int = 0, clock: str = "0:00",
    detail: str = "", home_score: Any = "0", away_score: Any = "0",
) -> dict[str, Any]:  # fmt: skip
    return {
        "status": {
            "period": period,
            "displayClock": clock,
            "type": {"state": state, "shortDetail": detail},
        },
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": home}, "score": home_score},
                    {"homeAway": "away", "team": {"abbreviation": away}, "score": away_score},
                ]
            }
        ],
    }


PAYLOAD = {
    "week": {"number": 6},
    "events": [
        _event("DEN", "SEA", "in", period=2, clock="2:24", detail="2:24 - 2nd", home_score="14", away_score="3"),
        _event("JAX", "HOU", "pre"),
        _event("WSH", "DAL", "post", period=4, detail="Final", home_score="24", away_score="17"),
        {"status": "broken"},  # a malformed event is skipped, not fatal
    ],
}  # fmt: skip


def test_parse_reads_state_period_clock_and_scores() -> None:
    games = {(g.home, g.away): g for g in parse_scoreboard(PAYLOAD)}
    live_game = games[("DEN", "SEA")]
    assert (live_game.state, live_game.period, live_game.clock) == ("live", 2, "2:24")
    assert (live_game.home_score, live_game.away_score, live_game.week) == (14, 3, 6)
    assert games[("JAX", "HOU")].state == "upcoming"
    final = games[("WAS", "DAL")]  # ESPN's WSH is Sleeper's WAS
    assert (final.state, final.home_score, final.away_score, final.clock) == ("final", 24, 17, None)


def test_parse_survives_anything_that_is_not_a_scoreboard() -> None:
    for junk in (None, [], {"events": "x"}, {"events": [None, 3]}, {"week": 4}):
        assert parse_scoreboard(junk) == []
    unknown = {"events": [_event("DEN", "SEA", "weird")]}
    assert parse_scoreboard(unknown) == []  # a state we do not know is left out
    odd_score = {"events": [_event("DEN", "SEA", "in", home_score="x", away_score=None)]}
    assert (
        parse_scoreboard(odd_score)[0].home_score,
        parse_scoreboard(odd_score)[0].away_score,
    ) == (None, None)


def test_describe_says_where_a_game_is_in_plain_words() -> None:
    def game(state: str, **kw: Any) -> LiveGame:
        return LiveGame(week=6, home="DEN", away="SEA", state=state, **kw)  # type: ignore[arg-type]

    assert describe(game("live", period=2, clock="2:24")) == "Q2 2:24"
    assert describe(game("live", period=5, clock="4:10")) == "OT 4:10"
    assert describe(game("live", period=2, clock="0:00", detail="Halftime")) == "Halftime"
    assert describe(game("live", period=1, clock="0:00", detail="End of 1st")) == "End of 1st"
    assert describe(game("live")) == "In progress"
    assert describe(game("final", detail="Final")) == "Final"
    assert describe(game("final", detail="Final/OT")) == "Final, OT"
    assert describe(game("upcoming")) is None


def test_the_window_is_open_only_around_kickoffs_or_while_sleeper_says_in_game() -> None:
    now = datetime(2026, 10, 18, 18, 0, tzinfo=UTC)
    assert window_open([now - timedelta(hours=2)], False, now)  # kicked off two hours ago
    assert window_open([now + timedelta(minutes=30)], False, now)  # about to kick off
    assert not window_open([now + timedelta(hours=3)], False, now)  # hours away
    assert not window_open([now - timedelta(hours=9)], False, now)  # long over
    assert window_open([], True, now)  # Sleeper says a game is on
    assert not window_open([None], False, now)  # no kickoff time known


def test_the_scoreboard_is_cached_and_a_failure_falls_back_to_the_last_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}
    games = parse_scoreboard(PAYLOAD)

    def fetcher() -> list[LiveGame]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise httpx.ConnectError("down")
        return games

    monkeypatch.setattr(live, "FETCHER", fetcher)
    assert current_games(now=100.0) == games and calls["n"] == 1
    assert current_games(now=110.0) == games and calls["n"] == 1  # still fresh: no new request
    assert current_games(now=200.0) == games and calls["n"] == 2  # stale: asked again, ESPN is down
    assert current_games(now=900.0) == []  # too old to trust once ESPN has stayed down


def _row(**kw: Any) -> NflGameRow:
    base: dict[str, Any] = {
        "game_id": "g1", "season": "2026", "week": 6, "home": "DEN", "away": "SEA",
        "game_date": "2026-10-18", "status": "pre_game",
    }  # fmt: skip
    return NflGameRow(**{**base, **kw})


def _games(session: Session, monkeypatch: pytest.MonkeyPatch, scoreboard: list[LiveGame]) -> Any:
    monkeypatch.setattr(live, "FETCHER", lambda: scoreboard)
    return games_for_week(session, "2026", 6)


def test_a_live_game_shows_state_clock_and_score_from_each_teams_side(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(_row(status="in_game"))
    session.commit()
    out = _games(session, monkeypatch, parse_scoreboard(PAYLOAD))
    den, sea = out["DEN"], out["SEA"]
    assert (den.state, den.period_text) == ("live", "Q2 2:24")
    assert (den.team, den.team_score, den.opponent_score) == ("DEN", 14, 3)
    assert (sea.team, sea.team_score, sea.opponent_score) == ("SEA", 3, 14)


def test_espn_is_fresher_than_sleepers_schedule(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sleeper still says the game has not started, ESPN says it is under way
    kickoff = datetime.now(UTC) - timedelta(minutes=20)
    session.add(_row(status="pre_game", kickoff=kickoff))
    session.commit()
    out = _games(session, monkeypatch, parse_scoreboard(PAYLOAD))
    assert out["DEN"].state == "live"


def test_without_espn_sleepers_state_stands_and_no_score_is_invented(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(_row(status="in_game"))
    session.commit()
    out = _games(session, monkeypatch, [])  # ESPN has nothing
    assert out["DEN"].state == "live"
    assert (out["DEN"].team_score, out["DEN"].period_text) == (None, None)


def test_an_upcoming_game_has_no_score_even_if_the_feed_says_zero(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(_row(status="pre_game", kickoff=datetime.now(UTC) + timedelta(minutes=10)))
    session.commit()
    pre = [LiveGame(week=6, home="DEN", away="SEA", state="upcoming", home_score=0, away_score=0)]
    out = _games(session, monkeypatch, pre)
    assert (out["DEN"].state, out["DEN"].team_score) == ("upcoming", None)


def test_a_finished_game_shows_its_final_score_from_the_stored_result(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(_row(status="complete", home_score=24, away_score=17))
    session.commit()
    out = _games(session, monkeypatch, [])  # the live window is closed: nothing is fetched
    assert (out["DEN"].state, out["DEN"].period_text) == ("final", "Final")
    assert (out["DEN"].team_score, out["DEN"].opponent_score) == (24, 17)
    assert (out["SEA"].team_score, out["SEA"].opponent_score) == (17, 24)


def test_a_game_from_another_week_is_not_matched_to_this_weeks_scoreboard(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(_row(week=3, status="in_game"))  # same teams, an earlier week
    session.add(_row(game_id="g2", week=6, status="pre_game"))
    session.commit()
    monkeypatch.setattr(live, "FETCHER", lambda: parse_scoreboard(PAYLOAD))
    old = games_for_week(session, "2026", 3)
    assert old["DEN"].state == "live"  # Sleeper's own word for the old game
    assert old["DEN"].team_score is None  # and this week's score is not borrowed


CSV = (
    "season,game_type,week,gameday,gametime,home_team,away_team,home_score,away_score\n"
    "2026,REG,5,2026-10-11,13:00,DEN,SEA,24,17\n"
    "2026,REG,6,2026-10-18,13:00,KC,LV,,\n"
    "2026,REG,5,2026-10-11,13:00,LA,SF,x,3\n"
)


def test_final_scores_come_from_the_nflverse_schedule() -> None:
    assert parse_scores(CSV, "2026") == {
        (5, "DEN", "SEA"): (24, 17)
    }  # unplayed or bad rows skipped


def test_the_daily_kickoff_sync_stores_final_scores(session: Session) -> None:
    session.add(_row(week=5, status="complete"))
    session.commit()
    http = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200, text=CSV)))
    sync_kickoffs(session, http, "2026")
    session.expire_all()
    row = session.get(NflGameRow, "g1")
    assert row is not None and (row.home_score, row.away_score) == (24, 17)


def test_scoreboard_fetch_asks_espn_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=json.dumps(PAYLOAD))

    real = httpx.Client
    monkeypatch.setattr(
        live.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )
    assert len(live.fetch_scoreboard()) == 3
    assert seen == [live.SCOREBOARD_URL]


def _live_event(situation: Any, state: str = "in") -> dict[str, Any]:
    event = _event("DEN", "SEA", state, period=2, clock="2:24", detail="2:24 - 2nd")
    competition = event["competitions"][0]
    competition["competitors"][0]["team"]["id"] = "7"  # DEN
    competition["competitors"][1]["team"]["id"] = "26"  # SEA
    if situation is not None:
        competition["situation"] = situation
    return {"events": [event]}


def _situation(block: Any, state: str = "in") -> Situation | None:
    return parse_scoreboard(_live_event(block, state))[0].situation


def test_the_ball_down_and_distance_and_red_zone_are_read_from_a_live_game() -> None:
    got = _situation(
        {
            "possession": "26", "shortDownDistanceText": "3rd & 4", "possessionText": "DEN 18",
            "downDistanceText": "3rd & 4 at DEN 18", "isRedZone": True,
        }
    )  # fmt: skip
    assert got == Situation(
        possession="SEA", down_distance="3rd & 4", ball_on="DEN 18", red_zone=True
    )


def test_each_part_is_optional_and_the_long_down_text_is_the_fallback() -> None:
    assert _situation({"possession": "7", "downDistanceText": "1st & 10 at DEN 35"}) == Situation(
        possession="DEN", down_distance="1st & 10 at DEN 35", ball_on=None, red_zone=False
    )
    assert _situation({"isRedZone": False, "possessionText": "SEA 40"}) == Situation(
        possession=None, down_distance=None, ball_on="SEA 40", red_zone=False
    )


def test_espn_codes_in_the_yard_line_are_written_the_way_the_app_does() -> None:
    event = _live_event({"possession": "28", "possessionText": "WSH 35"})
    competition = event["events"][0]["competitions"][0]
    competition["competitors"][0]["team"].update({"abbreviation": "WSH", "id": "28"})
    got = parse_scoreboard(event)[0].situation
    assert got is not None and got.ball_on == "WAS 35" and got.possession == "WAS"


def test_junk_empty_or_missing_situations_give_none_and_never_break_the_parse() -> None:
    for block in (
        None,
        "text",
        5,
        [],
        {},
        {"possession": None},
        {"isRedZone": "yes"},
        {"possession": "999"},
    ):
        assert _situation(block) is None, block
    assert len(parse_scoreboard(_live_event({"down": object()}))) == 1


def test_a_game_that_is_not_live_has_no_situation() -> None:
    for state in ("pre", "post"):
        assert _situation({"possession": "7", "isRedZone": True}, state) is None


def test_the_situation_reaches_both_teams_only_while_the_game_is_live(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(_row(status="in_game"))
    session.commit()
    board = parse_scoreboard(
        _live_event({"possession": "7", "possessionText": "SEA 35", "isRedZone": False})
    )
    out = _games(session, monkeypatch, board)
    for team in ("DEN", "SEA"):
        assert out[team].situation == Situation(
            possession="DEN", down_distance=None, ball_on="SEA 35", red_zone=False
        )
    live.reset_cache()
    quiet = _games(session, monkeypatch, [])  # ESPN has nothing: no situation is made up
    assert quiet["DEN"].state == "live" and quiet["DEN"].situation is None


def test_a_full_realistic_situation_block_is_read_and_extra_keys_are_ignored() -> None:
    block = {
        "down": 1, "yardLine": 82, "distance": 10, "isRedZone": True, "homeTimeouts": 3,
        "awayTimeouts": 2, "possession": "7", "downDistanceText": "1st & 10 at SEA 18",
        "shortDownDistanceText": "1st & 10", "possessionText": "SEA 18",
        "lastPlay": {"id": "401", "type": {"id": "24", "text": "Rush"}, "text": "R.Smith up the middle"},
    }  # fmt: skip
    assert _situation(block) == Situation(
        possession="DEN", down_distance="1st & 10", ball_on="SEA 18", red_zone=True
    )


@pytest.mark.parametrize("detail", ["Halftime", "End of 2nd Quarter", "End of 1st"])
def test_between_plays_no_situation_is_shown_even_if_espn_leaves_the_last_one(detail: str) -> None:
    event = _live_event({"possession": "7", "possessionText": "SEA 35", "isRedZone": True})
    event["events"][0]["status"]["type"]["shortDetail"] = detail
    assert parse_scoreboard(event)[0].situation is None


def test_an_unreadable_situation_block_is_logged_not_silently_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING", logger="sleeper_assistant.live"):
        assert _situation({"somethingNew": {"yard": 5}}) is None
    assert "could not read the ESPN situation block" in caplog.text
    assert "somethingNew" in caplog.text
    caplog.clear()
    with caplog.at_level("WARNING", logger="sleeper_assistant.live"):
        assert _situation({}) is None  # an empty block is just "nothing to say"
    assert caplog.text == ""
