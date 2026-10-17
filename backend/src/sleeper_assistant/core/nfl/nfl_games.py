"""One NFL week's games as the app shows them: state, score, clock and conditions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import GAME_COMPLETE, GAME_LIVE, GAME_PRE
from sleeper_assistant.core.models.games import GameConditions, GameInfo, GameState
from sleeper_assistant.core.sources.live import LiveGame, current_games, describe, fraction_elapsed
from sleeper_assistant.core.sources.live import window_open as live_window_open
from sleeper_assistant.db import (
    NflGameRow,
)
from sleeper_assistant.utils.clock import utc_iso

# Sleeper schedule statuses -> what we show. Unknown statuses show nothing rather than a guess.
_STATUS_STATE: dict[str, GameState] = {
    GAME_PRE: "upcoming",
    GAME_LIVE: "live",
    GAME_COMPLETE: "final",
}


def current_week(session: Session, season: str) -> int | None:
    """The first week not yet fully played; the last week once the season is over.

    A week followed by a fully completed later week is treated as done even if one of its games
    never reached 'complete' (for example a postponed game), so it cannot pin the app to a week.
    """
    rows = session.execute(
        select(NflGameRow.week, NflGameRow.status).where(NflGameRow.season == season)
    ).all()
    if not rows:
        return None
    weeks = sorted({week for week, _ in rows})
    fully_complete = {w for w in weeks if all(s == GAME_COMPLETE for wk, s in rows if wk == w)}
    last_complete = max(fully_complete, default=0)
    for week in weeks:
        if week > last_complete:
            return week
    return weeks[-1]


def _live_games(week_games: list[NflGameRow], week: int) -> dict[tuple[str, str], LiveGame]:
    """ESPN's live status for this week's games, only while a game could be on (else empty)."""
    in_progress = any(g.status == GAME_LIVE for g in week_games)
    if not live_window_open([g.kickoff for g in week_games], in_progress):
        return {}
    return {(g.home, g.away): g for g in current_games() if g.week in (None, week)}


def _conditions(g: NflGameRow) -> tuple[GameConditions | None, GameConditions | None]:
    """(home side, away side) conditions of a game; None when nothing is known."""
    if all(
        v is None
        for v in (g.roof, g.surface, g.stadium, g.temp, g.wind, g.spread_line, g.total_line)
    ):
        return None, None
    common = {
        "roof": g.roof, "surface": g.surface, "stadium": g.stadium, "temp": g.temp,
        "wind": g.wind, "total": g.total_line,
    }  # fmt: skip
    home_spread = None if g.spread_line is None else -g.spread_line
    away_spread = g.spread_line
    return (
        GameConditions(**common, spread=home_spread),
        GameConditions(**common, spread=away_spread),
    )


def games_for_week(session: Session, season: str, week: int) -> dict[str, GameInfo]:
    """NFL team -> that team's game in the week; teams with no game in the week are on a bye."""
    games = list(session.scalars(select(NflGameRow).where(NflGameRow.season == season)))
    all_teams = {g.home for g in games} | {g.away for g in games}
    week_games = [g for g in games if g.week == week]
    playing = {g.home for g in week_games} | {g.away for g in week_games}
    live_by_game = _live_games(week_games, week)
    out: dict[str, GameInfo] = {}
    for g in week_games:
        state = _STATUS_STATE.get(g.status)
        if state is None:
            continue
        kickoff = utc_iso(g.kickoff)
        live = live_by_game.get((g.home, g.away))
        game_state = live.state if live else state  # ESPN is fresher than Sleeper's schedule
        home_score, away_score = (
            (live.home_score, live.away_score) if live else (g.home_score, g.away_score)
        )
        if game_state == "upcoming":
            home_score = away_score = None
        words = describe(live) if live else ("Final" if game_state == "final" else None)
        played = {"upcoming": 0.0, "final": 1.0}.get(game_state)
        if live is not None and game_state == "live":
            played = fraction_elapsed(live)
        home_cond, away_cond = _conditions(g)
        situation = live.situation if live and game_state == "live" else None
        out[g.home] = GameInfo(
            state=game_state, date=g.game_date, kickoff=kickoff, opponent=g.away, home=True,
            team=g.home, team_score=home_score, opponent_score=away_score, period_text=words,
            elapsed=played, conditions=home_cond, situation=situation,
        )  # fmt: skip
        out[g.away] = GameInfo(
            state=game_state, date=g.game_date, kickoff=kickoff, opponent=g.home, home=False,
            team=g.away, team_score=away_score, opponent_score=home_score, period_text=words,
            elapsed=played, conditions=away_cond, situation=situation,
        )  # fmt: skip
    if week_games:  # without any games in the week we cannot tell a bye from missing data
        for team in all_teams - playing:
            out[team] = GameInfo(state="bye")
    return out
