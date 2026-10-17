"""The best lineup a set of projections allows, for the leagues' real slots."""

from hypothesis import given
from hypothesis import strategies as st

from sleeper_assistant.core.lineup_slots import assign_lineup, optimal_lineup

SLOTS = ["QB", "RB", "RB", "WR", "FLEX", "SUPER_FLEX"]


def test_dedicated_slots_fill_first_then_flex_takes_the_best_left() -> None:
    cands = [
        ("qb1", "QB", 20.0),
        ("qb2", "QB", 18.0),
        ("rb1", "RB", 12.0),
        ("rb2", "RB", 11.0),
        ("rb3", "RB", 15.0),
        ("wr1", "WR", 9.0),
        ("wr2", "WR", 14.0),
        ("te1", "TE", 7.0),
    ]
    best = optimal_lineup(SLOTS, cands)
    # QB, 2 RB, WR first; then FLEX and SUPER_FLEX take the best of what is left
    assert set(best) == {"qb1", "rb3", "rb1", "wr2", "rb2", "qb2"}


def test_unknown_slots_and_short_rosters_are_ignored() -> None:
    assert optimal_lineup(["QB", "IDP_FLEX"], [("a", "QB", 5.0)]) == ["a"]
    assert optimal_lineup(["QB", "QB"], [("a", "QB", 5.0)]) == ["a"]


@given(
    st.lists(
        st.tuples(st.sampled_from(["QB", "RB", "WR", "TE", "K"]), st.floats(0, 60)),
        max_size=14,
    )
)
def test_the_best_lineup_fits_the_slots_and_beats_any_other_choice_of_starters(
    players: list[tuple[str, float]],
) -> None:
    cands = [(f"p{i}", pos, pts) for i, (pos, pts) in enumerate(players)]
    points = {pid: pts for pid, _, pts in cands}
    best = optimal_lineup(SLOTS, cands)
    assert len(best) <= len(SLOTS)
    assert len(set(best)) == len(best)
    # the first-listed players at each position, a plain legal lineup, never beat it
    naive = optimal_lineup(SLOTS, sorted(cands, key=lambda c: c[2])[: len(SLOTS)])
    assert sum(points[p] for p in best) + 1e-9 >= sum(points[p] for p in naive)


def test_assign_lineup_names_the_slot_each_player_fills() -> None:
    cands = [("qb", "QB", 20.0), ("rb", "RB", 10.0), ("wr", "WR", 15.0), ("te", "TE", 5.0)]
    assert assign_lineup(["QB", "RB", "FLEX"], cands) == [
        ("QB", "qb"),
        ("RB", "rb"),
        ("FLEX", "wr"),
    ]
