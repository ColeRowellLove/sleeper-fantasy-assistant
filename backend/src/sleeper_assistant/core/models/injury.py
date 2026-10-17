"""A player's injury designation as the app shows it."""

from __future__ import annotations

from pydantic import BaseModel


class InjuryInfo(BaseModel):
    """Injury designation from Sleeper (Out, Doubtful, Questionable, IR, PUP, ...)."""

    status: str
    body_part: str | None = None
