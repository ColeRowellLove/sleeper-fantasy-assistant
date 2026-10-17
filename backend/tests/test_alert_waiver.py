"""Waiver targets: each team's best pickups, alerted the day before the league's waiver day."""

# ruff: noqa: E501  (fixtures with long rows read better on one line)

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alerts import advice as alert_advice
from sleeper_assistant.alerts import engine as alerts
from sleeper_assistant.alerts.engine import run_alerts
from sleeper_assistant.alerts.waiver import detect_waiver_targets
from sleeper_assistant.core.league.waiver_board import replaced_by
from sleeper_assistant.core.nfl.waiver_calendar import (
    coming_week,
    day_name,
    waiver_date_if_tomorrow,
    waiver_day,
)
from sleeper_assistant.core.sources import llm
from sleeper_assistant.db import (
    AlertRow,
    LeagueRow,
    NflGameRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    RosterRow,
    TeamDepthChartRow,
    utcnow,
)

SCORING = {"rush_yd": 0.1, "rec_yd": 0.1}
MONDAY_EVENING = datetime(2026, 10, 19, 23, 0, tzinfo=UTC)  # Monday 7pm in New York
MONDAY_LATE = datetime(2026, 10, 20, 3, 30, tzinfo=UTC)  # still Monday 11:30pm in New York
TUESDAY_ET = datetime(2026, 10, 20, 4, 30, tzinfo=UTC)  # already Tuesday 12:30am in New York


def _league(**settings: object) -> LeagueRow:
    return LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=2, scoring_settings=SCORING,
        roster_positions=["RB", "WR", "WR", "BN"], settings=dict(settings), last_viewed_at=utcnow(),
    )  # fmt: skip


def test_the_waiver_day_comes_from_the_league_with_tuesday_as_the_default() -> None:
    assert waiver_day(_league(waiver_day_of_week=4)) == 4
    assert waiver_day(_league(waiver_day_of_week=0)) == 0  # Sunday is a real value
    assert waiver_day(_league()) == 2
    for junk in (None, "2", 7, -1, True, 2.5):
        assert waiver_day(_league(waiver_day_of_week=junk)) == 2


def test_the_alert_date_is_the_day_before_the_waiver_day_in_eastern_time() -> None:
    league = _league(waiver_day_of_week=2)  # Tuesday
    assert waiver_date_if_tomorrow(league, MONDAY_EVENING) == date(2026, 10, 20)
    assert waiver_date_if_tomorrow(league, MONDAY_LATE) == date(2026, 10, 20)  # still Monday in ET
    assert waiver_date_if_tomorrow(league, TUESDAY_ET) is None  # Tuesday itself is too late
    early = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)  # Monday 8am in New York
    assert waiver_date_if_tomorrow(league, early) is None  # wait for the overnight syncs
    assert waiver_date_if_tomorrow(league, early + timedelta(hours=2)) == date(2026, 10, 20)
    assert waiver_date_if_tomorrow(league, MONDAY_EVENING - timedelta(days=1)) is None  # Sunday
    assert day_name(date(2026, 10, 20)) == "Tuesday"


def test_the_day_before_wraps_around_the_week() -> None:
    sunday_league = _league(waiver_day_of_week=0)  # Sunday waivers: alert on Saturday
    saturday = datetime(2026, 10, 24, 17, 0, tzinfo=UTC)
    assert waiver_date_if_tomorrow(sunday_league, saturday) == date(2026, 10, 25)
    assert day_name(date(2026, 10, 25)) == "Sunday"
    saturday_league = _league(waiver_day_of_week=6)  # Saturday waivers: alert on Friday
    friday = datetime(2026, 10, 23, 17, 0, tzinfo=UTC)
    assert waiver_date_if_tomorrow(saturday_league, friday) == date(2026, 10, 24)


def test_a_pickup_replaces_an_open_slot_first_then_the_weakest_starter_he_could_replace() -> None:
    slots = ["RB", "WR", "WR", "FLEX"]
    points = {"rb": 15.0, "w1": 12.0, "w2": 8.0, "flex": 6.0}
    full = [("RB", "rb"), ("WR", "w1"), ("WR", "w2"), ("FLEX", "flex")]
    assert replaced_by(slots, full, points, "WR") == ("FLEX", 6.0, "flex")  # the flex counts
    assert replaced_by(slots, full, points, "RB") == ("FLEX", 6.0, "flex")  # a back can take it too
    assert replaced_by(slots, full, points, "QB") == ("QB", 0.0, None)  # no slot for the position
    open_flex = [("RB", "rb"), ("WR", "w1"), ("WR", "w2")]  # nobody in the flex slot
    assert replaced_by(slots, open_flex, points, "WR") == ("FLEX", 0.0, None)
    assert replaced_by(slots, [], points, "RB") == ("RB", 0.0, None)  # an empty team: first slot


def test_the_coming_week_is_the_first_whose_games_start_on_or_after_the_waiver_date(
    session: Session,
) -> None:
    session.add_all(
        [
            NflGameRow(game_id="a", season="2026", week=6, home="SF", away="DAL",
                       game_date="2026-10-19", status="in_game"),  # Monday night, still on
            NflGameRow(game_id="b", season="2026", week=7, home="SF", away="DEN",
                       game_date="2026-10-22", status="pre_game"),
            NflGameRow(game_id="c", season="2026", week=8, home="SF", away="KC",
                       game_date="2026-10-29", status="pre_game"),
        ]
    )  # fmt: skip
    session.commit()
    assert coming_week(session, "2026", date(2026, 10, 20)) == 7
    assert coming_week(session, "2026", date(2026, 10, 27)) == 8
    assert coming_week(session, "2026", date(2026, 12, 1)) == 6  # nothing later: the current week


def _player(
    pid: str, pos: str, name: str, team: str = "SF", status: str | None = None
) -> PlayerRow:
    return PlayerRow(
        player_id=pid, full_name=name, position=pos, team=team, injury_status=status,
        external_ids={},
    )  # fmt: skip


def _proj(pid: str, yards: float) -> PlayerProjectionRow:
    return PlayerProjectionRow(
        season="2026", week=7, player_id=pid, team="SF", stats={"rec_yd": yards}, fetched_at=utcnow()
    )  # fmt: skip


def _roster(rid: int, players: list[str], reserve: list[str] | None = None) -> RosterRow:
    return RosterRow(
        league_id="L1", roster_id=rid, owner_id=f"u{rid}", players=players, starters=[],
        reserve=reserve or [], taxi=[], wins=0, losses=0, ties=0, points_for=0, points_against=0,
    )  # fmt: skip


def _setup(session: Session, **settings: object) -> LeagueRow:
    league = _league(**settings)
    session.add(league)
    session.add_all(
        [
            NflGameRow(game_id="g", season="2026", week=7, home="SF", away="DAL",
                       game_date="2026-10-25", status="pre_game"),
            NflGameRow(game_id="b", season="2026", week=7, home="SEA", away="DEN",
                       game_date="2026-10-25", status="pre_game"),
            NflGameRow(game_id="d6", season="2026", week=6, home="DEN", away="DAL",
                       game_date="2026-10-18", status="complete"),
            # Monday Night Football is still on, so the current week is 6; the coming one is 7
            NflGameRow(game_id="mnf", season="2026", week=6, home="KC", away="LV",
                       game_date="2026-10-19", status="in_game"),
            # week 6 is over, so week 7 is the coming one; these teams played then and not in week 7
            NflGameRow(game_id="p6", season="2026", week=6, home="SEA", away="XYZ",
                       game_date="2026-10-18", status="complete"),
            # team 1: WR1 12.0 and WR2 8.0; no running back at all
            _player("wr1", "WR", "Top Receiver"), _player("wr2", "WR", "Second Receiver"),
            # team 2: two strong receivers and a running back
            _player("s1", "WR", "Strong One"), _player("s2", "WR", "Strong Two"),
            _player("s_rb", "RB", "Strong Back"),
            # free agents
            _player("fa_wr", "WR", "Horton"), _player("fa_low", "WR", "Low Receiver"),
            _player("fa_rb", "RB", "Free Back"), _player("fa_out", "WR", "Hurt Receiver", status="Out"),
            _player("fa_bye", "WR", "Bye Receiver", team="XYZ"),
            _player("fa_none", "WR", "No Projection"),
            _proj("wr1", 120.0), _proj("wr2", 80.0), _proj("s1", 200.0), _proj("s2", 190.0), _proj("s_rb", 100.0),
            _proj("fa_wr", 114.0), _proj("fa_low", 70.0), _proj("fa_rb", 90.0),
            _proj("fa_out", 300.0), _proj("fa_bye", 300.0),
            _roster(1, ["wr1", "wr2"]),
            _roster(2, ["s1", "s2", "s_rb"]),
            PlayerTrendRow(player_id="fa_wr", adds=8200, drops=None, fetched_at=utcnow()),
        ]
    )  # fmt: skip
    session.commit()
    return league


def _by_team(session: Session) -> dict[int, AlertRow]:
    return {a.roster_id: a for a in session.scalars(select(AlertRow))}


def test_targets_are_ranked_by_projected_gain_over_the_teams_starter_level_player(
    session: Session,
) -> None:
    league = _setup(session)
    assert run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING) == 1
    alert = _by_team(session)[1]
    assert alert.kind == "waiver_targets"
    assert alert.title == "Top waiver targets for Tuesday, Oct 20"
    targets = alert.data["targets"]
    assert [t["player_id"] for t in targets] == ["fa_rb", "fa_wr"]  # type: ignore[index]
    assert alert.why.startswith("1. Free Back (RB, SF): projected 9.0, +9.0 at an open RB spot.")
    assert "2. Horton (WR, SF): projected 11.4, +3.4 over Second Receiver at WR." in alert.why
    assert "Added in 8,200 leagues in the last day." in alert.why


def test_a_team_with_nothing_useful_gets_no_alert_and_unusable_players_are_never_suggested(
    session: Session,
) -> None:
    league = _setup(session)
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert 2 not in _by_team(session)  # its receivers beat every free agent; nothing padded
    suggested = {t["player_id"] for t in _by_team(session)[1].data["targets"]}  # type: ignore[union-attr]
    assert suggested.isdisjoint({"fa_low", "fa_out", "fa_bye", "fa_none"})


def test_a_pickup_on_a_bye_is_skipped_for_the_coming_week(session: Session) -> None:
    league = _setup(session)
    session.add(_player("fa_sea", "WR", "Seattle Receiver", team="SEA"))
    session.add(_proj("fa_sea", 150.0))
    session.query(NflGameRow).filter(NflGameRow.game_id == "b").delete()
    session.add(NflGameRow(game_id="o", season="2026", week=7, home="KC", away="LV",
                           game_date="2026-10-25", status="pre_game"))  # fmt: skip
    session.commit()
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert "fa_sea" not in {t["player_id"] for t in _by_team(session)[1].data["targets"]}  # type: ignore[union-attr]


def test_it_fires_the_day_before_only_and_only_once_per_waiver_cycle(session: Session) -> None:
    league = _setup(session)
    assert run_alerts(session, league, {"w": detect_waiver_targets}, TUESDAY_ET) == 0
    assert (
        run_alerts(
            session, league, {"w": detect_waiver_targets}, MONDAY_EVENING - timedelta(days=1)
        )
        == 0
    )
    assert run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING) == 1
    assert run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_LATE) == 0  # same cycle
    # a week later there is a new cycle (week 8 is now the coming one, with its own projections)
    session.add(NflGameRow(game_id="w8", season="2026", week=8, home="SF", away="DEN",
                           game_date="2026-10-29", status="pre_game"))  # fmt: skip
    session.add_all(
        PlayerProjectionRow(season="2026", week=8, player_id=pid, team="SF",
                            stats={"rec_yd": yards}, fetched_at=utcnow())
        for pid, yards in (("wr1", 120.0), ("wr2", 80.0), ("fa_wr", 114.0), ("fa_rb", 90.0),
                           ("s1", 200.0), ("s2", 190.0), ("s_rb", 100.0))
    )  # fmt: skip
    session.commit()
    next_week = MONDAY_EVENING + timedelta(days=7)
    assert run_alerts(session, league, {"w": detect_waiver_targets}, next_week) == 1  # new cycle


def test_the_leagues_own_waiver_day_decides_when(session: Session) -> None:
    league = _setup(session, waiver_day_of_week=4)  # Thursday waivers: alert on Wednesday
    assert run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING) == 0
    wednesday = datetime(2026, 10, 21, 16, 0, tzinfo=UTC)
    assert run_alerts(session, league, {"w": detect_waiver_targets}, wednesday) == 1
    assert _by_team(session)[1].title == "Top waiver targets for Thursday, Oct 22"


def test_an_out_starter_ahead_of_a_pickup_is_named(session: Session) -> None:
    league = _setup(session)
    session.add(_player("out_starter", "WR", "Out Starter", status="Out"))
    chart = {"offense": {"wr1": [
        {"name": "Out Starter", "sleeper_id": "out_starter", "espn_id": "1", "injury": "Out"},
        {"name": "Horton", "sleeper_id": "fa_wr", "espn_id": "2", "injury": None},
    ]}, "defense": {}, "special": {}}  # fmt: skip
    session.add(TeamDepthChartRow(team="SF", source="ESPN", chart=chart, fetched_at=utcnow()))
    session.commit()
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert "Out Starter is out ahead of him." in _by_team(session)[1].why


def test_players_on_injured_reserve_do_not_count_as_the_teams_depth(session: Session) -> None:
    league = _setup(session)
    roster = session.get(RosterRow, ("L1", 2))
    assert roster is not None
    roster.reserve = ["s1", "s2"]  # both strong receivers are parked: team 2 now has open WR spots
    session.commit()
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert 2 in _by_team(session)


def test_registered_with_the_engine() -> None:
    assert alerts.DETECTORS["waiver_targets"] is detect_waiver_targets


def test_a_pickup_must_beat_the_player_in_the_flex_slot_he_would_really_take(
    session: Session,
) -> None:
    league = _setup(session)
    league.roster_positions = ["RB", "WR", "FLEX", "BN"]
    # team 1 now has a strong back, a strong receiver and a second back who fills the flex
    session.add_all([_player("rb_a", "RB", "Back A"), _player("rb_b", "RB", "Back B"),
                     _proj("rb_a", 150.0), _proj("rb_b", 110.0)])  # fmt: skip
    roster = session.get(RosterRow, ("L1", 1))
    assert roster is not None
    roster.players = ["wr1", "rb_a", "rb_b"]
    session.commit()
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    # Horton (11.4) is not better than Back B (11.0) by enough, and the flex is the weakest slot
    assert 1 not in _by_team(session)  # nothing beats the weakest slot by enough: no alert


def test_a_roster_player_who_cannot_play_does_not_hold_a_starting_slot(session: Session) -> None:
    league = _setup(session)
    wr2 = session.get(PlayerRow, "wr2")
    assert wr2 is not None
    wr2.injury_status = "Out"  # the second receiver is ruled out this week
    session.commit()
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    why = _by_team(session)[1].why
    assert "Horton (WR, SF): projected 11.4, +11.4 at an open WR spot." in why


def test_doubtful_pickups_are_not_suggested(session: Session) -> None:
    league = _setup(session)
    horton = session.get(PlayerRow, "fa_wr")
    assert horton is not None
    horton.injury_status = "Doubtful"
    session.commit()
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert "fa_wr" not in {t["player_id"] for t in _by_team(session)[1].data["targets"]}  # type: ignore[union-attr]


def test_the_coming_week_after_monday_night_is_used_for_projections_and_byes(
    session: Session,
) -> None:
    league = _setup(session)
    # a projection for week 6 only: it must not be suggested for week 7's waivers
    session.add_all([_player("old_wk", "WR", "Last Week Only"),
                     PlayerProjectionRow(season="2026", week=6, player_id="old_wk", team="SF",
                                         stats={"rec_yd": 500.0}, fetched_at=utcnow())])  # fmt: skip
    session.commit()
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert _by_team(session)[1].data["week"] == 7
    assert "old_wk" not in {t["player_id"] for t in _by_team(session)[1].data["targets"]}  # type: ignore[union-attr]


def test_nothing_is_raised_or_used_up_while_the_coming_week_has_no_projections(
    session: Session,
) -> None:
    league = _setup(session)
    session.query(PlayerProjectionRow).delete()
    session.commit()
    assert run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING) == 0
    session.add_all([_proj("fa_wr", 114.0), _proj("wr1", 120.0), _proj("wr2", 80.0)])
    session.commit()
    assert run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_LATE) >= 1  # next run
    assert 1 in _by_team(session)


class FakeLlm:
    def __init__(self, reply: str) -> None:
        self.reply, self.calls = reply, 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self.reply


def _ranking(*picks: tuple[str, str]) -> str:
    return json.dumps(
        {
            "summary": "Go for the receiver first.",
            "picks": [{"player_id": p, "drop_id": None, "reason": r} for p, r in picks],
        }
    )


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list[FakeLlm]:
    """Installs a fake model whose reply a test sets with ``model[0].reply``."""
    fake = FakeLlm("")
    monkeypatch.setattr(alert_advice, "client", lambda: fake)
    monkeypatch.setattr(alert_advice, "_budget", llm.Budget(50))
    return [fake]


def test_a_model_reorders_the_computed_pickups_and_the_numbers_stay_computed(
    session: Session, model: list[FakeLlm]
) -> None:
    league = _setup(session)
    model[0].reply = _ranking(("fa_wr", "He is projected 11.4."), ("fa_rb", "A back at 9.0."))
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    alert = _by_team(session)[1]
    advice = alert.data["advice"]
    assert [p["name"] for p in advice["picks"]] == ["Horton", "Free Back"]  # type: ignore[index]
    assert advice["picks"][0]["action"] == "pickup"  # type: ignore[index]
    assert [t["player_id"] for t in alert.data["targets"]] == ["fa_rb", "fa_wr"]  # type: ignore[index]
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert model[0].calls == 1  # the second run does not ask again for the same alert


@pytest.mark.parametrize(
    "reply",
    [
        _ranking(("fa_low", "He is projected 7.0.")),  # not one of the computed pickups
        _ranking(("fa_wr", "He is projected 25.0.")),  # a number that is not in the facts
        json.dumps({"summary": "x", "picks": []}),
        "no thanks",
    ],
)
def test_a_waiver_answer_that_breaks_a_rule_is_dropped(
    session: Session, model: list[FakeLlm], reply: str
) -> None:
    league = _setup(session)
    model[0].reply = reply
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert "advice" not in _by_team(session)[1].data


def test_a_drop_must_be_one_of_the_teams_droppable_players(
    session: Session, model: list[FakeLlm]
) -> None:
    league = _setup(session)
    bad = json.dumps(
        {
            "summary": "x",
            "picks": [{"player_id": "fa_wr", "drop_id": "s1", "reason": "Projected 11.4."}],
        }
    )
    model[0].reply = bad  # s1 is another team's player
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert "advice" not in _by_team(session)[1].data


def test_without_a_model_the_alert_has_no_advice(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(alert_advice, "client", lambda: None)
    league = _setup(session)
    run_alerts(session, league, {"w": detect_waiver_targets}, MONDAY_EVENING)
    assert "advice" not in _by_team(session)[1].data
