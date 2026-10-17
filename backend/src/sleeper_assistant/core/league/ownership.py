"""Who owns whom in a league."""

from __future__ import annotations

from collections.abc import Iterable

from sleeper_assistant.db import RosterRow


def all_players(roster: RosterRow) -> list[str]:
    """Every player a team has, in any spot (starting, bench, injured reserve or taxi squad)."""
    return [*roster.players, *roster.reserve, *roster.taxi]


def roster_owners(rosters: Iterable[RosterRow]) -> dict[str, int]:
    """Player id -> the roster id that has him, for every rostered player of the league."""
    return {pid: r.roster_id for r in rosters for pid in all_players(r)}
