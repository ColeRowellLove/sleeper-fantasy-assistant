from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from sleeper_assistant.alert_helpers import alert_key, first_game_date, lineup_week, player_tag
from sleeper_assistant.db import LeagueRow, NflGameRow, PlayerRow, RosterRow
from sleeper_assistant.player_names import player_name
from sleeper_assistant.rosters import league_rosters


def _league() -> LeagueRow:
    return LeagueRow(
        league_id="L", name="x", season="2026", total_rosters=2, scoring_settings={},
        roster_positions=[], settings={},
    )  # fmt: skip


def test_a_key_names_the_kind_then_the_occurrence() -> None:
    assert alert_key("bye_week", "p1", "2026", 7) == "bye_week:p1:2026:7"


def test_an_alert_is_only_due_within_the_window_before_the_first_game(session: Session) -> None:
    session.add_all(
        [
            NflGameRow(game_id="a", season="2026", week=7, home="A", away="B",
                       status="pre_game", game_date="2026-10-18"),
            NflGameRow(game_id="b", season="2026", week=7, home="C", away="D",
                       status="pre_game", game_date="2026-10-19"),
        ]
    )  # fmt: skip
    session.commit()
    assert first_game_date(session, "2026", 7).isoformat() == "2026-10-18"  # type: ignore[union-attr]
    league, window = _league(), timedelta(days=2)
    assert lineup_week(session, league, datetime(2026, 10, 16, 12, tzinfo=UTC), window) == 7
    assert lineup_week(session, league, datetime(2026, 10, 15, 12, tzinfo=UTC), window) is None
    assert lineup_week(session, league, datetime(2026, 10, 1, tzinfo=UTC), window) is None


def test_names_and_tags_never_show_a_blank(session: Session) -> None:
    named = PlayerRow(player_id="p", full_name="Jayden Daniels", position="QB", team="WAS",
                      external_ids={})  # fmt: skip
    unnamed = PlayerRow(player_id="q", full_name=None, position="RB", team="KC", external_ids={})
    defense = PlayerRow(player_id="CLE", full_name="Cleveland", position="DEF", team="CLE",
                        external_ids={})  # fmt: skip
    assert player_tag(named) == "Jayden Daniels (QB, WAS)"
    assert player_name(unnamed) == "q"
    assert player_name(defense) == "CLE defense"


def test_a_leagues_rosters_come_back_by_roster_id(session: Session) -> None:
    session.add(_league())
    session.flush()
    for rid in (2, 1):
        session.add(RosterRow(league_id="L", roster_id=rid, owner_id=None, players=[], starters=[]))
    session.add(RosterRow(league_id="L2", roster_id=1, owner_id=None, players=[], starters=[]))
    session.commit()
    assert [r.roster_id for r in league_rosters(session, "L")] == [1, 2]
