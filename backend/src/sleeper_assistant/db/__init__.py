"""Database schema (SQLAlchemy 2.0). Postgres in production; SQLite works for tests.

Every league-scoped table is keyed by ``league_id``. Player-level data is shared across leagues.
The tables are split by area (``leagues``, ``players``, ``games``, ``system``); everything is
importable from here, so ``from sleeper_assistant.db import LeagueRow`` keeps working.
"""

from sleeper_assistant.db.base import Base, as_utc, utcnow
from sleeper_assistant.db.engine import (
    database_url,
    make_engine,
    make_session_factory,
    normalize_url,
)
from sleeper_assistant.db.games import (
    NflGameRow,
)
from sleeper_assistant.db.leagues import (
    LeagueRow,
    MatchupRow,
    RosterRow,
    SleeperUserRow,
    TransactionRow,
    UserLeagueRow,
)
from sleeper_assistant.db.players import (
    CrosswalkRow,
    PlayerInjuryRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerSeasonStatsRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    TeamDepthChartRow,
)
from sleeper_assistant.db.system import (
    AlertRow,
    JobRow,
    NewsItemRow,
    RawSnapshotRow,
)

__all__ = [
    "AlertRow",
    "Base",
    "CrosswalkRow",
    "JobRow",
    "LeagueRow",
    "MatchupRow",
    "NewsItemRow",
    "NflGameRow",
    "PlayerInjuryRow",
    "PlayerOwnershipRow",
    "PlayerProjectionRow",
    "PlayerRow",
    "PlayerSeasonStatsRow",
    "PlayerTrendRow",
    "PlayerWeekStatsRow",
    "RawSnapshotRow",
    "RosterRow",
    "SleeperUserRow",
    "TeamDepthChartRow",
    "TransactionRow",
    "UserLeagueRow",
    "as_utc",
    "database_url",
    "make_engine",
    "make_session_factory",
    "normalize_url",
    "utcnow",
]
