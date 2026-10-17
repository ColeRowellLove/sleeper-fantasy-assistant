"""The calculation steps of the views, tested with plain objects: no database, no session."""

from sleeper_assistant.db import PlayerRow, RosterRow, TransactionRow
from sleeper_assistant.views.games import _top_projected
from sleeper_assistant.views.lineup_accuracy import team_accuracy
from sleeper_assistant.views.lineups import _week_to_show
from sleeper_assistant.views.player_detail import WeekLine, position_ranks
from sleeper_assistant.views.transactions import transaction_item


def _roster(points: float, potential: float | None) -> RosterRow:
    return RosterRow(
        league_id="L", roster_id=1, owner_id=None, players=[], starters=[], reserve=[], taxi=[],
        wins=0, losses=0, ties=0, points_for=points, points_against=0.0,
        potential_points=potential,
    )  # fmt: skip


def test_accuracy_is_points_over_potential_and_never_above_one_hundred_percent() -> None:
    assert team_accuracy(_roster(80.0, 100.0), "A").accuracy == 0.8
    assert team_accuracy(_roster(80.0, 100.0), "A").left_on_bench == 20.0
    assert team_accuracy(_roster(101.0, 100.0), "A").accuracy == 1.0
    none = team_accuracy(_roster(80.0, None), "A")
    assert (none.accuracy, none.left_on_bench) == (None, None)


def test_a_move_lists_what_each_team_got_and_gave() -> None:
    row = TransactionRow(
        league_id="L", transaction_id="t", type="trade", status="complete", week=3,
        created_ms=1_760_000_000_000, payload={"adds": {"a": 1, "b": 2}, "drops": {"b": 1}},
    )  # fmt: skip
    player = PlayerRow(player_id="a", full_name="Q. Judkins", position="RB", team="CLE",
                       external_ids={})  # fmt: skip
    item = transaction_item(row, {1: "One", 2: "Two"}, {1: "m1"}, {"a": player})
    first, second = item.moves
    assert (first.team, [p.name for p in first.added], [p.name for p in first.dropped]) == (
        "One", ["Q. Judkins"], ["b"],
    )  # fmt: skip
    assert (second.team, second.manager) == ("Two", None)


def test_the_week_shown_is_the_asked_one_else_the_current_else_the_latest_scored() -> None:
    from sleeper_assistant.db import MatchupRow  # noqa: PLC0415

    def row(week: int, points: float) -> MatchupRow:
        return MatchupRow(league_id="L", week=week, roster_id=1, matchup_id=1, points=points)

    rows = [row(1, 10.0), row(2, 20.0), row(3, 0.0)]
    assert _week_to_show(rows, [1, 2, 3], 3, 2) == 2  # asked for
    assert _week_to_show(rows, [1, 2, 3], 3, None) == 3  # current
    assert _week_to_show(rows, [1, 2, 3], None, None) == 2  # latest with scores
    assert _week_to_show(rows, [1, 2, 3], 3, 9) is None  # not a week
    assert _week_to_show([], [], None, None) is None


def test_the_top_unrostered_projected_players_are_kept_per_team_and_position() -> None:
    def p(pid: str, pos: str) -> PlayerRow:
        return PlayerRow(player_id=pid, position=pos, team="SF", external_ids={})

    candidates = [p("q1", "QB"), p("q2", "QB"), p("r1", "RB"), p("r2", "RB"), p("r3", "RB")]
    scored = {"q1": 20.0, "q2": 25.0, "r1": 10.0, "r2": 12.0, "r3": 11.0}
    top = _top_projected(candidates, {"SF"}, scored, owner={"r2": 1})
    assert top == {"q2", "r3", "r1"}  # one QB; two RBs once the rostered one is skipped
    assert _top_projected(candidates, set(), scored, {}) == set()  # the game has started


def test_season_and_game_ranks_use_only_his_position_and_games_he_played() -> None:
    position_of = {"me": "RB", "a": "RB", "b": "RB", "wr": "WR"}
    stat_rows = [
        ("me", 1, {"rec": 5.0}), ("a", 1, {"rec": 9.0}), ("b", 1, {"rec": 1.0}),
        ("wr", 1, {"rec": 50.0}), ("a", 2, {"rec": 3.0, "gp": 0.0}),
    ]  # fmt: skip
    me = PlayerRow(player_id="me", position="RB", external_ids={})
    weeks = [WeekLine(week=1, team="X", opponent=None, home=None, final=True, points=5.0, stats={})]
    rank = position_ranks(stat_rows, position_of, me, {"rec": 1.0}, weeks)
    assert rank == 2 and weeks[0].rank == 2  # one RB scored more; the WR does not count
    assert position_ranks(stat_rows, position_of, me, {"rec": 1.0}, []) is None
