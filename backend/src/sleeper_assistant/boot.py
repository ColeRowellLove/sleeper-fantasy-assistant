"""Load league data on boot: ``python -m sleeper_assistant.boot``.

Connects every league of a Sleeper username (``SLEEPER_USERNAME``) or one league
(``SLEEPER_LEAGUE_ID``), loads the player list and schedule, then runs one worker batch so
projections, rankings, depth charts and the rest are there without clicking anything. With neither
set it loads the made-up sample league into an empty SQLite database. It is safe to run again:
fresh data is skipped. Nothing here is specific to a league, so it works for any Sleeper league.
"""

from __future__ import annotations

import logging
import os
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sleeper_assistant import sample_league
from sleeper_assistant.db import LeagueRow, database_url, make_engine, make_session_factory, utcnow
from sleeper_assistant.ingest import ensure_players, ensure_schedule, sync_league
from sleeper_assistant.sleeper import SleeperClient, SleeperNotFoundError
from sleeper_assistant.worker import default_handlers, run_one_shot

log = logging.getLogger(__name__)


def leagues_for_user(sleeper: SleeperClient, username: str) -> list[str]:
    """The ids of the leagues a Sleeper username belongs to this season."""
    user = sleeper.get_user(username)
    return [lg.league_id for lg in sleeper.get_leagues(user.user_id, sleeper.get_state().season)]


def load_leagues(session: Session, sleeper: SleeperClient, league_ids: list[str]) -> list[str]:
    """Sync each league and mark it active (so the worker keeps it fresh); returns those loaded."""
    loaded: list[str] = []
    for league_id in league_ids:
        try:
            row = sync_league(session, sleeper, league_id)
        except SleeperNotFoundError:
            log.warning("league %s was not found on Sleeper", league_id)
            continue
        ensure_players(session, sleeper)
        ensure_schedule(session, sleeper, row.season)
        row.last_viewed_at = utcnow()
        session.commit()
        loaded.append(league_id)
    return loaded


def boot(
    session: Session, sleeper: SleeperClient, username: str | None, league_id: str | None
) -> int:
    """Load what was asked for (or the sample league when nothing was); returns leagues loaded."""
    if league_id:
        return len(load_leagues(session, sleeper, [league_id]))
    if username:
        return len(load_leagues(session, sleeper, leagues_for_user(sleeper, username)))
    if not session.scalar(select(func.count()).select_from(LeagueRow)):
        sample_league.seed(session)
        return 1
    return 0


def main() -> None:  # pragma: no cover - process entry point
    logging.basicConfig(level=logging.INFO)
    username = os.environ.get("SLEEPER_USERNAME") or None
    league_id = os.environ.get("SLEEPER_LEAGUE_ID") or None
    if not database_url().startswith("sqlite") and not (username or league_id):
        raise SystemExit("without SLEEPER_USERNAME or SLEEPER_LEAGUE_ID, boot only loads SQLite")
    factory = make_session_factory(make_engine())
    sleeper = SleeperClient()
    with factory() as session:
        count = boot(session, sleeper, username, league_id)
    log.info("boot loaded %d league(s)", count)
    if username or league_id:
        sys.exit(run_one_shot(factory, default_handlers(sleeper)))


if __name__ == "__main__":  # pragma: no cover
    main()
