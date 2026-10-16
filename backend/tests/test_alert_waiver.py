"""Waiver targets: each team's best pickups, alerted the day before the league's waiver day."""

# ruff: noqa: E501  (fixtures with long rows read better on one line)

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant import alerts
from sleeper_assistant.alert_waiver import (
    baseline,
    day_name,
    detect_waiver_targets,
    starter_level,
    waiver_date_if_tomorrow,
    waiver_day,
)
from sleeper_assistant.alerts import run_alerts
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
        roster_positions=["WR", "WR", "BN"], settings=dict(settings), last_viewed_at=utcnow(),
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


def test_starter_level_counts_the_spots_a_position_can_fill() -> None:
    assert starter_level(["RB", "RB", "WR", "FLEX"], "RB") == 3
    assert starter_level(["RB", "RB", "WR", "FLEX"], "WR") == 2
    assert starter_level(["QB", "SUPER_FLEX"], "QB") == 2
    assert starter_level(["QB"], "K") == 1  # at least one


def test_the_baseline_is_the_teams_kth_best_player_or_an_open_spot() -> None:
    mine = [("A", 12.0), ("B", 8.0), ("C", 3.0)]
    assert baseline(mine, 2) == ("B", 8.0, 2)
    assert baseline(mine, 1) == ("A", 12.0, 1)
    assert baseline(mine[:1], 2) == (None, 0.0, 2)  # an open starter spot is worth nothing yet
    assert baseline([], 1) == (None, 0.0, 1)


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
    assert alert.why.startswith(
        "1. Free Back (RB, SF): projected 9.0, +9.0 at RB1, an open starter spot."
    )
    assert "2. Horton (WR, SF): projected 11.4, +3.4 over your WR2 (Second Receiver)." in alert.why
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
