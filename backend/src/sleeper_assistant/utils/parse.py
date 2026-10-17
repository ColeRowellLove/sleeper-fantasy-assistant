"""Reading values from untrusted JSON (ESPN, Sleeper): never raises, returns None when unusable."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from sleeper_assistant.constants import ESPN_TEAM_CODES


def finite_number(value: object) -> float | None:
    """A finite float for a number (or numeric text like "0"), else None; never raises."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def finite_numbers(stats: Mapping[str, object]) -> dict[str, float]:
    """The finite numbers of a stat line; a null or non-numeric value is dropped."""
    cleaned = ((k, finite_number(v)) for k, v in stats.items())
    return {k: n for k, n in cleaned if n is not None}


def int_or_none(value: Any) -> int | None:
    """An int for a number or numeric text, else None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_text(value: Any) -> str | None:
    """A stripped string, or None for anything that is not text or is blank."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def rounded_percent(value: Any) -> float | None:
    """A share rounded to two places, or None when it is not a plain number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return round(float(value), 2)


def string_list(values: Any) -> list[str]:
    """Every item of a list as text, or an empty list when it is not a list."""
    return [str(v) for v in values] if isinstance(values, list) else []


def espn_team_code(value: Any) -> str | None:
    """A team code in Sleeper's spelling (ESPN writes WSH for WAS), or None when not a code."""
    if not isinstance(value, str) or not value:
        return None
    return ESPN_TEAM_CODES.get(value, value)
