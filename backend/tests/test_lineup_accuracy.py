"""Sit vs start accuracy comes straight from the totals Sleeper reports for each team."""

from sqlalchemy.orm import Session

from sleeper_assistant.db import LeagueRow, RosterRow
from sleeper_assistant.sync.ingest import _potential
from sleeper_assistant.views.lineup_accuracy import build_lineup_accuracy


def _roster(rid: int, points: float, potential: float | None) -> RosterRow:
    return RosterRow(
        league_id="L1", roster_id=rid, owner_id=None, players=[], starters=[], reserve=[],
        taxi=[], wins=0, losses=0, ties=0, points_for=points, points_against=0,
        potential_points=potential,
    )  # fmt: skip


def _league(session: Session, *rosters: RosterRow) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=len(rosters),
        scoring_settings={}, roster_positions=[], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(rosters)
    session.commit()
    return league


def test_accuracy_is_sleepers_points_over_sleepers_potential_points(session: Session) -> None:
    result = build_lineup_accuracy(
        session, _league(session, _roster(1, 900.0, 1000.0), _roster(2, 950.5, 950.5))
    )
    assert [t.roster_id for t in result.teams] == [2, 1]  # most accurate first
    perfect, miss = result.teams
    assert (perfect.accuracy, perfect.left_on_bench) == (1.0, 0.0)
    assert (miss.points, miss.potential, miss.accuracy, miss.left_on_bench) == (
        900.0, 1000.0, 0.9, 100.0,
    )  # fmt: skip


def test_a_team_without_potential_points_has_no_figure_not_a_guess(session: Session) -> None:
    result = build_lineup_accuracy(
        session, _league(session, _roster(1, 500.0, None), _roster(2, 400.0, 0.0), _roster(3, 1, 2))
    )
    by_id = {t.roster_id: t for t in result.teams}
    assert by_id[1].accuracy is None and by_id[1].left_on_bench is None
    assert by_id[2].accuracy is None  # a zero potential cannot be divided by
    assert next(t.roster_id for t in result.teams) == 3  # teams with a figure come first


def test_accuracy_never_shows_above_one_hundred_percent(session: Session) -> None:
    result = build_lineup_accuracy(session, _league(session, _roster(1, 100.04, 100.0)))
    assert result.teams[0].accuracy == 1.0
    assert result.teams[0].left_on_bench == 0.0


def test_potential_points_are_read_from_the_rosters_settings() -> None:
    assert _potential({"ppts": 1200, "ppts_decimal": 34}) == 1200.34
    assert _potential({"ppts": 1200}) == 1200.0
    assert _potential({"fpts": 5}) is None  # an older roster without the field
