from sqlalchemy.orm import Session

from sleeper_assistant.dashboard import build_dashboard
from sleeper_assistant.db import LeagueRow, PlayerRow, RosterRow, SleeperUserRow


def _league() -> LeagueRow:
    return LeagueRow(
        league_id="L1",
        name="Family",
        season="2026",
        total_rosters=3,
        scoring_settings={},
        roster_positions=[],
        settings={},
    )


def _roster(
    rid: int, owner: str | None, wins: int, losses: int, pf: float, **kw: object
) -> RosterRow:
    return RosterRow(
        league_id="L1",
        roster_id=rid,
        owner_id=owner,
        players=kw.get("players", []),  # type: ignore[arg-type]
        starters=kw.get("starters", []),  # type: ignore[arg-type]
        wins=wins,
        losses=losses,
        ties=0,
        points_for=pf,
        points_against=100.0,
    )


def test_standings_order_and_team_names(session: Session) -> None:
    league = _league()
    session.add(league)
    session.add_all([SleeperUserRow(user_id="u1", username="cole", display_name="Cole")])
    session.add_all(
        [
            _roster(1, "u1", 2, 1, 300.0),
            _roster(2, None, 2, 1, 350.5),  # same record, more points -> ahead; no owner name
            _roster(3, "ghost", 3, 0, 100.0),  # best record; owner not in users table
        ]
    )
    session.commit()

    dash = build_dashboard(session, league)

    assert [s.roster_id for s in dash.standings] == [3, 2, 1]
    assert [s.rank for s in dash.standings] == [1, 2, 3]
    teams = {s.roster_id: s.team for s in dash.standings}
    assert teams == {1: "Cole", 2: "Team 2", 3: "Team 3"}


def test_rosters_list_starters_first_and_fall_back_to_ids(session: Session) -> None:
    league = _league()
    session.add(league)
    session.add_all(
        [
            PlayerRow(
                player_id="10", full_name="Star RB", position="RB", team="SF", external_ids={}
            ),
            PlayerRow(
                player_id="11", full_name="Bench WR", position="WR", team="MIN", external_ids={}
            ),
        ]
    )
    session.add(_roster(1, None, 0, 0, 0.0, players=["11", "10", "999"], starters=["10"]))
    session.commit()

    roster = build_dashboard(session, league).rosters[0]

    assert [p.name for p in roster.players] == ["Star RB", "Bench WR", "999"]
    assert roster.players[0].starter
    assert not roster.players[2].starter
    assert roster.players[2].position is None
