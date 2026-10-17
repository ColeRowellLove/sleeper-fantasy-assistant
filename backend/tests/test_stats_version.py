from sqlalchemy.orm import Session

from sleeper_assistant.db import NflGameRow, PlayerRow, PlayerWeekStatsRow
from sleeper_assistant.stats_version import season_stats_version


def test_the_version_changes_when_a_game_completes_or_stats_are_stored(session: Session) -> None:
    assert season_stats_version(session, "2026") == (0, 0)
    session.add(
        NflGameRow(game_id="g1", season="2026", week=1, home="A", away="B", status="complete")
    )
    session.add(
        NflGameRow(game_id="g2", season="2026", week=2, home="A", away="B", status="pre_game")
    )
    session.add(PlayerRow(player_id="p", full_name="P", external_ids={}))
    session.flush()
    session.add(PlayerWeekStatsRow(season="2026", week=1, player_id="p", team="A", stats={}))
    session.commit()
    assert season_stats_version(session, "2026") == (1, 1)
    assert season_stats_version(session, "2025") == (0, 0)
