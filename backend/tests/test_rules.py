from typing import Any

import pytest

from sleeper_assistant.core.rules import ReceptionScoring, derive_rules
from sleeper_assistant.sources.sleeper import SleeperLeague


def _league(**overrides: Any) -> SleeperLeague:
    base: dict[str, Any] = {
        "league_id": "1",
        "name": "Family",
        "season": "2026",
        "total_rosters": 10,
        "scoring_settings": {"rec": 1.0, "bonus_rec_te": 0.5},
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "BN", "BN"],
        "settings": {
            "trade_deadline": 11,
            "playoff_week_start": 15,
            "playoff_teams": 6,
            "waiver_type": 2,
            "waiver_budget": 100,
        },
    }
    base.update(overrides)
    return SleeperLeague.model_validate(base)


def test_full_example() -> None:
    rules = derive_rules(_league())
    assert rules.reception_scoring is ReceptionScoring.FULL
    assert rules.te_premium == 0.5
    assert rules.flex_count == 1
    assert rules.superflex_count == 1
    assert rules.bench_size == 2
    assert "BN" not in rules.starter_slots
    assert rules.trade_deadline_week == 11
    assert rules.playoff_week_start == 15
    assert rules.playoff_teams == 6
    assert rules.uses_faab
    assert rules.faab_budget == 100


@pytest.mark.parametrize(
    ("rec", "expected"),
    [
        (0, ReceptionScoring.NONE),
        (0.5, ReceptionScoring.HALF),
        (1, ReceptionScoring.FULL),
        (0.75, ReceptionScoring.CUSTOM),
    ],
)
def test_reception_scoring(rec: float, expected: ReceptionScoring) -> None:
    assert derive_rules(_league(scoring_settings={"rec": rec})).reception_scoring is expected


def test_priority_waivers_have_no_budget() -> None:
    rules = derive_rules(_league(settings={"waiver_type": 1, "waiver_budget": 100}))
    assert not rules.uses_faab
    assert rules.faab_budget is None


def test_unset_weeks_are_none() -> None:
    rules = derive_rules(_league(settings={"trade_deadline": 0}))
    assert rules.trade_deadline_week is None
    assert rules.playoff_teams is None
