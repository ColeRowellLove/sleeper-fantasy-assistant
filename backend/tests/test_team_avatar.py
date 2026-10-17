from sqlalchemy.orm import Session

from sleeper_assistant.db import RosterRow, SleeperUserRow, UserLeagueRow
from sleeper_assistant.team_avatar import avatar_id, team_avatar_url, team_avatars


def test_the_teams_own_picture_must_be_a_sleeper_image() -> None:
    assert team_avatar_url({"avatar": "https://sleepercdn.com/uploads/x.png"}) == (
        "https://sleepercdn.com/uploads/x.png"
    )
    assert team_avatar_url({"avatar": "https://evil.example/x.png"}) is None
    assert team_avatar_url({"avatar": ""}) is None
    assert team_avatar_url(None) is None


def test_an_avatar_id_is_letters_and_digits_only() -> None:
    assert avatar_id("abc123") == "abc123"
    assert avatar_id("../etc") is None
    assert avatar_id(None) is None


def _roster(roster_id: int, owner: str | None) -> RosterRow:
    return RosterRow(
        league_id="L",
        roster_id=roster_id,
        owner_id=owner,
        players=[],
        starters=[],
        reserve=[],
        taxi=[],
        wins=0,
        losses=0,
        ties=0,
        points_for=0.0,
        points_against=0.0,
    )


def test_a_team_shows_its_own_picture_then_the_managers_then_none(session: Session) -> None:
    session.add_all(
        [
            SleeperUserRow(user_id="a", username="a", display_name="A", avatar="av1"),
            SleeperUserRow(user_id="b", username="b", display_name="B", avatar="av2"),
            SleeperUserRow(user_id="c", username="c", display_name="C"),
            UserLeagueRow(user_id="a", league_id="L", team_avatar="https://sleepercdn.com/t.png"),
            UserLeagueRow(user_id="b", league_id="L"),
        ]
    )
    rosters = [_roster(1, "a"), _roster(2, "b"), _roster(3, "c"), _roster(4, None)]
    session.add_all(rosters)
    session.commit()
    assert team_avatars(session, rosters) == {
        1: "https://sleepercdn.com/t.png",
        2: "https://sleepercdn.com/avatars/thumbs/av2",
        3: None,
        4: None,
    }
