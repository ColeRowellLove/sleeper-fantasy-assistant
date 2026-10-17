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

from sleeper_assistant.constants import ESPN_SCOREBOARD_URL
from sleeper_assistant.core.sources.espn import normalize_name
from sleeper_assistant.db import PlayerRow
from sleeper_assistant.utils.parse import espn_team_code, string_list

log = logging.getLogger(__name__)

SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
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


def _row(entry: Any, width: int) -> BoxRow | None:
    athlete = entry.get("athlete") if isinstance(entry, dict) else None
    if not isinstance(athlete, dict):
        return None
    name = athlete.get("displayName") or athlete.get("shortName")
    stats = string_list(entry.get("stats"))
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
    labels = string_list(block.get("labels"))
    key = block.get("name")
    if not labels or not isinstance(key, str):
        return None
    rows = [r for e in block.get("athletes") or [] if (r := _row(e, len(labels))) is not None]
    if not rows:
        return None
    totals = string_list(block.get("totals"))
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
    box = payload.get("boxscore") if isinstance(payload, dict) else None
    players = box.get("players") if isinstance(box, dict) else None
    if not isinstance(players, list):
        raise BoxScoreError("the summary has no box score")
    by_team: dict[str, BoxTeam] = {}
    for side in players:
        team = side.get("team") if isinstance(side, dict) else None
        code = espn_team_code(team.get("abbreviation")) if isinstance(team, dict) else None
        if code is None:
            continue
        tables = []
        for block in side.get("statistics") or [] if isinstance(side, dict) else []:
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
    return BoxScore(home=home, away=away, final=_is_final(payload), teams=teams)


def _is_final(payload: Any) -> bool:
    """Whether ESPN says the game is over; anything unexpected counts as not over."""
    header = payload.get("header") if isinstance(payload, dict) else None
    competitions = header.get("competitions") if isinstance(header, dict) else None
    first = competitions[0] if isinstance(competitions, list) and competitions else None
    status = first.get("status") if isinstance(first, dict) else None
    kind = status.get("type") if isinstance(status, dict) else None
    return isinstance(kind, dict) and kind.get("state") == "post"


def find_event_id(scoreboard: Any, home: str, away: str) -> str | None:
    """The ESPN event id of the game between two teams in a scoreboard response."""
    for event in scoreboard.get("events") or [] if isinstance(scoreboard, dict) else []:
        try:
            sides = {
                c["homeAway"]: espn_team_code(c["team"]["abbreviation"])
                for c in event["competitions"][0]["competitors"]
            }
        except (KeyError, IndexError, TypeError):
            continue
        if sides.get("home") == home and sides.get("away") == away and event.get("id"):
            return str(event["id"])
    return None


_event_ids: dict[tuple[str, int, str, str], str] = {}  # a game's event id never changes


def fetch_box_score(season: str, week: int, home: str, away: str) -> BoxScore:
    """Find the game on ESPN's scoreboard for the week (once), then read its summary."""
    key = (season, week, home, away)
    try:
        with httpx.Client(timeout=TIMEOUT) as http:
            event_id = _event_ids.get(key)
            if event_id is None:
                board = http.get(
                    ESPN_SCOREBOARD_URL, params={"dates": season, "seasontype": 2, "week": week}
                )
                board.raise_for_status()
                event_id = find_event_id(board.json(), home, away)
                if event_id is None:
                    raise BoxScoreError("ESPN does not list this game")
                _event_ids[key] = event_id
            summary = http.get(SUMMARY_URL, params={"event": event_id})
            summary.raise_for_status()
            return parse_summary(summary.json(), home, away)
    except (httpx.HTTPError, ValueError) as error:
        raise BoxScoreError(f"ESPN could not be reached: {error}") from error
    except (AttributeError, KeyError, TypeError, IndexError) as error:
        log.warning("box score: ESPN's response had an unexpected shape: %r", error)
        raise BoxScoreError("ESPN's response was not in the expected shape") from error


# replaceable in tests, so no test ever touches the network
Fetcher = Callable[[str, int, str, str], BoxScore]
FETCHER: Fetcher = fetch_box_score
_cache: dict[tuple[str, int, str, str], tuple[float, BoxScore | None]] = {}
FAILURE_SECONDS = 10.0  # a failed lookup is not repeated for every viewer's refresh
MAX_ENTRIES = 200  # a season has fewer games than this; the cache never grows without bound


def reset_cache() -> None:
    _cache.clear()
    _event_ids.clear()


def box_score(season: str, week: int, home: str, away: str, now: float | None = None) -> BoxScore:
    """The box score, cached briefly (a few seconds while live, minutes once final).

    A failure is remembered for a few seconds too, so an ESPN outage does not turn every refresh
    into two more requests; the error is raised again until the entry expires.
    """
    moment = time.monotonic() if now is None else now
    key = (season, week, home, away)
    cached = _cache.get(key)
    if cached is not None:
        age = moment - cached[0]
        found = cached[1]
        if found is None and age < FAILURE_SECONDS:
            raise BoxScoreError("ESPN had no box score a moment ago")
        if found is not None and age < (FINAL_SECONDS if found.final else LIVE_SECONDS):
            return found
    if len(_cache) >= MAX_ENTRIES:
        _cache.clear()
    try:
        result = FETCHER(season, week, home, away)
    except BoxScoreError:
        _cache[key] = (moment, None)
        raise
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
