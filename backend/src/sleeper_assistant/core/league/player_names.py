"""A player's name as people read it."""

from __future__ import annotations

from sleeper_assistant.db import PlayerRow


def player_name(player: PlayerRow) -> str:
    """A team defense is "CLE defense"; a player with no name shows his id, never a blank."""
    if player.position == "DEF" and player.team:
        return f"{player.team} defense"
    return player.full_name or player.player_id
