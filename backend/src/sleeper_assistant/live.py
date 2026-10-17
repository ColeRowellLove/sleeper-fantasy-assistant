"""Live game status from ESPN's public scoreboard: score, quarter and clock.

Sleeper's schedule only says whether a game has not started, is in progress or is over, and the
worker refreshes it every 10 to 25 minutes. ESPN's scoreboard (no key, one small request for the
whole week) adds the score and the game clock and is fresh to the minute. It is unofficial, so a
failed or changed response must never break a page: callers fall back to Sleeper's state.

The scoreboard is only requested while a game could be on (a short window around kickoffs), and the
answer is cached for a few seconds in the running process, so many viewers cause one request.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from sleeper_assistant.constants import ESPN_SCOREBOARD_URL
from sleeper_assistant.utils.parse import clean_text, espn_team_code, int_or_none

log = logging.getLogger(__name__)

CACHE_SECONDS = 15.0  # a viewer sees a score at most this old (only asked for during live windows)
STALE_SECONDS = 600.0  # if ESPN is down, a score this old is still better than none
WINDOW_BEFORE = timedelta(hours=1)  # start looking this long before a kickoff
WINDOW_AFTER = timedelta(hours=5)  # a game is over well within this long after kickoff

# ESPN's team codes where they differ from Sleeper's
_STATES: dict[str, Literal["upcoming", "live", "final"]] = {
    "pre": "upcoming",
    "in": "live",
    "post": "final",
}


class Situation(BaseModel):
    """Who has the ball and where, for a game in progress."""

    possession: str | None = None  # the team code with the ball
    down_distance: str | None = None  # "1st & 10"
    ball_on: str | None = None  # "DEN 35": the yard line and the side of the field
    red_zone: bool = False  # the offense is inside the opponent's 20


class LiveGame(BaseModel):
    week: int | None
    home: str
    away: str
    state: Literal["upcoming", "live", "final"]
    period: int | None = None
    clock: str | None = None
    detail: str | None = None  # ESPN's short text: "2:24 - 2nd", "Halftime", "Final", "Final/OT"
    home_score: int | None = None
    away_score: int | None = None
    situation: Situation | None = None  # only while the game is live and ESPN reports it


def _between_plays(detail: Any) -> bool:
    """Halftime and the end of a quarter: ESPN may leave the last possession in place."""
    return isinstance(detail, str) and any(word in detail.lower() for word in ("half", "end"))


def parse_situation(competition: dict[str, Any], sides: dict[str, Any]) -> Situation | None:
    """The ball, down and red zone from a live competition's ``situation`` block.

    The key names are ESPN's (``possession`` is a team id, ``shortDownDistanceText``,
    ``possessionText``, ``isRedZone``) but the block is undocumented and was not checked against a
    live game when this was written, so every part is read defensively: a missing or oddly typed key
    is simply left out, and a block with nothing usable gives None.
    """
    block = competition.get("situation")
    if not isinstance(block, dict):
        return None
    by_id: dict[str, str] = {}  # ESPN team id -> team code
    for side in sides.values():
        team = side.get("team") if isinstance(side, dict) else None
        code = espn_team_code(team.get("abbreviation")) if isinstance(team, dict) else None
        if code and isinstance(team, dict) and team.get("id") is not None:
            by_id[str(team["id"])] = code
    codes = set(by_id.values())
    ball_on = clean_text(block.get("possessionText"))
    possession = by_id.get(str(block.get("possession")))
    if ball_on:
        side, _, rest = ball_on.partition(" ")
        ball_code = espn_team_code(side)
        if ball_code in codes:  # "WSH 35" is written with the codes the rest of the app uses
            ball_on = f"{ball_code} {rest}".strip()
    down = clean_text(block.get("shortDownDistanceText")) or clean_text(
        block.get("downDistanceText")
    )
    red_zone = block.get("isRedZone") is True
    if possession is None and down is None and ball_on is None and not red_zone:
        if (
            block
        ):  # ESPN sent a situation but nothing in it was readable: the shape may have changed
            log.warning("could not read the ESPN situation block: keys %s", sorted(block))
        return None
    return Situation(possession=possession, down_distance=down, ball_on=ball_on, red_zone=red_zone)


def parse_scoreboard(payload: Any) -> list[LiveGame]:
    """Every game in an ESPN scoreboard response with two known teams and a known state."""
    if not isinstance(payload, dict):
        return []
    week = payload.get("week", {}).get("number") if isinstance(payload.get("week"), dict) else None
    events = payload.get("events")
    if not isinstance(events, list):
        return []
    games: list[LiveGame] = []
    for event in events:
        try:
            competition = event["competitions"][0]
            status = event["status"]
            state = _STATES.get(status["type"]["state"])
            sides = {c["homeAway"]: c for c in competition["competitors"]}
            home, away = (
                espn_team_code(sides["home"]["team"]["abbreviation"]),
                espn_team_code(sides["away"]["team"]["abbreviation"]),
            )
        except (KeyError, IndexError, TypeError):
            continue
        if state is None or home is None or away is None:
            continue
        period = status.get("period")
        clock = status.get("displayClock")
        detail = status["type"].get("shortDetail")
        games.append(
            LiveGame(
                week=week if isinstance(week, int) else None,
                home=home,
                away=away,
                state=state,
                period=period if isinstance(period, int) and period > 0 else None,
                clock=clock if isinstance(clock, str) and state == "live" else None,
                detail=detail if isinstance(detail, str) else None,
                home_score=int_or_none(sides["home"].get("score")),
                away_score=int_or_none(sides["away"].get("score")),
                situation=parse_situation(competition, sides)
                if state == "live" and not _between_plays(detail)
                else None,
            )
        )
    return games


def fetch_scoreboard() -> list[LiveGame]:
    """One request for the current week's whole slate."""
    with httpx.Client(timeout=5.0) as http:
        response = http.get(ESPN_SCOREBOARD_URL)
        response.raise_for_status()
        return parse_scoreboard(response.json())


# replaceable in tests, so no test ever touches the network
Fetcher = Callable[[], list[LiveGame]]
FETCHER: Fetcher = fetch_scoreboard
_cache: tuple[float, list[LiveGame]] | None = None


def reset_cache() -> None:
    global _cache  # noqa: PLW0603 - a module-level cache is the point
    _cache = None


def current_games(now: float | None = None) -> list[LiveGame]:
    """The scoreboard, cached for under a minute; empty if ESPN is unavailable."""
    global _cache  # noqa: PLW0603
    moment = time.monotonic() if now is None else now
    if _cache is not None and moment - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    try:
        games = FETCHER()
    except (httpx.HTTPError, ValueError):
        log.warning("could not load the ESPN scoreboard")
        if _cache is not None and moment - _cache[0] < STALE_SECONDS:
            return _cache[1]  # an older score beats no score while ESPN is down
        return []
    _cache = (moment, games)
    return games


def window_open(
    kickoffs: list[datetime | None], in_progress: bool, now: datetime | None = None
) -> bool:
    """Whether a game could be on now: one is in progress per Sleeper, or one kicked off lately."""
    if in_progress:
        return True
    moment = now or datetime.now(UTC)
    for kickoff in kickoffs:
        if kickoff is None:
            continue
        start = kickoff if kickoff.tzinfo else kickoff.replace(tzinfo=UTC)
        if start - WINDOW_BEFORE <= moment <= start + WINDOW_AFTER:
            return True
    return False


_REGULATION_SECONDS = 3600.0  # four 15-minute quarters
_QUARTER_SECONDS = 900.0


def _clock_seconds(clock: str | None) -> float | None:
    """ "2:24" is 144 seconds; anything that is not minutes:seconds is None."""
    if not clock or ":" not in clock:
        return None
    minutes, _, seconds = clock.partition(":")
    try:
        return int(minutes) * 60.0 + float(seconds)
    except ValueError:
        return None


def fraction_elapsed(game: LiveGame) -> float | None:  # noqa: PLR0911 - one early exit per state
    """The share of a game played, 0 to 1: from the quarter and clock; None when it is unknown."""
    if game.state == "final":
        return 1.0
    if game.state == "upcoming":
        return 0.0
    if game.detail and "half" in game.detail.lower():
        return 0.5
    if game.period is None:
        return None
    if game.period > 4:  # noqa: PLR2004 - overtime: the regulation game is over
        return 1.0
    left = _clock_seconds(game.clock)
    if left is None:
        return None
    left = min(max(left, 0.0), _QUARTER_SECONDS)
    return ((game.period - 1) * _QUARTER_SECONDS + (_QUARTER_SECONDS - left)) / _REGULATION_SECONDS


def describe(game: LiveGame) -> str | None:
    """A short plain phrase for where the game is: "Q2 2:24", "Halftime", "Final", "Final, OT"."""
    if game.state == "final":
        return "Final" if not game.detail or "OT" not in game.detail else "Final, OT"
    if game.state != "live":
        return None
    if game.detail and "half" in game.detail.lower():
        return "Halftime"
    if game.detail and "end" in game.detail.lower():
        return game.detail.strip()
    if game.period is None:
        return "In progress"
    name = f"Q{game.period}" if game.period <= 4 else "OT"  # noqa: PLR2004 - four quarters
    return f"{name} {game.clock}" if game.clock else name
