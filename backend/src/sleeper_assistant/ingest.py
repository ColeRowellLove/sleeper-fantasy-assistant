"""Sync a Sleeper league (and the shared player DB) into the database."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sleeper_assistant.crosswalk import build_crosswalk
from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerRow,
    RawSnapshotRow,
    RosterRow,
    SleeperUserRow,
    TransactionRow,
    UserLeagueRow,
    utcnow,
)
from sleeper_assistant.sleeper import SleeperClient, SleeperPlayer

log = logging.getLogger(__name__)

MAX_WEEKS = 18
_SKIP_SNAPSHOT_PREFIXES = ("/players/",)  # ~5 MB; the parsed rows are enough


def _snapshot_recorder(session: Session) -> Callable[[str, Any], None]:
    def record(path: str, data: Any) -> None:
        if path.startswith(_SKIP_SNAPSHOT_PREFIXES):
            return
        session.add(RawSnapshotRow(source="sleeper", key=path, payload={"data": data}))

    return record


def _weeks_to_sync(client: SleeperClient, season: str) -> range:
    state = client.get_state()
    if state.season != season:
        return range(1, MAX_WEEKS + 1)  # past season: everything is final
    if state.season_type == "regular":
        return range(1, min(state.week, MAX_WEEKS) + 1)
    if state.season_type == "post":
        return range(1, MAX_WEEKS + 1)
    return range(0)


def _regular_season_weeks(settings: dict[str, Any]) -> range:
    """Weeks before the playoffs start (all weeks when the league has no playoff week set)."""
    start = settings.get("playoff_week_start")
    last = start - 1 if isinstance(start, int) and start > 1 else MAX_WEEKS
    return range(1, min(last, MAX_WEEKS) + 1)


def _streak(metadata: dict[str, Any] | None) -> str | None:
    """Sleeper's "3W" / "2L" / "1T" streak, or None when it is missing or unrecognisable."""
    value = (metadata or {}).get("streak")
    if isinstance(value, str) and re.fullmatch(r"\d{1,2}[WLT]", value):
        return value
    return None


def sync_league(session: Session, client: SleeperClient, league_id: str) -> LeagueRow:
    """Fetch and upsert league settings, users, rosters, matchups and transactions."""
    client = client.with_recorder(
        _snapshot_recorder(session)
    )  # per-sync; never mutate the shared client
    try:
        league = client.get_league(league_id)
        existing = session.get(LeagueRow, league_id)
        row = session.merge(
            LeagueRow(
                league_id=league.league_id,
                name=league.name,
                season=league.season,
                total_rosters=league.total_rosters,
                scoring_settings=league.scoring_settings,
                roster_positions=league.roster_positions,
                settings=league.settings,
                previous_league_id=league.previous_league_id,
                last_synced_at=utcnow(),
                last_viewed_at=existing.last_viewed_at if existing else None,
            )
        )

        for user in client.get_league_users(league_id):
            session.merge(
                SleeperUserRow(
                    user_id=user.user_id, username=user.username, display_name=user.display_name
                )
            )
            team_name = str((user.metadata or {}).get("team_name") or "").strip() or None
            session.merge(
                UserLeagueRow(user_id=user.user_id, league_id=league_id, team_name=team_name)
            )
        session.flush()

        for roster in client.get_rosters(league_id):
            rs = roster.settings
            session.merge(
                RosterRow(
                    league_id=league_id,
                    roster_id=roster.roster_id,
                    owner_id=roster.owner_id,
                    players=roster.players or [],
                    starters=roster.starters or [],
                    reserve=roster.reserve or [],
                    taxi=roster.taxi or [],
                    wins=int(rs.get("wins", 0)),
                    losses=int(rs.get("losses", 0)),
                    ties=int(rs.get("ties", 0)),
                    points_for=float(rs.get("fpts", 0)) + float(rs.get("fpts_decimal", 0)) / 100,
                    points_against=float(rs.get("fpts_against", 0))
                    + float(rs.get("fpts_against_decimal", 0)) / 100,
                    streak=_streak(roster.metadata),
                    potential_points=_potential(rs),
                )
            )

        played_weeks = set(_weeks_to_sync(client, league.season))
        # Sleeper also returns future pairings (with each team's current starters and 0 points),
        # so sync every regular-season week to be able to show upcoming opponents.
        for week in sorted(played_weeks | set(_regular_season_weeks(league.settings))):
            for m in client.get_matchups(league_id, week):
                session.merge(
                    MatchupRow(
                        league_id=league_id,
                        week=week,
                        roster_id=m.roster_id,
                        matchup_id=m.matchup_id,
                        points=m.points,
                        starters=m.starters or [],
                        starters_points=m.starters_points or [],
                        players=m.players or [],
                        players_points=m.players_points or {},
                    )
                )
            for t in client.get_transactions(league_id, week) if week in played_weeks else []:
                session.merge(
                    TransactionRow(
                        league_id=league_id,
                        transaction_id=t.transaction_id,
                        type=t.type,
                        status=t.status,
                        week=t.leg,
                        created_ms=t.created,
                        payload=t.model_dump(),
                    )
                )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return row


def _potential(settings: dict[str, Any]) -> float | None:
    """Sleeper's potential points (``ppts``): what the best lineups would score; None if absent."""
    if "ppts" not in settings:
        return None
    return float(settings["ppts"]) + float(settings.get("ppts_decimal", 0)) / 100


def _bio(p: SleeperPlayer) -> dict[str, Any] | None:
    """The pop-up's bio fields that Sleeper actually has for this player."""
    bio = {
        "age": p.age,
        "birth_date": p.birth_date,
        "height": p.height,
        "weight": p.weight,
        "college": p.college,
        "years_exp": p.years_exp,
        "number": p.number,
        "depth_chart_position": p.depth_chart_position,
        "depth_chart_order": p.depth_chart_order,
    }
    present = {k: v for k, v in bio.items() if v not in (None, "")}
    return present or None


def _player_row(p: SleeperPlayer) -> PlayerRow:
    external = {
        "gsis": p.gsis_id,
        "espn": p.espn_id,
        "yahoo": p.yahoo_id,
        "sportradar": p.sportradar_id,
        "rotowire": p.rotowire_id,
        "fantasy_data": p.fantasy_data_id,
        "stats": p.stats_id,
    }
    return PlayerRow(
        player_id=p.player_id,
        full_name=p.full_name,
        position=p.position,
        team=p.team,
        status=p.status,
        injury_status=p.injury_status,
        injury_body_part=p.injury_body_part,
        external_ids={k: v for k, v in external.items() if v is not None},
        bio=_bio(p),
    )


def sync_players(session: Session, client: SleeperClient) -> int:
    """Upsert the shared Sleeper player DB. Returns the number of players synced."""
    players = client.get_players()
    # One query for existing rows, then update in memory / bulk insert. A merge() per player
    # costs ~11k SELECT round trips, which is minutes against a remote database.
    existing = {row.player_id: row for row in session.scalars(select(PlayerRow))}
    for p in players:
        new = _player_row(p)
        row = existing.get(p.player_id)
        if row is None:
            session.add(new)
            continue
        row.full_name = new.full_name
        row.position = new.position
        row.team = new.team
        row.status = new.status
        row.injury_status = new.injury_status
        row.injury_body_part = new.injury_body_part
        row.external_ids = new.external_ids
        row.bio = new.bio
    session.commit()
    return len(players)


def sync_schedule(session: Session, client: SleeperClient, season: str) -> int:
    """Upsert the season's games (dates and statuses). Returns the number of games synced."""
    games = client.get_schedule(season)
    existing = {row.game_id: row for row in session.scalars(select(NflGameRow))}
    now = utcnow()
    for g in games:
        row = existing.get(g.game_id)
        if row is None:
            row = NflGameRow(game_id=g.game_id, season=season)
            session.add(row)
        row.week = g.week
        row.home = g.home
        row.away = g.away
        row.game_date = g.date
        row.status = g.status
        row.updated_at = now
    session.commit()
    return len(games)


def ensure_schedule(session: Session, sleeper: SleeperClient, season: str) -> None:
    """Load the season schedule the first time (one small request) so bye weeks and game state show.

    The worker refreshes it afterwards; a failure here must not block connecting.
    """
    has_games = session.scalar(
        select(func.count()).select_from(NflGameRow).where(NflGameRow.season == season)
    )
    if has_games:
        return
    try:
        sync_schedule(session, sleeper, season)
    except IntegrityError:  # a concurrent first connect loaded the schedule; that is fine
        session.rollback()
    except (httpx.HTTPError, ValidationError):
        session.rollback()
        log.exception("could not load the NFL schedule; bye weeks and game state will be missing")


def ensure_players(session: Session, sleeper: SleeperClient) -> None:
    """Load Sleeper's player DB (~5 MB) the first time, so rosters show names, not ids.

    After that the worker refreshes it daily; a failure here must not block connecting.
    """
    if (session.scalar(select(func.count()).select_from(PlayerRow)) or 0) > 0:
        return
    try:
        sync_players(session, sleeper)
        build_crosswalk(session)
    except IntegrityError:  # a concurrent first connect loaded the players; that is fine
        session.rollback()
    except (httpx.HTTPError, ValidationError):
        session.rollback()
        log.exception("could not load the Sleeper player database; names will show as ids")
