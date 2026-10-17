"""Kickoff times and game conditions from the nflverse schedule (CC-BY 4.0).

https://github.com/nflverse/nflverse-data. Sleeper's schedule has dates but no kickoff time.
nflverse publishes both, in US Eastern time, plus the roof, surface, stadium, temperature, wind and
the betting spread and total for each game.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import EASTERN
from sleeper_assistant.db import NflGameRow

SCHEDULE_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
# nflverse and Sleeper disagree on one team code; every other code matches
_TEAM_CODES = {"LA": "LAR"}

GameKey = tuple[int, str, str]  # (week, home, away)
Score = tuple[int, int]  # (home points, away points)


@dataclass(frozen=True)
class Conditions:
    """What nflverse knows about the setting of a game. Any part can be missing."""

    roof: str | None
    surface: str | None
    stadium: str | None
    temp: int | None
    wind: int | None
    spread_line: float | None  # points the home team is favoured by
    total_line: float | None


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "", "NA") else None
    except ValueError:
        return None


def _whole(value: str | None) -> int | None:
    number = _number(value)
    return None if number is None else round(number)


def _text(value: str | None) -> str | None:
    return value if value not in (None, "", "NA") else None


def parse_conditions(csv_text: str, season: str) -> dict[GameKey, Conditions]:
    """Roof, surface, weather and betting lines for the season's regular-season games."""
    out: dict[GameKey, Conditions] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        if row.get("season") != season or row.get("game_type") != "REG":
            continue
        try:
            week = int(row["week"])
        except (ValueError, KeyError):
            continue
        out[(week, _team(row["home_team"]), _team(row["away_team"]))] = Conditions(
            roof=_text(row.get("roof")),
            surface=_text(row.get("surface")),
            stadium=_text(row.get("stadium")),
            temp=_whole(row.get("temp")),
            wind=_whole(row.get("wind")),
            spread_line=_number(row.get("spread_line")),
            total_line=_number(row.get("total_line")),
        )
    return out


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


def parse_scores(csv_text: str, season: str) -> dict[GameKey, Score]:
    """Final scores of the season's finished regular-season games, keyed by (week, home, away)."""
    out: dict[GameKey, Score] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        if row.get("season") != season or row.get("game_type") != "REG":
            continue
        try:
            home, away = int(row["home_score"]), int(row["away_score"])
            week = int(row["week"])
        except (ValueError, KeyError):
            continue  # a game not played yet has empty scores
        out[(week, _team(row["home_team"]), _team(row["away_team"]))] = (home, away)
    return out


def fetch_schedule_csv(http: httpx.Client) -> str:
    response = http.get(SCHEDULE_URL, follow_redirects=True)
    response.raise_for_status()
    return response.text


def sync_kickoffs(session: Session, http: httpx.Client, season: str) -> int:
    """Store each game's kickoff time. Returns how many games were matched."""
    text = fetch_schedule_csv(http)
    kickoffs = parse_kickoffs(text, season)
    scores = parse_scores(text, season)
    conditions = parse_conditions(text, season)
    matched = 0
    for row in session.scalars(select(NflGameRow).where(NflGameRow.season == season)):
        key = (row.week, row.home, row.away)
        score = scores.get(key)
        if score is not None and (row.home_score, row.away_score) != score:
            row.home_score, row.away_score = score
        setting = conditions.get(key)
        if setting is not None:
            row.roof, row.surface, row.stadium = setting.roof, setting.surface, setting.stadium
            row.temp, row.wind = setting.temp, setting.wind
            row.spread_line, row.total_line = setting.spread_line, setting.total_line
        kickoff = kickoffs.get(key)
        if kickoff is None:
            continue
        matched += 1
        if row.kickoff != kickoff:
            row.kickoff = kickoff
    session.commit()
    return matched
