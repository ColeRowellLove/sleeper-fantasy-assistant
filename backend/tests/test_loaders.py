from sqlalchemy.orm import Session

from sleeper_assistant.core.league.loaders import players_by_id
from sleeper_assistant.core.league.ownership import all_players, roster_owners
from sleeper_assistant.core.models.games import GameInfo
from sleeper_assistant.core.nfl.nfl_games import bye_teams, current_week_games
from sleeper_assistant.db import PlayerRow, RosterRow


def _roster(roster_id: int, **spots: list[str]) -> RosterRow:
    base: dict[str, list[str]] = {"players": [], "starters": [], "reserve": [], "taxi": []}
    return RosterRow(league_id="L", roster_id=roster_id, owner_id=None, **(base | spots))


def test_every_spot_counts_as_owning_a_player() -> None:
    a = _roster(1, players=["p1", "p2"], reserve=["p3"], taxi=["p4"])
    b = _roster(2, players=["p5"])
    assert all_players(a) == ["p1", "p2", "p3", "p4"]
    assert roster_owners([a, b]) == {"p1": 1, "p2": 1, "p3": 1, "p4": 1, "p5": 2}


def test_players_load_by_id_and_unknown_ids_are_missing(session: Session) -> None:
    session.add_all(
        [
            PlayerRow(player_id="a", full_name="A", external_ids={}),
            PlayerRow(player_id="b", full_name="B", external_ids={}),
        ]
    )
    session.commit()
    assert set(players_by_id(session, ["a", "zzz"])) == {"a"}
    assert players_by_id(session, []) == {}
    assert set(players_by_id(session, {"a", "b"})) == {"a", "b"}


def test_a_season_with_no_games_has_no_current_week(session: Session) -> None:
    assert current_week_games(session, "2026") == (None, {})


def test_bye_teams_are_the_ones_with_no_game() -> None:
    games = {"KC": GameInfo(state="bye"), "SF": GameInfo(state="upcoming")}
    assert bye_teams(games) == {"KC"}
