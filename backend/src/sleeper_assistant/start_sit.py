"""Start/Sit: compare players for a lineup spot, and suggest the best lineup for a roster.

Both build on the weekly rankings, so the numbers match the Rankings tab: the projection scored
with this league's rules, recent form, the opponent's defense rank against the position, the
game's conditions and the injury designation. The recommendation always names its reason and the
figures behind it, and says when it is a close call instead of pretending to be sure.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import LeagueRow, PlayerRow, RosterRow
from sleeper_assistant.injury_status import WILL_NOT_PLAY
from sleeper_assistant.lineup_slots import assign_lineup, starter_slots
from sleeper_assistant.matchup_rank import (
    DefenseTable,
    MatchupRank,
    build_defense_table,
    matchup_rank,
)
from sleeper_assistant.nfl_games import GameInfo, games_for_week
from sleeper_assistant.players_view import player_name
from sleeper_assistant.projections import projected_points
from sleeper_assistant.rankings import RankedPlayer, Rankings, build_rankings
from sleeper_assistant.roster_players import InjuryInfo, injury_info

# designations that mean a player will not play
CLOSE_CALL = 1.5  # projected points apart, or fewer, is a close call
MAX_COMPARE = 6
_POSITION_ORDER = {pos: i for i, pos in enumerate(("QB", "RB", "WR", "TE", "K", "DEF"))}


class Candidate(BaseModel):
    player_id: str
    name: str
    position: str | None
    team: str | None
    injury: InjuryInfo | None = None
    game: GameInfo | None = None
    matchup: MatchupRank | None = None
    projected: float | None = None
    form: float | None = None
    started_pct: float | None = None
    rank: int | None = None  # consensus rank within the position
    score: float | None = None  # average signal rank (lower is better)
    sources: int = 0
    out: str | None = None  # why he cannot be recommended: an injury or a bye


class Comparison(BaseModel):
    league_id: str
    week: int | None
    candidates: list[Candidate]  # best first
    start: str | None  # the recommended player's id
    close_call: bool
    why: str


class LineupSpot(BaseModel):
    slot: str
    player: Candidate | None


class LineupChange(BaseModel):
    start: Candidate
    sit: Candidate
    gain: float  # projected points


class BestLineup(BaseModel):
    league_id: str
    roster_id: int
    week: int | None
    lineup: list[LineupSpot]
    projected: float
    current_projected: float
    changes: list[LineupChange]
    why: str
    roster: list[Candidate] = Field(
        default_factory=list
    )  # everyone who can be picked to compare, with the same numbers


@dataclass(frozen=True)
class _Extra:
    """What to use for a player the consensus rankings leave out: his stored projection and game."""

    projections: dict[str, float]
    games: dict[str, GameInfo]
    defense: DefenseTable


def _extra(
    session: Session, league: LeagueRow, rankings: Rankings, ids: list[str], ranked: set[str]
) -> _Extra:
    """Projections (scored with the league's rules), games and the defense table for the players
    in ``ids`` the rankings leave out; nothing is looked up when the rankings have them all."""
    week = rankings.week
    missing = [pid for pid in ids if pid not in ranked]
    if week is None or not missing:
        return _Extra(projections={}, games={}, defense={})
    return _Extra(
        projections=projected_points(
            session, league.season, week, league.scoring_settings, missing
        ),
        games=games_for_week(session, league.season, week),
        defense=build_defense_table(session, league.season, league.scoring_settings),
    )


def _candidate(
    pid: str, ranked: dict[str, RankedPlayer], info: dict[str, PlayerRow], extra: _Extra
) -> Candidate:
    player = info.get(pid)
    r = ranked.get(pid)
    if r is None and player is not None and pid in extra.projections:
        # the rankings left him out (a zero projection, or no source ranks him) but a projection
        # exists: use it instead of calling him unprojected
        game = extra.games.get(player.team or "")
        injury = injury_info({pid: player}, pid)
        status = injury.status if injury else None
        return Candidate(
            player_id=pid, name=player_name(player), position=player.position, team=player.team,
            injury=injury, game=game,
            matchup=matchup_rank(
                extra.defense, player.position or "", game.opponent if game else None
            ),
            projected=round(extra.projections[pid], 2), sources=1,
            out=f"listed {status}" if status in WILL_NOT_PLAY else (
                "on a bye" if game is not None and game.state == "bye" else None
            ),
        )  # fmt: skip
    if r is not None:
        status = r.injury.status if r.injury else None
        return Candidate(
            player_id=pid, name=r.name, position=r.position, team=r.team, injury=r.injury,
            game=r.game, matchup=r.matchup, projected=r.projected, form=r.form,
            started_pct=r.started_pct, rank=r.rank, score=r.score, sources=r.sources,
            out=f"listed {status}" if status in WILL_NOT_PLAY else (
                "on a bye" if r.game is not None and r.game.state == "bye" else None
            ),
        )  # fmt: skip
    return Candidate(
        player_id=pid,
        name=player_name(player) if player else pid,
        position=player.position if player else None,
        team=player.team if player else None,
        out="no projection this week",
    )


def candidate_line(c: Candidate) -> str:
    bits = []
    if c.projected is not None:
        bits.append(f"projected {c.projected:.1f}")
    if c.form is not None:
        bits.append(f"{c.form:.1f} a game lately")
    if c.matchup is not None:
        side = "offense" if c.matchup.side == "offense" else "defense"
        bits.append(f"{c.matchup.opponent} {side} ranks {c.matchup.rank} of {c.matchup.teams}")
    return ", ".join(bits)


def compare_players(
    session: Session, league: LeagueRow, player_ids: list[str], week: int | None = None
) -> Comparison:
    """Rank the given players for one spot and say which to start."""
    rankings = build_rankings(session, league, week)
    ranked = {p.player_id: p for p in rankings.players}
    ids = list(dict.fromkeys(player_ids))[:MAX_COMPARE]
    info = {
        p.player_id: p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(ids)))
    }
    extra = _extra(session, league, rankings, ids, set(ranked))
    candidates = [_candidate(pid, ranked, info, extra) for pid in ids]
    eligible = [c for c in candidates if c.out is None and c.projected is not None]
    # the consensus decides; projected points break a tie, then the name keeps it stable. A player
    # the rankings left out has no consensus score, so when anyone lacks one the projections
    # decide for everybody (a score and a projection cannot be compared with each other).
    by_projection = any(c.score is None for c in eligible)

    def order(c: Candidate) -> tuple[float, float, str]:
        score = c.score if c.score is not None else 1e9
        projected = -(c.projected or 0.0)
        return (projected, score, c.name) if by_projection else (score, projected, c.name)

    candidates.sort(key=lambda c: (c.out is not None, *order(c)))
    eligible.sort(key=order)
    if not eligible:
        return Comparison(
            league_id=league.league_id, week=rankings.week, candidates=candidates, start=None,
            close_call=False, why="None of these players can be started this week.",
        )  # fmt: skip
    best = eligible[0]
    gap = None
    close = False
    if len(eligible) > 1:
        runner = eligible[1]
        gap = (best.projected or 0.0) - (runner.projected or 0.0)
        same_score = best.score is not None and best.score == runner.score
        close = abs(gap) < CLOSE_CALL or same_score
    why = f"Start {best.name}: {candidate_line(best)}."
    if len(eligible) > 1 and gap is not None:
        runner = eligible[1]
        why += f" Over {runner.name} by {gap:+.1f} projected points ({candidate_line(runner)})."
        if close:
            why += " This is a close call."
    skipped = [c for c in candidates if c.out is not None]
    if skipped:
        why += " Not counted: " + ", ".join(f"{c.name} ({c.out})" for c in skipped) + "."
    return Comparison(
        league_id=league.league_id, week=rankings.week, candidates=candidates, start=best.player_id,
        close_call=close, why=why,
    )  # fmt: skip


def best_lineup(
    session: Session, league: LeagueRow, roster_id: int, week: int | None = None
) -> BestLineup | None:
    """The projected-best lineup for a roster and how it differs from the current starters."""
    roster = session.get(RosterRow, (league.league_id, roster_id))
    if roster is None:
        return None
    rankings = build_rankings(session, league, week)
    ranked = {p.player_id: p for p in rankings.players}
    parked = set(roster.reserve) | set(roster.taxi)
    ids = [pid for pid in roster.players if pid not in parked and pid != "0"]
    info = {
        p.player_id: p
        for p in session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(ids)))
    }
    extra = _extra(session, league, rankings, ids, set(ranked))
    cands = {pid: _candidate(pid, ranked, info, extra) for pid in ids}
    usable = [
        (pid, c.position or "", c.projected or 0.0)
        for pid, c in cands.items()
        if c.out is None and c.projected is not None
    ]
    slots = starter_slots(league.roster_positions)
    lineup = assign_lineup(slots, usable)
    spots: list[LineupSpot] = []
    remaining = list(lineup)
    for slot in slots:
        match = next(((s, p) for s, p in remaining if s == slot), None)
        if match is not None:
            remaining.remove(match)
            spots.append(LineupSpot(slot=slot, player=cands[match[1]]))
        else:
            spots.append(LineupSpot(slot=slot, player=None))
    best_ids = {s.player.player_id for s in spots if s.player}
    current = [pid for pid in roster.starters if pid in cands]
    current_projected = round(sum(cands[pid].projected or 0.0 for pid in current), 2)
    projected = round(sum((s.player.projected or 0.0) for s in spots if s.player), 2)

    to_start = sorted(
        (cands[pid] for pid in best_ids if pid not in current), key=lambda c: -(c.projected or 0.0)
    )
    to_sit = sorted(
        (cands[pid] for pid in current if pid not in best_ids), key=lambda c: c.projected or 0.0
    )
    changes: list[LineupChange] = []
    for a in to_start:  # swap like for like first (a back for a back), then whoever is left
        if not to_sit:
            break
        b = next((s for s in to_sit if s.position == a.position), to_sit[0])
        to_sit.remove(b)
        changes.append(
            LineupChange(start=a, sit=b, gain=round((a.projected or 0.0) - (b.projected or 0.0), 2))
        )
    if changes:
        why = "; ".join(
            f"start {c.start.name} ({candidate_line(c.start)}) "
            f"for {c.sit.name} ({candidate_line(c.sit)}): {c.gain:+.1f}"
            for c in changes
        )
    else:
        why = "Your current lineup is already the projected best."
    return BestLineup(
        league_id=league.league_id,
        roster_id=roster_id,
        week=rankings.week,
        lineup=spots,
        projected=projected,
        current_projected=current_projected,
        changes=changes,
        why=why,
        roster=sorted(
            cands.values(),
            key=lambda c: (
                _POSITION_ORDER.get(c.position or "", len(_POSITION_ORDER)),
                c.projected is None,  # without a projection (or out) after those who have one
                -(c.projected or 0.0),
                c.name,
            ),
        ),
    )
