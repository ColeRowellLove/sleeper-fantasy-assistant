"""Keep the fantasy-relevant headlines: match each one to the players and teams it names."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import timedelta

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import PLAYER_POSITIONS
from sleeper_assistant.core.nfl.nfl_teams import NICKNAMES
from sleeper_assistant.core.sources.espn import normalize_name
from sleeper_assistant.core.sources.news_feed import NewsEntry, configured_feeds, fetch_feed
from sleeper_assistant.db import NewsItemRow, PlayerRow, RawSnapshotRow, utcnow

log = logging.getLogger(__name__)

KEEP = timedelta(days=14)  # older headlines are deleted
SNAPSHOT_KEEP = timedelta(days=2)  # raw lists are only for debugging a parse problem
MAX_NAME_WORDS = 4
TOPICS: dict[str, re.Pattern[str]] = {
    "injury": re.compile(
        r"\b(injur\w*|questionable|doubtful|ruled out|out for|inactive|hamstring|concussion)\b",
        re.I,
    ),
    "depth": re.compile(r"\b(depth chart|starter|benched|promoted|activated)\b", re.I),
    "trade": re.compile(r"\b(trade[sd]?|acquire[sd]?)\b", re.I),
    "waivers": re.compile(r"\b(waive[sd]?|released|signed|signs with|cut by)\b", re.I),
}


def _words(title: str) -> list[str]:
    return normalize_name(title).split()


def name_index(session: Session) -> dict[str, str]:
    """Normalised player name -> Sleeper id, for names that belong to exactly one fantasy player."""
    seen: dict[str, str | None] = {}
    for pid, name, position in session.execute(
        select(PlayerRow.player_id, PlayerRow.full_name, PlayerRow.position).where(
            PlayerRow.team.is_not(None)
        )
    ):
        if not name or position not in PLAYER_POSITIONS:
            continue
        key = normalize_name(name)
        if len(key.split()) < 2:  # noqa: PLR2004 - a single word names nobody reliably
            continue
        seen[key] = None if key in seen else pid  # a name two players share is not guessed
    return {k: v for k, v in seen.items() if v is not None}


def match_entry(title: str, index: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """(player ids, team codes, topics) a headline is about."""
    words = _words(title)
    players: list[str] = []
    for size in range(MAX_NAME_WORDS, 1, -1):
        for i in range(len(words) - size + 1):
            pid = index.get(" ".join(words[i : i + size]))
            if pid and pid not in players:
                players.append(pid)
    teams = [
        code
        for code, nick in NICKNAMES.items()
        if re.search(rf"\b{re.escape(nick)}\b", title, re.I)
    ]
    topics = [name for name, pattern in TOPICS.items() if pattern.search(title)]
    return players, teams, topics


def _id(link: str) -> str:
    return hashlib.sha1(link.encode()).hexdigest()


def store_entries(session: Session, entries: list[NewsEntry], index: dict[str, str]) -> int:
    """Store the entries that name a player or a team (others are not fantasy news); new count."""
    stored = 0
    now = utcnow()
    for entry in entries:
        players, teams, topics = match_entry(entry.title, index)
        if not players and not teams:
            continue
        row = session.get(NewsItemRow, _id(entry.link))
        if row is not None:  # a publisher can edit a headline; keep what we show current
            row.title, row.teams, row.player_ids, row.topics = entry.title, teams, players, topics
        else:
            session.add(
                NewsItemRow(
                    id=_id(entry.link), source=entry.source, title=entry.title, link=entry.link,
                    published_at=entry.published, fetched_at=now, teams=teams,
                    player_ids=players, topics=topics,
                )
            )  # fmt: skip
            stored += 1
    return stored


def sync_news(session: Session, http: httpx.Client) -> int:
    """Read every configured feed; one failing feed never stops the others (it is logged).

    Returns how many new headlines were stored. Raises only when *every* feed failed, so the job
    queue shows it and the previous headlines stay.
    """
    index = name_index(session)
    feeds = configured_feeds()
    stored = 0
    failures: list[str] = []
    for source, url in feeds:
        try:
            entries = fetch_feed(http, source, url)
        except (httpx.HTTPError, ValueError) as error:
            log.warning("news feed %s failed: %s", source, error)
            failures.append(f"{source}: {error}")
            continue
        session.add(
            RawSnapshotRow(
                source="news", key=source,
                payload={"entries": [[e.title, e.link] for e in entries[:200]]},
            )
        )  # fmt: skip
        stored += store_entries(session, entries, index)
    session.execute(delete(NewsItemRow).where(NewsItemRow.fetched_at < utcnow() - KEEP))
    session.execute(
        delete(RawSnapshotRow).where(
            RawSnapshotRow.source == "news", RawSnapshotRow.fetched_at < utcnow() - SNAPSHOT_KEEP
        )
    )
    session.commit()
    if feeds and len(failures) == len(feeds):
        raise RuntimeError("every news feed failed: " + "; ".join(failures))
    return stored
