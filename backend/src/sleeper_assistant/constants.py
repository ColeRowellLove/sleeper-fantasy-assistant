"""Values that more than one module needs. A value used by a single module stays in that module."""

from __future__ import annotations

from zoneinfo import ZoneInfo

# --- players and lineups -------------------------------------------------------------------
# individual players, and then everything the app shows and scores (team defenses included)
PLAYER_POSITIONS = ("QB", "RB", "WR", "TE", "K")
FANTASY_POSITIONS = (*PLAYER_POSITIONS, "DEF")
# the positions that can fill a FLEX slot
FLEX_POSITIONS = frozenset({"RB", "WR", "TE"})
# Sleeper marks an empty starter slot with the player id "0"
EMPTY_SLOT = "0"
# roster slots that are not part of the starting lineup (bench, injured reserve, taxi squad)
NON_STARTER_SLOTS = frozenset({"BN", "IR", "TAXI"})

# --- NFL games: Sleeper's schedule statuses ------------------------------------------------
GAME_PRE = "pre_game"
GAME_LIVE = "in_game"
GAME_COMPLETE = "complete"

# --- ESPN -----------------------------------------------------------------------------------
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
# ESPN's team codes where they differ from Sleeper's
ESPN_TEAM_CODES = {"WSH": "WAS", "JAC": "JAX", "LA": "LAR"}

# --- time -----------------------------------------------------------------------------------
# kickoff times and the waiver day are in US Eastern time
EASTERN = ZoneInfo("America/New_York")
