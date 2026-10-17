"""The news board: recent headlines about players and teams, with who owns the players named."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import LeagueRow, NewsItemRow, PlayerRow, as_utc
from sleeper_assistant.player_names import player_name
from sleeper_assistant.rosters import league_rosters

LIMIT = 80
PLAYER_LIMIT = 10


class NewsPlayer(BaseModel):
    player_id: str
    name: str
    position: str | None = None
    team: str | None = None


class NewsEntryView(BaseModel):
    """A headline and where to read it; the article itself always stays at the source."""

    id: str
    source: str
    title: str
    link: str
    published_at: datetime | None = None
    players: list[NewsPlayer] = []
    teams: list[str] = []
    topics: list[str] = []
    roster_ids: list[int] = []  # league teams that roster a player named in the headline


class NewsView(BaseModel):
    league_id: str | None = None
    items: list[NewsEntryView]
    sources: list[str] = []


def _view(rows: list[NewsItemRow], session: Session, owners: dict[str, int]) -> list[NewsEntryView]:
    ids = {pid for row in rows for pid in row.player_ids}
    players = {
        p.player_id: p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(ids)))
    }
    out = []
    for row in rows:
        named = [players[pid] for pid in row.player_ids if pid in players]
        out.append(
            NewsEntryView(
                id=row.id, source=row.source, title=row.title, link=row.link,
                published_at=as_utc(row.published_at) if row.published_at else None,
                teams=row.teams, topics=row.topics,
                players=[
                    NewsPlayer(
                        player_id=p.player_id, name=player_name(p), position=p.position, team=p.team
                    )
                    for p in named
                ],
                roster_ids=sorted({owners[p.player_id] for p in named if p.player_id in owners}),
            )
        )  # fmt: skip
    return out


def _owners(session: Session, league: LeagueRow) -> dict[str, int]:
    return {
        pid: roster.roster_id
        for roster in league_rosters(session, league.league_id)
        for pid in [*roster.players, *roster.reserve, *roster.taxi]
    }


def build_news(session: Session, league: LeagueRow) -> NewsView:
    """The latest headlines, newest first, with the league teams that own the players named."""
    rows = list(
        session.scalars(
            select(NewsItemRow)
            .order_by(NewsItemRow.published_at.desc().nulls_last(), NewsItemRow.fetched_at.desc())
            .limit(LIMIT)
        )
    )
    items = _view(rows, session, _owners(session, league))
    return NewsView(
        league_id=league.league_id, items=items, sources=sorted({i.source for i in items})
    )


def player_news(session: Session, player_id: str) -> list[NewsEntryView]:
    """The latest headlines that name one player."""
    rows = [
        row
        for row in session.scalars(
            select(NewsItemRow)
            .order_by(NewsItemRow.published_at.desc().nulls_last())
            .limit(LIMIT * 3)
        )
        if player_id in row.player_ids
    ][:PLAYER_LIMIT]
    return _view(rows, session, {})
