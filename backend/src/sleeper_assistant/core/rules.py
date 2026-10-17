"""Derive league rules from a Sleeper league object. Never hard-code rules elsewhere."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from sleeper_assistant.core.lineup_slots import starter_slots
from sleeper_assistant.sources.sleeper import SleeperLeague

# Sleeper waiver_type: 0 = rolling priority, 1 = reverse standings priority, 2 = FAAB
FAAB_WAIVER_TYPE = 2

HALF_PPR = 0.5

_FLEX_SLOTS = {"FLEX", "WRRB_FLEX", "REC_FLEX"}
_SUPERFLEX_SLOTS = {"SUPER_FLEX"}


class ReceptionScoring(StrEnum):
    NONE = "none"
    HALF = "half"
    FULL = "full"
    CUSTOM = "custom"


class LeagueRules(BaseModel):
    reception_scoring: ReceptionScoring
    te_premium: float
    starter_slots: list[str]
    flex_count: int
    superflex_count: int
    bench_size: int
    trade_deadline_week: int | None
    playoff_week_start: int | None
    playoff_teams: int | None
    uses_faab: bool
    faab_budget: int | None


def _reception_scoring(rec: float) -> ReceptionScoring:
    if rec == 0:
        return ReceptionScoring.NONE
    if rec == HALF_PPR:
        return ReceptionScoring.HALF
    if rec == 1:
        return ReceptionScoring.FULL
    return ReceptionScoring.CUSTOM


def _positive_or_none(value: object) -> int | None:
    """Sleeper uses 0 (or a missing key) for 'not set' on week-style settings."""
    if isinstance(value, int) and value > 0:
        return value
    return None


def derive_rules(league: SleeperLeague) -> LeagueRules:
    scoring = league.scoring_settings
    settings = league.settings
    positions = league.roster_positions
    uses_faab = settings.get("waiver_type") == FAAB_WAIVER_TYPE
    budget = _positive_or_none(settings.get("waiver_budget"))

    return LeagueRules(
        reception_scoring=_reception_scoring(float(scoring.get("rec", 0))),
        te_premium=float(scoring.get("bonus_rec_te", 0)),
        starter_slots=starter_slots(positions),
        flex_count=sum(p in _FLEX_SLOTS for p in positions),
        superflex_count=sum(p in _SUPERFLEX_SLOTS for p in positions),
        bench_size=sum(p == "BN" for p in positions),
        trade_deadline_week=_positive_or_none(settings.get("trade_deadline")),
        playoff_week_start=_positive_or_none(settings.get("playoff_week_start")),
        playoff_teams=_positive_or_none(settings.get("playoff_teams")),
        uses_faab=uses_faab,
        faab_budget=budget if uses_faab else None,
    )
