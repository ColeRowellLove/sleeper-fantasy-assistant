"""Which Sleeper injury designations mean a player will not play, and which make it unlikely.

One list for the lineup view, start/sit, the depth chart and every alert, so they cannot disagree
about the same player.
"""

from __future__ import annotations

from sleeper_assistant.core.models.injury import InjuryInfo
from sleeper_assistant.db import PlayerRow

# ruled out, on a reserve list, suspended, not active or otherwise unavailable this week
WILL_NOT_PLAY = frozenset(
    {"Out", "IR", "Injured Reserve", "PUP", "Sus", "Suspended", "NA", "DNR", "COV"}
)
# a player listed Doubtful rarely plays, so no one starts or picks him up on hope
UNLIKELY_TO_PLAY = WILL_NOT_PLAY | {"Doubtful"}


# Designations that carry no information for a fantasy manager are hidden.
_HIDDEN_INJURY_STATUSES = {"", "NA"}


def injury_info(players: dict[str, PlayerRow], pid: str) -> InjuryInfo | None:
    p = players.get(pid)
    if p is None or not p.injury_status or p.injury_status in _HIDDEN_INJURY_STATUSES:
        return None
    return InjuryInfo(status=p.injury_status, body_part=p.injury_body_part or None)
