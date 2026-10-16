"""ESPN fantasy ownership: the share of ESPN leagues that roster and start each player.

Sleeper does not publish rostered or started percentages, but ESPN's public fantasy API does
(``ownership.percentOwned`` and ``percentStarted``). It is undocumented, so every response is
treated as untrusted and a failed pull leaves the previous numbers in place. These are ESPN-wide
numbers, not Sleeper's, and the app labels them that way.

ESPN players are matched to Sleeper players by ESPN id where Sleeper has one (about a fifth of
players), otherwise by name, team and position.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from typing import Any, NamedTuple

import httpx

ESPN_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
    "/segments/0/leaguedefaults/3?view=kona_player_info"
)
# top players by ownership; below roughly the 900th the share is under 0.1 percent
LIMIT = 900
_FILTER = {
    "players": {
        "filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]},
        "limit": LIMIT,
        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
    }
}

# ESPN's pro team ids and position ids (D/ST rows use id -(16000 + team id))
TEAMS = {
    1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET", 9: "GB",
    10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR", 15: "MIA", 16: "MIN", 17: "NE",
    18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF",
    26: "SEA", 27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}  # fmt: skip
POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}
_DST_BASE = 16000


class Ownership(NamedTuple):
    """One ESPN player's numbers, with what is needed to find the matching Sleeper player."""

    espn_id: str
    name: str
    team: str | None
    position: str | None
    owned: float | None
    started: float | None


def _percent(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return round(float(value), 2)


def parse_ownership(payload: Any) -> list[Ownership]:
    """The players in an ESPN response that have a usable id, name and ownership block."""
    players = payload.get("players") if isinstance(payload, dict) else None
    if not isinstance(players, list):
        return []
    out: list[Ownership] = []
    for item in players:
        player = item.get("player") if isinstance(item, dict) else None
        if not isinstance(player, dict) or not isinstance(player.get("id"), int):
            continue
        ownership = player.get("ownership")
        if not isinstance(ownership, dict) or not player.get("fullName"):
            continue
        espn_id = player["id"]
        position = POSITIONS.get(player.get("defaultPositionId", 0))
        if espn_id < 0:  # a team defense: the team is part of the id
            team = TEAMS.get(-espn_id - _DST_BASE)
        else:
            team = TEAMS.get(player.get("proTeamId", 0))
        out.append(
            Ownership(
                espn_id=str(espn_id),
                name=str(player["fullName"]),
                team=team,
                position=position,
                owned=_percent(ownership.get("percentOwned")),
                started=_percent(ownership.get("percentStarted")),
            )
        )
    return out


def fetch_ownership(http: httpx.Client, season: str) -> list[Ownership]:
    """Pull the top players' ownership from ESPN (about 4 MB compressed, a second or so)."""
    response = http.get(
        ESPN_URL.format(season=season),
        headers={"X-Fantasy-Filter": json.dumps(_FILTER)},
        timeout=60.0,
    )
    response.raise_for_status()
    return parse_ownership(response.json())


_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def normalize_name(name: str) -> str:
    """Lowercase, no accents, punctuation or Jr/III suffixes, so "D'Andre Swift Jr." matches."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^a-z0-9 ]", "", folded.lower().replace("-", " "))
    return re.sub(r"\s+", " ", _SUFFIX.sub("", cleaned)).strip()


class SleeperPerson(NamedTuple):
    player_id: str
    name: str | None
    team: str | None
    position: str | None
    espn_id: str | None


def match_players(
    espn: Iterable[Ownership], sleeper: Iterable[SleeperPerson]
) -> dict[str, Ownership]:
    """Sleeper player id -> ESPN numbers. Ambiguous or unknown players are simply left out."""
    by_id: dict[str, Ownership] = {}
    by_key: dict[tuple[str, str | None, str | None], list[Ownership]] = {}
    for row in espn:
        by_id[row.espn_id] = row
        by_key.setdefault((normalize_name(row.name), row.team, row.position), []).append(row)

    matched: dict[str, Ownership] = {}
    for person in sleeper:
        if person.espn_id and person.espn_id in by_id:
            matched[person.player_id] = by_id[person.espn_id]
            continue
        if person.position == "DEF" and person.team:
            # a defense is its team: ESPN calls it "<nickname> D/ST", Sleeper uses the team code
            candidates = [
                r for r in by_id.values() if r.position == "DEF" and r.team == person.team
            ]
        elif person.name:
            key = (normalize_name(person.name), person.team, person.position)
            candidates = by_key.get(key, [])
        else:
            continue
        if len(candidates) == 1:  # a name that matches two players is not guessed
            matched[person.player_id] = candidates[0]
    return matched
