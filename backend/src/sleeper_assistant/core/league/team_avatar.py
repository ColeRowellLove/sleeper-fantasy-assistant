"""The picture a manager's team shows: the team's own image, else the manager's Sleeper avatar."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import RosterRow, SleeperUserRow, UserLeagueRow

_CDN = "https://sleepercdn.com/avatars/thumbs/"
_ALLOWED_PREFIXES = ("https://sleepercdn.com/", "https://sleeper.com/", "https://sleeper.app/")


def _cdn_url(avatar_id: str | None) -> str | None:
    return f"{_CDN}{avatar_id}" if avatar_id else None


def team_avatar_url(metadata: dict[str, Any] | None) -> str | None:
    """The team's own picture from the user's league metadata, when it is a Sleeper image URL.

    Other hosts are ignored so a manager cannot make every viewer's browser load a link of their
    choosing.
    """
    value = str((metadata or {}).get("avatar") or "").strip()
    return value if value.startswith(_ALLOWED_PREFIXES) else None


def avatar_id(user_avatar: object) -> str | None:
    """Sleeper's avatar id for a user, only when it looks like one (letters and digits)."""
    value = str(user_avatar or "").strip()
    return value if re.fullmatch(r"[A-Za-z0-9]+", value) else None


def team_avatars(session: Session, rosters: list[RosterRow]) -> dict[int, str | None]:
    """roster_id -> the image URL for that team, or None (the page then shows initials)."""
    owner_ids = {r.owner_id for r in rosters if r.owner_id}
    league_ids = {r.league_id for r in rosters}
    users = {
        u.user_id: u.avatar
        for u in session.scalars(
            select(SleeperUserRow).where(SleeperUserRow.user_id.in_(owner_ids))
        )
    }
    own = {
        link.user_id: link.team_avatar
        for link in session.scalars(
            select(UserLeagueRow).where(
                UserLeagueRow.user_id.in_(owner_ids), UserLeagueRow.league_id.in_(league_ids)
            )
        )
        if link.team_avatar
    }
    return {
        r.roster_id: own.get(r.owner_id or "") or _cdn_url(users.get(r.owner_id or ""))
        for r in rosters
    }
