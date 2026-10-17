"""Model-written advice for alerts: a roster-aware switch or pickup, with the facts stay computed.

The detectors find the *legal* options in code (a bench player who fits the slot and is healthy, a
free agent who is available and projected). The model only chooses among them and explains, and its
answer is checked before it is shown: every pick must be one of the options, a drop must be one of
the droppable players, and every number it writes must be one of the facts. Anything else, or no
model configured, leaves the alert exactly as the deterministic detector wrote it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.alerts.engine import register_pre_run
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.nfl.injury_status import UNLIKELY_TO_PLAY
from sleeper_assistant.core.scoring.projections import projected_points
from sleeper_assistant.core.sources import llm
from sleeper_assistant.db import LeagueRow, PlayerProjectionRow, PlayerRow, RosterRow

log = logging.getLogger(__name__)

FREE_AGENTS = 5  # free agents offered to the model per position
_LINKS = re.compile(r"https?:|www\.|@|<", re.IGNORECASE)


class Pick(BaseModel):
    player_id: str
    drop_id: str | None = None
    reason: str = Field(max_length=300)


class Advice(BaseModel):
    summary: str = Field(max_length=500)
    picks: list[Pick] = Field(min_length=1, max_length=3)


_budget = llm.Budget()


@register_pre_run("llm_budget")
def new_budget(_session: Session, _now: datetime) -> None:
    """A fresh call budget for each alert run."""
    global _budget  # noqa: PLW0603
    _budget = llm.Budget()


def client() -> llm.LlmClient | None:
    return llm.client_from_env()


_UNQUOTABLE = {"player_id", "droppable"}


def quotable(facts: object) -> object:
    """The facts without ids, so a number written in advice cannot match some player's id."""
    if isinstance(facts, dict):
        return {k: quotable(v) for k, v in facts.items() if k not in _UNQUOTABLE}
    if isinstance(facts, list):
        return [quotable(v) for v in facts]
    return facts


@dataclass(frozen=True)
class Unavailable:
    """Who cannot be offered as a pickup: rostered somewhere in the league, or on a bye."""

    taken: set[str]
    byes: set[str]


def free_agents(
    session: Session, league: LeagueRow, week: int, unavailable: Unavailable, positions: set[str]
) -> list[dict[str, object]]:
    """The best available players at the positions, healthy, playing, with a projection."""
    taken, byes = unavailable.taken, unavailable.byes
    ids = (
        set(
            session.scalars(
                select(PlayerProjectionRow.player_id).where(
                    PlayerProjectionRow.season == league.season, PlayerProjectionRow.week == week
                )
            )
        )
        - taken
    )
    points = projected_points(session, league.season, week, league.scoring_settings, ids)
    found = [
        (points[p.player_id], p)
        for p in session.scalars(
            select(PlayerRow).where(PlayerRow.player_id.in_(ids), PlayerRow.position.in_(positions))
        )
        if p.player_id in points
        and p.team is not None
        and p.team not in byes
        and (p.injury_status or "") not in UNLIKELY_TO_PLAY
    ]
    found.sort(key=lambda item: (-item[0], item[1].player_id))
    return [option(p, "pickup", pts) for pts, p in found[: FREE_AGENTS * len(positions)]]


def option(
    p: PlayerRow, source: str, projected: float | None, **extra: object
) -> dict[str, object]:
    return {
        "player_id": p.player_id,
        "name": player_name(p),
        "position": p.position,
        "team": p.team,
        "source": source,
        "projected": None if projected is None else round(projected, 1),
        **extra,
    }


def roster_facts(
    session: Session, roster: RosterRow, projections: Mapping[str, float], slots: list[str]
) -> list[dict[str, object]]:
    """Every player the team has, with where he sits and how he is projected."""
    ids = [*roster.players, *roster.reserve, *roster.taxi]
    players = {
        p.player_id: p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(ids)))
    }
    facts: list[dict[str, object]] = []
    for pid in dict.fromkeys(ids):
        p = players.get(pid)
        if p is None:
            continue
        if pid in roster.starters and roster.starters.index(pid) < len(slots):
            spot = f"starter at {slots[roster.starters.index(pid)]}"
        elif pid in roster.reserve:
            spot = "injured reserve"
        elif pid in roster.taxi:
            spot = "taxi squad"
        else:
            spot = "bench"
        facts.append(
            {
                **option(p, spot, projections.get(pid)),
                "injury": p.injury_status or "healthy",
            }
        )
    return facts


def advise(
    prompt_name: str,
    facts: dict[str, object],
    options: list[dict[str, object]],
    droppable: set[str],
) -> dict[str, object] | None:
    """The model's checked advice for these facts, ready to store in an alert, or None."""
    chosen = client()
    if chosen is None or not options:
        return None
    by_id = {str(o["player_id"]): o for o in options}

    def valid(advice: Advice) -> bool:
        ids = [pick.player_id for pick in advice.picks]
        texts = [advice.summary, *(pick.reason for pick in advice.picks)]
        return (
            len(set(ids)) == len(ids)
            and all(i in by_id for i in ids)
            and all(pick.drop_id is None or pick.drop_id in droppable for pick in advice.picks)
            and not any(_LINKS.search(t) for t in texts)
            and llm.grounded_numbers(texts, quotable(facts))
        )

    answer = llm.ask(
        chosen,
        llm.load_prompt(prompt_name),
        facts,
        Advice,
        check=valid,
        budget=_budget,
    )
    if answer is None:
        return None
    names = {str(f["player_id"]): str(f["name"]) for f in facts.get("roster", [])}  # type: ignore[attr-defined]
    return {
        "source": "model",
        "summary": answer.summary,
        "picks": [
            {
                "player_id": pick.player_id,
                "name": by_id[pick.player_id]["name"],
                "position": by_id[pick.player_id]["position"],
                "team": by_id[pick.player_id]["team"],
                "action": by_id[pick.player_id]["source"],
                "drop_id": pick.drop_id,
                "drop_name": names.get(pick.drop_id) if pick.drop_id else None,
                "reason": pick.reason,
            }
            for pick in answer.picks
        ],
    }
