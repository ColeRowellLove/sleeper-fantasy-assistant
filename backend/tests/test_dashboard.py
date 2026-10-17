from sqlalchemy.orm import Session

from sleeper_assistant.dashboard import build_dashboard, build_lineups
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    PlayerOwnershipRow,
    PlayerRow,
    RosterRow,
    SleeperUserRow,
)


def _league(positions: list[str] | None = None) -> LeagueRow:
    return LeagueRow(
        league_id="L1",
        name="Family",
        season="2026",
        total_rosters=3,
        scoring_settings={},
        roster_positions=positions or ["RB", "WR", "BN", "BN"],
        settings={},
    )


def _roster(  # noqa: PLR0913
    rid: int,
    owner: str | None,
    *,
    wins: int = 0,
    losses: int = 0,
    pf: float = 0.0,
    players: list[str] | None = None,
    starters: list[str] | None = None,
    reserve: list[str] | None = None,
    taxi: list[str] | None = None,
) -> RosterRow:
    return RosterRow(
        league_id="L1",
        roster_id=rid,
        owner_id=owner,
        players=players or [],
        starters=starters or [],
        reserve=reserve or [],
        taxi=taxi or [],
        wins=wins,
        losses=losses,
        ties=0,
        points_for=pf,
        points_against=100.0,
    )


def _player(pid: str, name: str, pos: str, team: str) -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=name, position=pos, team=team, external_ids={})


def test_standings_order_and_team_names(session: Session) -> None:
    league = _league()
    session.add(league)
    session.add(SleeperUserRow(user_id="u1", username="cole", display_name="Cole"))
    session.add_all(
        [
            _roster(1, "u1", wins=2, losses=1, pf=300.0),
            _roster(
                2, None, wins=2, losses=1, pf=350.5
            ),  # same record, more points -> ahead; no owner name
            _roster(
                3, "ghost", wins=3, losses=0, pf=100.0
            ),  # best record; owner not in users table
        ]
    )
    session.commit()

    dash = build_dashboard(session, league)

    assert [s.roster_id for s in dash.standings] == [3, 2, 1]
    assert [s.rank for s in dash.standings] == [1, 2, 3]
    teams = {s.roster_id: s.team for s in dash.standings}
    assert teams == {1: "Cole", 2: "Team 2", 3: "Team 3"}


def test_rostered_players_carry_espn_owned_and_started_shares(session: Session) -> None:
    league = _league(["RB", "BN"])
    session.add(league)
    session.add_all([_player("10", "Star RB", "RB", "SF"), _player("11", "Bench WR", "WR", "MIN")])
    session.add(_roster(1, None, players=["10", "11"], starters=["10"]))
    session.add(PlayerOwnershipRow(player_id="10", owned=88.0, started=53.0))
    session.commit()

    players = {p.name: p for p in build_dashboard(session, league).rosters[0].players}

    assert (players["Star RB"].owned_pct, players["Star RB"].started_pct) == (88.0, 53.0)
    assert players["Bench WR"].owned_pct is None  # no ESPN number: nothing claimed


def test_roster_groups_starters_bench_ir_taxi(session: Session) -> None:
    league = _league(["RB", "WR", "BN", "BN"])
    session.add(league)
    session.add_all(
        [
            _player("10", "Star RB", "RB", "SF"),
            _player("11", "Bench WR", "WR", "MIN"),
            _player("12", "Hurt TE", "TE", "KC"),
            _player("13", "Rookie QB", "QB", "NYJ"),
        ]
    )
    session.add(
        _roster(
            1,
            None,
            players=["13", "12", "11", "10", "999"],
            starters=["10", "0"],  # "0" is Sleeper's empty-slot marker
            reserve=["12"],
            taxi=["13"],
        )
    )
    session.commit()

    players = build_dashboard(session, league).rosters[0].players

    assert [(p.name, p.status, p.slot) for p in players] == [
        ("Star RB", "starter", "RB"),
        ("Bench WR", "bench", None),
        ("999", "bench", None),  # unknown player id falls back to the id
        ("Hurt TE", "ir", None),
        ("Rookie QB", "taxi", None),
    ]
    assert players[0].position == "RB"
    assert players[0].team == "SF"
    assert players[2].position is None


def _matchup(rid: int, mid: int | None, week: int, pts: float, **kw: object) -> MatchupRow:
    return MatchupRow(
        league_id="L1",
        week=week,
        roster_id=rid,
        matchup_id=mid,
        points=pts,
        starters=kw.get("starters", []),  # type: ignore[arg-type]
        starters_points=kw.get("starters_points", []),  # type: ignore[arg-type]
        players=kw.get("players", []),  # type: ignore[arg-type]
        players_points=kw.get("players_points", {}),  # type: ignore[arg-type]
    )


def test_lineups_pair_teams_and_split_starters_from_bench(session: Session) -> None:
    league = _league(["RB", "WR", "BN", "BN"])
    session.add(league)
    session.add(SleeperUserRow(user_id="u1", username="cole", display_name="Cole"))
    session.add_all([_player("10", "Star RB", "RB", "SF"), _player("11", "Bench WR", "WR", "MIN")])
    session.add_all([_roster(1, "u1"), _roster(2, None), _roster(3, None)])
    session.add_all(
        [
            _matchup(
                1,
                7,
                5,
                20.5,
                starters=["10", "0"],
                starters_points=[20.5, 0.0],
                players=["10", "11"],
                players_points={"10": 20.5, "11": 3.25},
            ),
            _matchup(2, 7, 5, 11.0),
            _matchup(3, None, 5, 9.0),  # no matchup id: must not be paired with anyone
            _matchup(1, 1, 4, 0.0),
        ]
    )
    session.commit()

    lineups = build_lineups(session, league)  # default: latest scored week

    assert lineups.week == 5
    assert lineups.weeks == [4, 5]
    assert len(lineups.matchups) == 2
    paired = next(m for m in lineups.matchups if m.matchup_id == 7)
    assert [t.team for t in paired.teams] == ["Cole", "Team 2"]
    cole = paired.teams[0]
    assert cole.points == 20.5
    assert [(s.slot, s.name, s.points) for s in cole.starters] == [
        ("RB", "Star RB", 20.5),
        ("WR", "Empty", None),
    ]
    assert [(b.slot, b.name, b.points) for b in cole.bench] == [("BN", "Bench WR", 3.25)]
    unpaired = next(m for m in lineups.matchups if m.matchup_id is None)
    assert len(unpaired.teams) == 1


def test_lineups_for_explicit_and_unknown_weeks(session: Session) -> None:
    league = _league()
    session.add(league)
    session.add_all([_roster(1, None), _matchup(1, 1, 3, 5.0)])
    session.commit()

    assert build_lineups(session, league, week=3).week == 3
    unknown = build_lineups(session, league, week=9)
    assert unknown.week is None
    assert unknown.matchups == []
    assert unknown.weeks == [3]


def test_lineups_with_no_matchups(session: Session) -> None:
    league = _league()
    session.add(league)
    session.commit()
    assert build_lineups(session, league).matchups == []


def test_owner_ids_are_exposed_for_my_team_matching(session: Session) -> None:
    league = _league()
    session.add(league)
    session.add_all([SleeperUserRow(user_id="u1", username=None, display_name="Cole")])
    session.add_all([_roster(1, "u1"), _roster(2, None)])
    session.add_all([_matchup(1, 7, 5, 1.0), _matchup(2, 7, 5, 2.0)])
    session.commit()

    dash = build_dashboard(session, league)
    assert {s.roster_id: s.owner_id for s in dash.standings} == {1: "u1", 2: None}
    assert {r.roster_id: r.owner_id for r in dash.rosters} == {1: "u1", 2: None}

    teams = {
        t.roster_id: t.owner_id for m in build_lineups(session, league).matchups for t in m.teams
    }
    assert teams == {1: "u1", 2: None}


def test_ir_and_taxi_players_are_not_labelled_as_bench_in_lineups(session: Session) -> None:
    league = _league(["RB", "BN", "BN"])
    session.add(league)
    session.add_all(
        [
            _player("10", "Starter", "RB", "SF"),
            _player("11", "Bench Guy", "WR", "MIN"),
            _player("12", "Hurt Guy", "RB", "SEA"),
            _player("13", "Stash Guy", "QB", "NYJ"),
        ]
    )
    session.add(
        _roster(
            1, None, players=["10", "11", "12", "13"], starters=["10"], reserve=["12"], taxi=["13"]
        )
    )
    session.add(
        _matchup(
            1,
            1,
            6,
            9.0,
            starters=["10"],
            starters_points=[9.0],
            players=["10", "11", "12", "13"],  # Sleeper lists IR and taxi players here too
            players_points={"10": 9.0, "11": 4.0, "12": 99.0, "13": 0.5},
        )
    )
    session.commit()

    team = build_lineups(session, league, week=6).matchups[0].teams[0]

    assert [(b.name, b.slot) for b in team.bench] == [
        ("Bench Guy", "BN"),
        ("Hurt Guy", "IR"),  # sorted after the bench even though it has the highest points
        ("Stash Guy", "TAXI"),
    ]


def test_injury_designation_is_exposed_and_meaningless_values_are_hidden(session: Session) -> None:
    league = _league(["RB", "WR", "BN"])
    session.add(league)
    session.add_all(
        [
            PlayerRow(
                player_id="1",
                full_name="Hurt RB",
                position="RB",
                team="SF",
                injury_status="Questionable",
                injury_body_part="Hamstring",
                external_ids={},
            ),
            PlayerRow(
                player_id="2",
                full_name="Out WR",
                position="WR",
                team="MIN",
                injury_status="Out",
                injury_body_part=None,
                external_ids={},
            ),
            PlayerRow(
                player_id="3",
                full_name="Fine TE",
                position="TE",
                team="KC",
                injury_status="NA",  # carries no information
                external_ids={},
            ),
            PlayerRow(
                player_id="4", full_name="Healthy", position="QB", team="HOU", external_ids={}
            ),
        ]
    )
    session.add(_roster(1, None, players=["1", "2", "3", "4"], starters=["1", "2"]))
    session.add(
        _matchup(1, 1, 6, 0.0, starters=["1", "2"], players=["1", "2", "3", "4"], players_points={})
    )
    session.commit()

    roster = {p.name: p for p in build_dashboard(session, league).rosters[0].players}
    assert roster["Hurt RB"].injury is not None
    assert (roster["Hurt RB"].injury.status, roster["Hurt RB"].injury.body_part) == (
        "Questionable",
        "Hamstring",
    )
    assert roster["Out WR"].injury is not None
    assert roster["Out WR"].injury.body_part is None
    assert roster["Fine TE"].injury is None  # NA is hidden
    assert roster["Healthy"].injury is None

    team = build_lineups(session, league, week=6).matchups[0].teams[0]
    starters = {p.name: p for p in team.starters}
    assert starters["Hurt RB"].injury is not None
    assert starters["Hurt RB"].injury.status == "Questionable"
    bench = {p.name: p for p in team.bench}
    assert bench["Fine TE"].injury is None
