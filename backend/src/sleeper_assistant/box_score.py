"""A game's full box score from ESPN's game summary: every player and every stat category.

Sleeper only reports fantasy stats; ESPN's per-game summary also lists defenders, returners and
punters. The endpoint is unofficial, so the payload is untrusted: every part is read defensively, a
category that cannot be read is skipped with a warning, and a response with nothing readable raises
``BoxScoreError`` so the page shows an honest "not available" instead of an empty table.

The shape read here (``boxscore.players[].statistics[]`` with ``labels`` and per-athlete ``stats``)
is the one ESPN's own site uses. The test fixture is written by hand in that shape, not recorded,
because the build environment cannot reach ESPN; replace it with a recorded response when possible.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import PlayerRow
from sleeper_assistant.espn import normalize_name

log = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
_CODES = {"WSH": "WAS", "JAC": "JAX", "LA": "LAR"}
LIVE_SECONDS = 15.0  # a viewer sees a box score at most this old while the game is on
FINAL_SECONDS = 600.0  # a finished game only changes with stat corrections
TIMEOUT = 8.0


class BoxScoreError(Exception):
    """ESPN has no readable box score for this game."""


class BoxRow(BaseModel):
    name: str
    position: str | None = None
    player_id: str | None = None  # the Sleeper player, when the name and team match exactly one
    stats: list[str]


class BoxTable(BaseModel):
    key: str  # ESPN's category: passing, rushing, receiving, defensive, kicking, ...
    title: str
    columns: list[str]
    rows: list[BoxRow]
    totals: list[str] | None = None


class BoxTeam(BaseModel):
    team: str
    tables: list[BoxTable]


class BoxScore(BaseModel):
    home: str
    away: str
    final: bool
    teams: list[BoxTeam]  # away first, then home


def _code(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return _CODES.get(value, value)


def _strings(values: Any) -> list[str]:
    return [str(v) for v in values] if isinstance(values, list) else []


def _row(entry: Any, width: int) -> BoxRow | None:
    athlete = entry.get("athlete") if isinstance(entry, dict) else None
    if not isinstance(athlete, dict):
        return None
    name = athlete.get("displayName") or athlete.get("shortName")
    stats = _strings(entry.get("stats"))
    if not isinstance(name, str) or not name or len(stats) != width:
        return None
    position = athlete.get("position")
    abbreviation = position.get("abbreviation") if isinstance(position, dict) else None
    return BoxRow(
        name=name,
        position=abbreviation if isinstance(abbreviation, str) else None,
        stats=stats,
    )


def _table(block: Any) -> BoxTable | None:
    if not isinstance(block, dict):
        return None
    labels = _strings(block.get("labels"))
    key = block.get("name")
    if not labels or not isinstance(key, str):
        return None
    rows = [r for e in block.get("athletes") or [] if (r := _row(e, len(labels))) is not None]
    if not rows:
        return None
    totals = _strings(block.get("totals"))
    title = block.get("text") if isinstance(block.get("text"), str) else key.title()
    return BoxTable(
        key=key,
        title=str(title),
        columns=labels,
        rows=rows,
        totals=totals if len(totals) == len(labels) else None,
    )


def parse_summary(payload: Any, home: str, away: str) -> BoxScore:
    """The box score of an ESPN game summary; raises when no category could be read."""
    players = payload.get("boxscore", {}).get("players") if isinstance(payload, dict) else None
    if not isinstance(players, list):
        raise BoxScoreError("the summary has no box score")
    by_team: dict[str, BoxTeam] = {}
    for side in players:
        team = side.get("team") if isinstance(side, dict) else None
        code = _code(team.get("abbreviation")) if isinstance(team, dict) else None
        if code is None:
            continue
        tables = []
        for block in side.get("statistics") or []:
            table = _table(block)
            if table is None:
                log.warning("box score: skipped an unreadable %s category", code)
                continue
            tables.append(table)
        if tables:
            by_team[code] = BoxTeam(team=code, tables=tables)
    teams = [by_team[c] for c in (away, home) if c in by_team]
    if not teams:
        raise BoxScoreError("no box score category could be read")
    header = payload.get("header") if isinstance(payload, dict) else None
    final = False
    if isinstance(header, dict):
        status = (header.get("competitions") or [{}])[0].get("status", {})
        final = isinstance(status, dict) and status.get("type", {}).get("state") == "post"
    return BoxScore(home=home, away=away, final=final, teams=teams)


def find_event_id(scoreboard: Any, home: str, away: str) -> str | None:
    """The ESPN event id of the game between two teams in a scoreboard response."""
    for event in scoreboard.get("events") or [] if isinstance(scoreboard, dict) else []:
        try:
            sides = {
                c["homeAway"]: _code(c["team"]["abbreviation"])
                for c in event["competitions"][0]["competitors"]
            }
        except (KeyError, IndexError, TypeError):
            continue
        if sides.get("home") == home and sides.get("away") == away and event.get("id"):
            return str(event["id"])
    return None


def fetch_box_score(season: str, week: int, home: str, away: str) -> BoxScore:
    """Find the game on ESPN's scoreboard for the week, then read its summary."""
    try:
        with httpx.Client(timeout=TIMEOUT) as http:
            board = http.get(
                SCOREBOARD_URL, params={"dates": season, "seasontype": 2, "week": week}
            )
            board.raise_for_status()
            event_id = find_event_id(board.json(), home, away)
            if event_id is None:
                raise BoxScoreError("ESPN does not list this game")
            summary = http.get(SUMMARY_URL, params={"event": event_id})
            summary.raise_for_status()
            return parse_summary(summary.json(), home, away)
    except (httpx.HTTPError, ValueError) as error:
        raise BoxScoreError(f"ESPN could not be reached: {error}") from error


# replaceable in tests, so no test ever touches the network
Fetcher = Callable[[str, int, str, str], BoxScore]
FETCHER: Fetcher = fetch_box_score
_cache: dict[tuple[str, int, str, str], tuple[float, BoxScore]] = {}


def reset_cache() -> None:
    _cache.clear()


def box_score(season: str, week: int, home: str, away: str, now: float | None = None) -> BoxScore:
    """The box score, cached briefly (a few seconds while live, minutes once final)."""
    moment = time.monotonic() if now is None else now
    key = (season, week, home, away)
    cached = _cache.get(key)
    if cached is not None:
        age = moment - cached[0]
        if age < (FINAL_SECONDS if cached[1].final else LIVE_SECONDS):
            return cached[1]
    result = FETCHER(season, week, home, away)
    _cache[key] = (moment, result)
    return result


def link_players(session: Session, box: BoxScore) -> BoxScore:
    """Fill in each row's Sleeper player id when his name and team match exactly one player."""
    found: dict[tuple[str, str], str | None] = {}
    for pid, name, nfl_team in session.execute(
        select(PlayerRow.player_id, PlayerRow.full_name, PlayerRow.team).where(
            PlayerRow.team.in_([box.home, box.away])
        )
    ):
        if not name or not nfl_team:
            continue
        key = (normalize_name(name), nfl_team)
        found[key] = None if key in found else pid  # two players with one name: no guess
    for team in box.teams:
        for table in team.tables:
            for row in table.rows:
                row.player_id = found.get((normalize_name(row.name), team.team))
    return box
