"""Kickoff times from the nflverse schedule (CC-BY 4.0, https://github.com/nflverse/nflverse-data).

Sleeper's schedule has dates but no kickoff time. nflverse publishes both, in US Eastern time.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import NflGameRow

SCHEDULE_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
EASTERN = ZoneInfo("America/New_York")
# nflverse and Sleeper disagree on one team code; every other code matches
_TEAM_CODES = {"LA": "LAR"}

GameKey = tuple[int, str, str]  # (week, home, away)


def _team(code: str) -> str:
    return _TEAM_CODES.get(code, code)


def parse_kickoffs(csv_text: str, season: str) -> dict[GameKey, datetime]:
    """Regular-season kickoffs for one season as UTC datetimes, keyed by (week, home, away).

    Games without a published time (not yet scheduled) are left out.
    """
    out: dict[GameKey, datetime] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        if row.get("season") != season or row.get("game_type") != "REG":
            continue
        day, clock = row.get("gameday"), row.get("gametime")
        if not day or not clock:
            continue
        try:
            local = datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=EASTERN)
            week = int(row["week"])
        except (ValueError, KeyError):
            continue
        out[(week, _team(row["home_team"]), _team(row["away_team"]))] = local.astimezone(UTC)
    return out


def fetch_schedule_csv(http: httpx.Client) -> str:
    response = http.get(SCHEDULE_URL, follow_redirects=True)
    response.raise_for_status()
    return response.text


def sync_kickoffs(session: Session, http: httpx.Client, season: str) -> int:
    """Store each game's kickoff time. Returns how many games were matched."""
    kickoffs = parse_kickoffs(fetch_schedule_csv(http), season)
    matched = 0
    for row in session.scalars(select(NflGameRow).where(NflGameRow.season == season)):
        kickoff = kickoffs.get((row.week, row.home, row.away))
        if kickoff is None:
            continue
        matched += 1
        if row.kickoff != kickoff:
            row.kickoff = kickoff
    session.commit()
    return matched
