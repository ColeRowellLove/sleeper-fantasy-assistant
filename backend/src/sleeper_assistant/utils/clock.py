"""Times: the app stores UTC, SQLite returns it without a zone."""

from __future__ import annotations

from datetime import datetime

from sleeper_assistant.db import as_utc


def utc_iso(moment: datetime | None) -> str | None:
    """An ISO timestamp ending in Z (what the site expects), or None without a moment."""
    if moment is None:
        return None
    return as_utc(moment).isoformat().replace("+00:00", "Z")
