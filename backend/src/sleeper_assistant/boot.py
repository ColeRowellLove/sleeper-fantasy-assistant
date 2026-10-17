"""Load league data on boot: ``python -m sleeper_assistant.boot``.

Connects every league of a Sleeper username (``SLEEPER_USERNAME``) or one league
(``SLEEPER_LEAGUE_ID``), loads the player list and schedule the first time, then runs one worker
batch so projections, rankings, depth charts and the rest are there without clicking anything. With
neither set it loads the made-up sample league into an empty SQLite database. It is safe to run
again: the leagues are re-synced, and the player list and schedule are only loaded when missing.
Nothing here is specific to a league, so it works for any Sleeper league. It writes only to SQLite
unless ``BOOT_ALLOW_SHARED_DB=1`` is set, so a production ``DATABASE_URL`` is never touched by
accident.
"""

from __future__ import annotations

import logging
import sys

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sleeper_assistant import sample_league
from sleeper_assistant.core.sources.sleeper import SleeperClient, SleeperNotFoundError
from sleeper_assistant.db import (
    LeagueRow,
    PlayerRow,
    database_url,
    make_engine,
    make_session_factory,
)
from sleeper_assistant.settings import load_settings
from sleeper_assistant.sync.ingest import finish_connect, sync_league
from sleeper_assistant.worker import default_handlers, run_one_shot

log = logging.getLogger(__name__)


def leagues_for_user(sleeper: SleeperClient, username: str) -> list[str]:
    """The ids of the leagues a Sleeper username belongs to this season (empty if none)."""
    user = sleeper.get_user(username)
    return [lg.league_id for lg in sleeper.get_leagues(user.user_id, sleeper.get_state().season)]


def load_leagues(session: Session, sleeper: SleeperClient, league_ids: list[str]) -> list[str]:
    """Sync each league and mark it active; one that fails is logged and skipped, not fatal."""
    loaded: list[str] = []
    for league_id in league_ids:
        try:
            row = sync_league(session, sleeper, league_id)
            finish_connect(session, sleeper, row)
        except SleeperNotFoundError:
            log.warning("league %s was not found on Sleeper", league_id)
        except (httpx.HTTPError, ValidationError):
            session.rollback()
            log.exception("could not load league %s; skipping it", league_id)
        else:
            loaded.append(league_id)
    return loaded


def boot(
    session: Session, sleeper: SleeperClient, username: str | None, league_id: str | None
) -> int:
    """Load what was asked for (or the sample league when nothing was); returns leagues loaded."""
    if league_id:
        return len(load_leagues(session, sleeper, [league_id]))
    if username:
        try:
            ids = leagues_for_user(sleeper, username)
        except SleeperNotFoundError:
            log.error("Sleeper has no user %r", username)
            return 0
        except httpx.HTTPError:
            log.exception("could not reach Sleeper for %r", username)
            return 0
        if not ids:
            log.warning("%r has no leagues this season", username)
        return len(load_leagues(session, sleeper, ids))
    empty = not session.scalar(select(func.count()).select_from(LeagueRow))
    if empty and not session.scalar(select(func.count()).select_from(PlayerRow)):
        sample_league.seed(session)
        return 1
    return 0


def main() -> None:  # pragma: no cover - process entry point
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    username, league_id = settings.sleeper_username, settings.sleeper_league_id
    if not database_url().startswith("sqlite") and not settings.boot_allow_shared_db:
        raise SystemExit("boot only writes to SQLite (set BOOT_ALLOW_SHARED_DB=1 to override)")
    factory = make_session_factory(make_engine())
    sleeper = SleeperClient()
    with factory() as session:
        count = boot(session, sleeper, username, league_id)
    log.info("boot loaded %d league(s)", count)
    if (username or league_id) and count == 0:
        raise SystemExit("boot loaded no leagues (see the log above)")
    if username or league_id:
        sys.exit(run_one_shot(factory, default_handlers(sleeper)))


if __name__ == "__main__":  # pragma: no cover
    main()
