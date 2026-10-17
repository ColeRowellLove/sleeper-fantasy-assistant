"""How a player has been playing lately."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.core.scoring.projections import score_stats
from sleeper_assistant.db import PlayerWeekStatsRow

FORM_GAMES = 3  # how many recent games make a player's form


def recent_form(
    session: Session, season: str, week: int, scoring: Mapping[str, float]
) -> dict[str, float]:
    """Points per game over the last three games played before ``week``."""
    games: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for pid, wk, stats in session.execute(
        select(
            PlayerWeekStatsRow.player_id, PlayerWeekStatsRow.week, PlayerWeekStatsRow.stats
        ).where(PlayerWeekStatsRow.season == season, PlayerWeekStatsRow.week < week)
    ):
        played = stats.get("gp")
        if played is not None and played <= 0:
            continue
        games[pid].append((wk, score_stats(stats, scoring)))
    out: dict[str, float] = {}
    for pid, rows in games.items():
        last = [points for _, points in sorted(rows)[-FORM_GAMES:]]
        out[pid] = round(sum(last) / len(last), 2)
    return out
