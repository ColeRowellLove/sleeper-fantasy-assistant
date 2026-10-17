"""Weekly player rankings by position: a consensus of independent signals, not one opinion.

Each signal ranks the players of a position on its own; the consensus is the average of those
ranks, so the page can show how many signals back a player and how far apart they are
(project principle: show the spread, not just an average). The signals today are:

* ``projection``: Sleeper's projected points for the week, scored with this league's rules;
* ``form``: points per game over the player's last three games before that week, same scoring;
* ``start``: ESPN's share of leagues that start the player (current week only);
* ``vegas``: the points the betting line implies for the player's team (total / 2 minus the team's
  spread / 2), from the lines stored with each game.

The caller can choose which of the available signals to use; the ranks, spread and source count
are then computed from only those. More sources (a licensed expert ranking such as FantasyPros,
usage shares) plug in by adding a signal. Weights start equal. A player missing from a selected
signal is ranked by the rest, and one missing from all of them is left out.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.constants import FANTASY_POSITIONS, FLEX_POSITIONS
from sleeper_assistant.core.league.ownership import roster_owners
from sleeper_assistant.core.league.player_names import player_name
from sleeper_assistant.core.league.rosters import league_rosters
from sleeper_assistant.core.league.team_names import team_names
from sleeper_assistant.core.models.games import GameInfo
from sleeper_assistant.core.models.injury import InjuryInfo
from sleeper_assistant.core.models.matchup import MatchupRank
from sleeper_assistant.core.nfl.injury_status import injury_info
from sleeper_assistant.core.nfl.matchup_rank import DefenseTable, build_defense_table, matchup_rank
from sleeper_assistant.core.nfl.nfl_games import current_week, games_for_week
from sleeper_assistant.core.scoring.form import FORM_GAMES, recent_form
from sleeper_assistant.core.scoring.projections import score_projection
from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
)
from sleeper_assistant.utils.text import ordinal

SIGNALS = ("projection", "form", "start", "vegas")
SIGNAL_LABELS = {
    "projection": "Sleeper projection",
    "form": "Last three games",
    "start": "ESPN start %",
    "vegas": "Vegas implied points",
}
# sources people ask for that cannot be used yet, and why
UNAVAILABLE = {
    "fantasypros": "FantasyPros (needs a paid license)",
}


class RankedPlayer(BaseModel):
    player_id: str
    name: str
    position: str
    team: str | None
    injury: InjuryInfo | None = None
    game: GameInfo | None = None
    matchup: MatchupRank | None = None
    owner_roster_id: int | None = None
    owner_team: str | None = None
    projected: float | None = None
    form: float | None = None  # points per game over the last three games
    started_pct: float | None = None
    implied_points: float | None = None  # points the betting line implies for his team
    signal_ranks: dict[str, int]  # signal -> rank within the position
    rank: int  # consensus rank within the position
    flex_rank: int | None = None  # consensus rank among RB, WR and TE together
    score: float  # the average of the signal ranks (lower is better)
    spread: int  # the gap between the best and worst signal rank
    sources: int  # how many signals back the player
    why: str


class Rankings(BaseModel):
    league_id: str
    week: int | None
    current_week: int | None
    weeks: list[int]
    signals: dict[str, str]  # the signals available this week: key -> label
    selected: list[str]  # the signals the ranks were computed from
    unavailable: dict[str, str] = {}  # sources not connected yet, with the reason
    players: list[RankedPlayer]


def _order[V: (float, tuple[float, ...])](values: Mapping[str, V]) -> dict[str, int]:
    """1 for the highest value; tied values share a rank. A tuple breaks ties left to right."""
    ranked = sorted(values.values(), reverse=True)
    return {pid: 1 + sum(1 for v in ranked if v > value) for pid, value in values.items()}


def _why(p: RankedPlayer, pool: int) -> str:
    bits: list[str] = []
    if p.projected is not None and "projection" in p.signal_ranks:
        bits.append(
            f"projected {p.projected:.1f} ({ordinal(p.signal_ranks['projection'])} {p.position})"
        )
    if p.form is not None:
        bits.append(f"{p.form:.1f} a game over his last {FORM_GAMES}")
    if p.started_pct is not None:
        bits.append(f"started in {p.started_pct:.0f}% of ESPN leagues")
    if p.implied_points is not None:
        bits.append(f"Vegas has {p.team} scoring {p.implied_points:.1f}")
    if p.matchup is not None:
        side = "offense" if p.matchup.side == "offense" else "defense"
        bits.append(
            f"{p.matchup.opponent} {side} ranks {ordinal(p.matchup.rank)} of {p.matchup.teams}"
        )
    if p.injury is not None:
        bits.append(f"listed {p.injury.status}")
    return "; ".join(bits) if bits else f"one of {pool} ranked"


def _implied_points(session: Session, season: str, week: int) -> dict[str, float]:
    """team -> the points the betting line implies for it this week (games with a line only)."""
    out: dict[str, float] = {}
    for g in session.scalars(
        select(NflGameRow).where(NflGameRow.season == season, NflGameRow.week == week)
    ):
        if g.total_line is None or g.spread_line is None:
            continue
        # spread_line is how many points the home team is favoured by
        out[g.home] = round(g.total_line / 2 + g.spread_line / 2, 2)
        out[g.away] = round(g.total_line / 2 - g.spread_line / 2, 2)
    return out


@dataclass
class _Signals:
    """The numbers each ranking source works from, for one week."""

    projections: dict[str, float]
    form: dict[str, float]
    started: dict[str, float]
    implied: dict[str, float]  # team code -> implied points from the betting line

    def available(self) -> dict[str, str]:
        has = {
            "projection": bool(self.projections),
            "form": bool(self.form),
            "start": bool(self.started),
            "vegas": bool(self.implied),
        }
        return {s: SIGNAL_LABELS[s] for s in SIGNALS if has[s]}


def _weeks(session: Session, season: str) -> list[int]:
    return sorted(
        set(
            session.scalars(
                select(PlayerProjectionRow.week).where(PlayerProjectionRow.season == season)
            )
        )
        | set(session.scalars(select(NflGameRow.week).where(NflGameRow.season == season)))
    )


def _load_signals(
    session: Session, season: str, week: int, now: int | None, scoring: Mapping[str, float]
) -> _Signals:
    projections = {
        row.player_id: score_projection(row.stats, scoring)
        for row in session.scalars(
            select(PlayerProjectionRow).where(
                PlayerProjectionRow.season == season, PlayerProjectionRow.week == week
            )
        )
    }
    started: dict[str, float] = {}
    if week == now:  # ESPN's start share describes the current week only
        started = {
            row.player_id: row.started
            for row in session.scalars(select(PlayerOwnershipRow))
            if row.started is not None
        }
    return _Signals(
        projections=projections,
        form=recent_form(session, season, week, scoring),
        started=started,
        implied=_implied_points(session, season, week),
    )


def _candidates(session: Session, projections: Mapping[str, float]) -> dict[str, PlayerRow]:
    """The players worth ranking: projected above zero and in a position the app shows."""
    ids = {pid for pid, pts in projections.items() if pts > 0}
    return {
        p.player_id: p
        for p in session.scalars(
            select(PlayerRow).where(
                PlayerRow.player_id.in_(ids), PlayerRow.position.in_(FANTASY_POSITIONS)
            )
        )
    }


def _consensus(
    group: list[str],
    signals: _Signals,
    players: Mapping[str, PlayerRow],
    selected: list[str],
) -> dict[str, tuple[dict[str, int], float]]:
    """pid -> (signal ranks, average rank) for one pool of players."""
    values: dict[str, dict[str, float]] = {
        "projection": {
            pid: signals.projections[pid] for pid in group if pid in signals.projections
        },
        "form": {pid: signals.form[pid] for pid in group if pid in signals.form},
        "start": {pid: signals.started[pid] for pid in group if pid in signals.started},
        "vegas": {
            pid: signals.implied[team]
            for pid in group
            if (team := players[pid].team or "") in signals.implied
        },
    }
    by_signal = {s: _order(values[s]) for s in selected}
    out: dict[str, tuple[dict[str, int], float]] = {}
    for pid in group:
        ranks = {s: r[pid] for s, r in by_signal.items() if pid in r}
        if ranks:  # a player none of the chosen sources has is left out, not guessed
            out[pid] = (ranks, sum(ranks.values()) / len(ranks))
    return out


@dataclass
class _Context:
    """What every ranked row needs besides the numbers: games, matchups and who owns him."""

    games: Mapping[str, GameInfo]
    defense: DefenseTable
    owner: Mapping[str, int]
    team_name: Mapping[int, str]


def _context(session: Session, league: LeagueRow, week: int) -> _Context:
    rosters = league_rosters(session, league.league_id)
    team_name, _ = team_names(session, rosters)
    return _Context(
        games=games_for_week(session, league.season, week),
        defense=build_defense_table(session, league.season, league.scoring_settings),
        owner=roster_owners(rosters),
        team_name=team_name,
    )


class _Standing(NamedTuple):
    """Where a player landed: his rank in each source, the average and his rank in the position."""

    ranks: dict[str, int]
    score: float
    rank: int


def _ranked_player(
    p: PlayerRow, position: str, standing: _Standing, signals: _Signals, ctx: _Context
) -> RankedPlayer:
    pid = p.player_id
    ranks, score, rank = standing
    game = ctx.games.get(p.team or "")
    return RankedPlayer(
        player_id=pid,
        name=player_name(p),
        position=position,
        team=p.team,
        injury=injury_info({pid: p}, pid),
        game=game,
        matchup=matchup_rank(ctx.defense, position, game.opponent if game else None),
        owner_roster_id=ctx.owner.get(pid),
        owner_team=ctx.team_name.get(ctx.owner[pid]) if pid in ctx.owner else None,
        projected=round(signals.projections[pid], 2) if pid in signals.projections else None,
        form=signals.form.get(pid),
        started_pct=signals.started.get(pid),
        implied_points=signals.implied.get(p.team or ""),
        signal_ranks=ranks,
        rank=rank,
        score=round(score, 2),
        spread=max(ranks.values()) - min(ranks.values()),
        sources=len(ranks),
        why="",
    )


def _rank_by_position(
    players: Mapping[str, PlayerRow], signals: _Signals, selected: list[str], ctx: _Context
) -> dict[str, RankedPlayer]:
    by_position: dict[str, list[str]] = defaultdict(list)
    for pid, p in players.items():
        by_position[p.position or ""].append(pid)
    ranked: dict[str, RankedPlayer] = {}
    for position, pool in by_position.items():
        scores = _consensus(pool, signals, players, selected)
        group = [pid for pid in pool if pid in scores]
        order = sorted(group, key=lambda pid: (scores[pid][1], -signals.projections[pid], pid))
        # consensus first, then projected points; only a tie on both shares a rank
        position_rank = _order({pid: (-scores[pid][1], signals.projections[pid]) for pid in group})
        for pid in order:
            ranks, score = scores[pid]
            standing = _Standing(ranks, score, position_rank[pid])
            ranked[pid] = _ranked_player(players[pid], position, standing, signals, ctx)
    return ranked


def _add_flex_ranks(
    ranked: dict[str, RankedPlayer],
    players: Mapping[str, PlayerRow],
    signals: _Signals,
    selected: list[str],
) -> None:
    flex_group = [pid for pid, r in ranked.items() if r.position in FLEX_POSITIONS]
    flex_scores = _consensus(flex_group, signals, players, selected)
    flex_rank = _order(
        {pid: (-flex_scores[pid][1], signals.projections[pid]) for pid in flex_group}
    )
    for pid in flex_group:
        ranked[pid].flex_rank = flex_rank[pid]


def build_rankings(
    session: Session,
    league: LeagueRow,
    week: int | None = None,
    sources: Sequence[str] | None = None,
) -> Rankings:
    now = current_week(session, league.season)
    weeks = _weeks(session, league.season)
    chosen = week if week in weeks else now
    if chosen is None:
        return Rankings(
            league_id=league.league_id, week=None, current_week=now, weeks=weeks,
            signals={}, selected=[], unavailable=UNAVAILABLE, players=[],
        )  # fmt: skip

    signals = _load_signals(session, league.season, chosen, now, league.scoring_settings)
    available = signals.available()
    selected = [s for s in SIGNALS if s in (sources or []) and s in available] or list(available)
    players = _candidates(session, signals.projections)

    ranked = _rank_by_position(players, signals, selected, _context(session, league, chosen))
    _add_flex_ranks(ranked, players, signals, selected)
    sizes: dict[str, int] = defaultdict(int)
    for r in ranked.values():
        sizes[r.position] += 1
    for r in ranked.values():
        r.why = _why(r, sizes[r.position])

    return Rankings(
        league_id=league.league_id,
        week=chosen,
        current_week=now,
        weeks=weeks,
        signals=available,
        selected=selected,
        unavailable=UNAVAILABLE,
        players=sorted(ranked.values(), key=lambda r: (r.position, r.rank, r.name)),
    )
