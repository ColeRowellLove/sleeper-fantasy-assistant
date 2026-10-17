"""Which Sleeper injury designations mean a player will not play, and which make it unlikely.

One list for the lineup view, start/sit, the depth chart and every alert, so they cannot disagree
about the same player.
"""

from __future__ import annotations

# ruled out, on a reserve list, suspended, not active or otherwise unavailable this week
WILL_NOT_PLAY = frozenset(
    {"Out", "IR", "Injured Reserve", "PUP", "Sus", "Suspended", "NA", "DNR", "COV"}
)
# a player listed Doubtful rarely plays, so no one starts or picks him up on hope
UNLIKELY_TO_PLAY = WILL_NOT_PLAY | {"Doubtful"}
