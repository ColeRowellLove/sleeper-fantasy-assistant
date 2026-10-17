"""Every environment variable the app reads, in one place.

``load_settings()`` reads the environment each time it is called (cheap, and tests can change the
environment); nothing else in the app reads ``os.environ``. Keys and URLs with credentials are never
logged. Each variable is documented in the README configuration table, and a test fails when one is
missing there.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "sqlite:///./dev.db"

# every variable load_settings reads (the README table must list each one)
ENV_VARS = (
    "DATABASE_URL",
    "NEWS_FEEDS",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_KEY",
    "ANTHROPIC_API_KEY",
    "LLM_BASE_URL",
    "LLM_MAX_CALLS_PER_RUN",
    "SLEEPER_USERNAME",
    "SLEEPER_LEAGUE_ID",
    "BOOT_ALLOW_SHARED_DB",
)


@dataclass(frozen=True)
class Settings:
    database_url_raw: str  # as set; empty when DATABASE_URL is unset
    news_feeds: str  # "name|url,name|url", empty for the defaults
    llm_provider: str  # none, anthropic or openai_compatible
    llm_model: str
    llm_api_key: str
    anthropic_api_key: str
    llm_base_url: str
    llm_max_calls: int | None  # None means the built-in default
    sleeper_username: str | None  # boot loads every league of this user
    sleeper_league_id: str | None  # boot loads this one league
    boot_allow_shared_db: bool  # let boot write to a database that is not SQLite

    @property
    def database_url(self) -> str:
        return self.database_url_raw or DEFAULT_DATABASE_URL


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """The settings from ``env`` (the process environment when not given)."""
    values = os.environ if env is None else env
    cap = values.get("LLM_MAX_CALLS_PER_RUN", "")
    return Settings(
        database_url_raw=values.get("DATABASE_URL", ""),
        news_feeds=values.get("NEWS_FEEDS", "").strip(),
        llm_provider=(values.get("LLM_PROVIDER") or "none").strip().lower(),
        llm_model=values.get("LLM_MODEL", "").strip(),
        llm_api_key=values.get("LLM_API_KEY", ""),
        anthropic_api_key=values.get("ANTHROPIC_API_KEY", ""),
        llm_base_url=values.get("LLM_BASE_URL", "").strip(),
        llm_max_calls=int(cap) if cap.isdigit() else None,
        sleeper_username=values.get("SLEEPER_USERNAME") or None,
        sleeper_league_id=values.get("SLEEPER_LEAGUE_ID") or None,
        boot_allow_shared_db=values.get("BOOT_ALLOW_SHARED_DB") == "1",
    )
