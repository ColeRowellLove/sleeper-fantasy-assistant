"""Loading team depth charts into the database (ESPN first, Sleeper's chart as the fallback)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import PlayerRow, TeamDepthChartRow, utcnow
from sleeper_assistant.depth import (
    TEAM_IDS,
    Entry,
    RosterPlayer,
    attach_sleeper_ids,
    chart_from_sleeper,
    fetch_depth_chart,
)

log = logging.getLogger(__name__)


def _roster(session: Session) -> dict[str, list[RosterPlayer]]:
    """Every player with a team, grouped by team, with Sleeper's own depth chart fields."""
    by_team: dict[str, list[RosterPlayer]] = {}
    for p in session.scalars(select(PlayerRow).where(PlayerRow.team.is_not(None))):
        bio = p.bio or {}
        order = bio.get("depth_chart_order")
        by_team.setdefault(p.team or "", []).append(
            RosterPlayer(
                player_id=p.player_id,
                name=p.full_name,
                team=p.team,
                espn_id=str(p.external_ids["espn"]) if p.external_ids.get("espn") else None,
                depth_position=bio.get("depth_chart_position"),
                depth_order=int(order)
                if isinstance(order, int | str) and str(order).isdigit()
                else None,
            )
        )
    return by_team


def _json(chart: dict[str, dict[str, list[Entry]]]) -> dict[str, Any]:
    return {
        group: {
            slot: [
                {
                    "name": e.name,
                    "espn_id": e.espn_id,
                    "sleeper_id": e.sleeper_id,
                    "injury": e.injury,
                }
                for e in players
            ]
            for slot, players in slots.items()
        }
        for group, slots in chart.items()
    }


def _has_players(chart: dict[str, dict[str, list[Entry]]]) -> bool:
    return any(players for slots in chart.values() for players in slots.values())


def sync_depth_charts(session: Session, http: httpx.Client, teams: list[str] | None = None) -> int:
    """Refresh each team's chart. Returns how many teams were stored.

    A team whose ESPN request fails keeps its stored chart. A team with no stored chart falls back
    to Sleeper's depth chart fields, so a page is never empty because one source was down.
    """
    roster = _roster(session)
    existing = {row.team: row for row in session.scalars(select(TeamDepthChartRow))}
    stored = 0
    for team in teams or sorted(TEAM_IDS):
        source = "ESPN"
        try:
            chart = fetch_depth_chart(http, team)
        except (httpx.HTTPError, ValueError, KeyError):
            log.warning("could not load the %s depth chart from ESPN", team)
            chart = {}
        if not _has_players(chart):
            if team in existing and existing[team].source == "ESPN":
                continue  # keep the last good ESPN chart rather than downgrade it
            chart, source = chart_from_sleeper(roster.get(team, [])), "Sleeper"
            if not _has_players(chart):
                continue
        chart = attach_sleeper_ids(chart, team, roster.get(team, []))
        row = existing.get(team)
        if row is None:
            row = existing[team] = TeamDepthChartRow(team=team)
            session.add(row)
        row.source = source
        row.chart = _json(chart)
        row.fetched_at = utcnow()
        stored += 1
    session.commit()
    return stored
