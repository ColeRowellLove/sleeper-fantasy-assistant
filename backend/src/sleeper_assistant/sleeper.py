"""Thin read-only client for the public Sleeper API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, Field

BASE_URL = "https://api.sleeper.app/v1"


class SleeperNotFoundError(LookupError):
    """The requested user or league does not exist on Sleeper."""


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
    previous_league_id: str | None = None


class SleeperState(BaseModel):
    week: int
    season: str
    season_type: str


class SleeperRoster(BaseModel):
    roster_id: int
    owner_id: str | None = None
    players: list[str] | None = None
    starters: list[str] | None = None
    reserve: list[str] | None = None  # injured reserve
    taxi: list[str] | None = None
    settings: dict[str, Any] = {}


class SleeperMatchup(BaseModel):
    roster_id: int
    matchup_id: int | None = None
    points: float = 0.0
    starters: list[str] | None = None
    starters_points: list[float | None] | None = None
    players: list[str] | None = None
    players_points: dict[str, float | None] | None = None


class SleeperTransaction(BaseModel):
    transaction_id: str
    type: str
    status: str
    leg: int = Field(description="Week the transaction belongs to")
    created: int | None = None


class SleeperPlayer(BaseModel):
    player_id: str
    full_name: str | None = None
    position: str | None = None
    team: str | None = None
    status: str | None = None
    injury_status: str | None = None
    gsis_id: str | None = None
    espn_id: int | str | None = None
    yahoo_id: int | str | None = None
    sportradar_id: str | None = None
    rotowire_id: int | str | None = None
    fantasy_data_id: int | str | None = None
    stats_id: int | str | None = None


class SleeperClient:
    """Read-only; the Sleeper API needs no auth."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        recorder: Callable[[str, Any], None] | None = None,
    ) -> None:
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=10.0)
        # Called with (path, raw JSON) for every response, e.g. to keep raw snapshots.
        self.recorder = recorder

    def with_recorder(self, recorder: Callable[[str, Any], None]) -> SleeperClient:
        """A view of this client (same HTTP connection pool) with its own recorder.

        Lets concurrent syncs record into their own sessions without sharing mutable state.
        """
        return SleeperClient(self._client, recorder)

    def get_json(self, path: str) -> Any:
        resp = self._client.get(path)
        resp.raise_for_status()
        data = resp.json()
        if self.recorder is not None:
            self.recorder(path, data)
        return data

    def get_state(self) -> SleeperState:
        return SleeperState.model_validate(self.get_json("/state/nfl"))

    def get_user(self, username: str) -> SleeperUser:
        data = self.get_json(f"/user/{username}")
        if data is None:  # Sleeper answers 200 with a JSON null for unknown users
            raise SleeperNotFoundError(f"no Sleeper user {username!r}")
        return SleeperUser.model_validate(data)

    def get_leagues(self, user_id: str, season: str) -> list[SleeperLeague]:
        data = self.get_json(f"/user/{user_id}/leagues/nfl/{season}")
        return [SleeperLeague.model_validate(item) for item in data]

    def get_league(self, league_id: str) -> SleeperLeague:
        data = self.get_json(f"/league/{league_id}")
        if data is None:  # unknown league ids come back as a JSON null
            raise SleeperNotFoundError(f"no Sleeper league {league_id!r}")
        return SleeperLeague.model_validate(data)

    def get_league_users(self, league_id: str) -> list[SleeperUser]:
        data = self.get_json(f"/league/{league_id}/users")
        return [SleeperUser.model_validate(item) for item in data]

    def get_rosters(self, league_id: str) -> list[SleeperRoster]:
        data = self.get_json(f"/league/{league_id}/rosters")
        return [SleeperRoster.model_validate(item) for item in data]

    def get_matchups(self, league_id: str, week: int) -> list[SleeperMatchup]:
        data = self.get_json(f"/league/{league_id}/matchups/{week}")
        return [SleeperMatchup.model_validate(item) for item in data]

    def get_transactions(self, league_id: str, week: int) -> list[SleeperTransaction]:
        data = self.get_json(f"/league/{league_id}/transactions/{week}")
        return [SleeperTransaction.model_validate(item) for item in data]

    def get_players(self) -> list[SleeperPlayer]:
        """The full player DB (~5 MB). Fetch at most once a day."""
        data: dict[str, dict[str, Any]] = self.get_json("/players/nfl")
        return [
            SleeperPlayer.model_validate({**item, "player_id": pid}) for pid, item in data.items()
        ]
