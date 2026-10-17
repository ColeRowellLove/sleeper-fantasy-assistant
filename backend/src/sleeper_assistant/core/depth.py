"""NFL team depth charts: offense, defense and special teams.

ESPN's public depth chart endpoint is the main source: it lists every slot (including the offensive
line, the defensive scheme's positions and the returners, holder and long snapper) with the players
in depth order. Sleeper's own depth chart fields are the fallback when ESPN is down or has no chart
for a team. Both are unofficial, so everything parsed here is treated as untrusted input.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, NamedTuple

import httpx

from sleeper_assistant.sources.espn import TEAMS, normalize_name

TEAM_IDS = {abbr: espn_id for espn_id, abbr in TEAMS.items()}
DEPTH_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts"

GROUPS = ("offense", "defense", "special")

# the slots each group contains, in reading order, with a plain-language label
_OFFENSE = {
    "qb": "Quarterback", "rb": "Running back", "fb": "Fullback", "wr1": "Wide receiver 1",
    "wr2": "Wide receiver 2", "wr3": "Wide receiver 3", "te": "Tight end", "lt": "Left tackle",
    "lg": "Left guard", "c": "Center", "rg": "Right guard", "rt": "Right tackle",
}  # fmt: skip
_DEFENSE = {
    "lde": "Left defensive end", "ldt": "Left defensive tackle", "nt": "Nose tackle",
    "rdt": "Right defensive tackle", "rde": "Right defensive end", "wlb": "Weak-side linebacker",
    "mlb": "Middle linebacker", "slb": "Strong-side linebacker", "lilb": "Left inside linebacker",
    "rilb": "Right inside linebacker", "lolb": "Left outside linebacker",
    "rolb": "Right outside linebacker", "lcb": "Left cornerback", "rcb": "Right cornerback",
    "nb": "Nickel back", "ss": "Strong safety", "fs": "Free safety",
}  # fmt: skip
_SPECIAL = {
    "pk": "Kicker", "p": "Punter", "h": "Holder", "ls": "Long snapper", "pr": "Punt returner",
    "kr": "Kick returner",
}  # fmt: skip
LABELS = {"offense": _OFFENSE, "defense": _DEFENSE, "special": _SPECIAL}
_GROUP_OF = {slot: group for group, slots in LABELS.items() for slot in slots}

# the fantasy-relevant slots, shown first
SKILL_SLOTS = ("qb", "rb", "fb", "wr1", "wr2", "wr3", "te")


class Entry(NamedTuple):
    """One player in a slot. ``sleeper_id`` is filled in once the player is matched."""

    espn_id: str | None
    name: str
    injury: str | None = None  # ESPN's status text when it has one
    sleeper_id: str | None = None


def _injury_text(athlete: dict[str, Any]) -> str | None:
    injuries = athlete.get("injuries")
    if isinstance(injuries, list) and injuries and isinstance(injuries[0], dict):
        status = injuries[0].get("status")
        if isinstance(status, str) and status:
            return status
    return None


def parse_depth_chart(payload: Any) -> dict[str, dict[str, list[Entry]]]:
    """group -> slot -> players in depth order, from one team's ESPN response.

    A team can have several formations (two offensive looks, a 3-4 and a nickel defense). The first
    formation that lists a slot wins, so a slot is never listed twice. Unknown slots are kept under
    the group of the formation they came from.
    """
    formations = payload.get("depthchart") if isinstance(payload, dict) else None
    out: dict[str, dict[str, list[Entry]]] = {group: {} for group in GROUPS}
    if not isinstance(formations, list):
        return out
    for formation in formations:
        if not isinstance(formation, dict) or not isinstance(formation.get("positions"), dict):
            continue
        fallback = "special" if formation.get("name") == "Special Teams" else "offense"
        for slot, entry in formation["positions"].items():
            athletes = entry.get("athletes") if isinstance(entry, dict) else None
            if not isinstance(athletes, list):
                continue
            group = _GROUP_OF.get(slot, fallback)
            if slot in out[group]:
                continue
            players = [
                Entry(str(a["id"]), str(a["displayName"]), _injury_text(a))
                for a in athletes
                if isinstance(a, dict) and a.get("id") is not None and a.get("displayName")
            ]
            if players:
                out[group][slot] = players
    return out


def fetch_depth_chart(http: httpx.Client, team: str) -> dict[str, dict[str, list[Entry]]]:
    """One team's chart from ESPN. Raises for an unknown team or a failed request."""
    response = http.get(DEPTH_URL.format(team_id=TEAM_IDS[team]), timeout=30.0)
    response.raise_for_status()
    return parse_depth_chart(response.json())


def slot_label(group: str, slot: str) -> str:
    return LABELS.get(group, {}).get(slot) or slot.upper()


def slot_order(group: str, slot: str) -> int:
    """Reading order within a group; slots we have no label for go last."""
    keys = list(LABELS.get(group, {}))
    return keys.index(slot) if slot in keys else len(keys)


class RosterPlayer(NamedTuple):
    player_id: str
    name: str | None
    team: str | None
    espn_id: str | None
    depth_position: str | None  # Sleeper's depth chart slot, e.g. RWR, LDE, K
    depth_order: int | None


def attach_sleeper_ids(
    chart: dict[str, dict[str, list[Entry]]], team: str, roster: list[RosterPlayer]
) -> dict[str, dict[str, list[Entry]]]:
    """The same chart with each player's Sleeper id filled in where one can be found.

    A player matches by ESPN id first, then by name within the team. A name that matches two
    players on the team is not guessed, and the player is simply left without a Sleeper id.
    """
    by_espn = {p.espn_id: p.player_id for p in roster if p.espn_id}
    by_name: dict[str, list[str]] = defaultdict(list)
    for p in roster:
        if p.name and p.team == team:
            by_name[normalize_name(p.name)].append(p.player_id)

    def resolve(entry: Entry) -> Entry:
        if entry.sleeper_id:
            return entry
        if entry.espn_id in by_espn:
            return entry._replace(sleeper_id=by_espn[entry.espn_id])
        candidates = by_name.get(normalize_name(entry.name), [])
        return entry._replace(sleeper_id=candidates[0]) if len(candidates) == 1 else entry

    return {
        group: {slot: [resolve(e) for e in players] for slot, players in slots.items()}
        for group, slots in chart.items()
    }


# Sleeper's depth chart slots, mapped to the same slot keys the ESPN chart uses
_SLEEPER_SLOT = {
    "QB": "qb", "RB": "rb", "TE": "te", "LWR": "wr1", "RWR": "wr2", "SWR": "wr3", "K": "pk",
    "P": "p", "LS": "ls", "NT": "nt", "LDE": "lde", "RDE": "rde", "LDT": "ldt", "RDT": "rdt",
    "LOLB": "lolb", "ROLB": "rolb", "MLB": "mlb", "LILB": "lilb", "RILB": "rilb", "SLB": "slb",
    "LCB": "lcb", "RCB": "rcb", "NB": "nb", "SS": "ss", "FS": "fs",
}  # fmt: skip


def chart_from_sleeper(roster: list[RosterPlayer]) -> dict[str, dict[str, list[Entry]]]:
    """A chart from Sleeper's depth chart fields (Sleeper has no offensive line or returners)."""
    slots: dict[str, list[tuple[int, RosterPlayer]]] = defaultdict(list)
    for p in roster:
        slot = _SLEEPER_SLOT.get(p.depth_position or "")
        if slot is not None and p.depth_order is not None:
            slots[slot].append((p.depth_order, p))
    out: dict[str, dict[str, list[Entry]]] = {group: {} for group in GROUPS}
    for slot, players in slots.items():
        ordered = sorted(players, key=lambda item: (item[0], item[1].name or ""))
        out[_GROUP_OF[slot]][slot] = [
            Entry(p.espn_id, p.name or p.player_id, None, p.player_id) for _, p in ordered
        ]
    return out
