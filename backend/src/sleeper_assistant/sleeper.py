"""Thin read-only client for the public Sleeper API."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

BASE_URL = "https://api.sleeper.app/v1"


class SleeperUser(BaseModel):
    user_id: str
    username: str | None = None
    display_name: str


class SleeperLeague(BaseModel):
    league_id: str
    name: str
    season: str
    total_rosters: int
    scoring_settings: dict[str, Any] = {}
    roster_positions: list[str] = []
    settings: dict[str, Any] = {}


class SleeperClient:
    """Read-only; the Sleeper API needs no auth."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=10.0)

    def get_user(self, username: str) -> SleeperUser:
        resp = self._client.get(f"/user/{username}")
        resp.raise_for_status()
        return SleeperUser.model_validate(resp.json())

    def get_leagues(self, user_id: str, season: str) -> list[SleeperLeague]:
        resp = self._client.get(f"/user/{user_id}/leagues/nfl/{season}")
        resp.raise_for_status()
        return [SleeperLeague.model_validate(item) for item in resp.json()]
