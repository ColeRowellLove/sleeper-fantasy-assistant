"""Sync a Sleeper league (and the shared player DB) into the database."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    PlayerRow,
    RawSnapshotRow,
    RosterRow,
    SleeperUserRow,
    TransactionRow,
    UserLeagueRow,
    utcnow,
)
from sleeper_assistant.sleeper import SleeperClient, SleeperPlayer

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
            session.merge(UserLeagueRow(user_id=user.user_id, league_id=league_id))
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
                    wins=int(rs.get("wins", 0)),
                    losses=int(rs.get("losses", 0)),
                    ties=int(rs.get("ties", 0)),
                    points_for=float(rs.get("fpts", 0)) + float(rs.get("fpts_decimal", 0)) / 100,
                    points_against=float(rs.get("fpts_against", 0))
                    + float(rs.get("fpts_against_decimal", 0)) / 100,
                )
            )

        for week in _weeks_to_sync(client, league.season):
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
                    )
                )
            for t in client.get_transactions(league_id, week):
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
        external_ids={k: v for k, v in external.items() if v is not None},
    )


def sync_players(session: Session, client: SleeperClient) -> int:
    """Upsert the shared Sleeper player DB. Returns the number of players synced."""
    players = client.get_players()
    for p in players:
        session.merge(_player_row(p))
    session.commit()
    return len(players)
