"""Words for numbers."""

from __future__ import annotations

_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}
_TEENS = range(11, 14)


def ordinal(n: int) -> str:
    """1 -> "1st", 2 -> "2nd", 3 -> "3rd", 11 -> "11th", 22 -> "22nd"."""
    if n % 100 in _TEENS:
        return f"{n}th"
    return f"{n}{_SUFFIXES.get(n % 10, 'th')}"
