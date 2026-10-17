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

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    NflGameRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerWeekStatsRow,
)
from sleeper_assistant.matchup_rank import MatchupRank, build_defense_table, matchup_rank
from sleeper_assistant.nfl_games import GameInfo, current_week, games_for_week
from sleeper_assistant.player_names import player_name
from sleeper_assistant.projections import score_projection, score_stats
from sleeper_assistant.roster_players import InjuryInfo, injury_info
from sleeper_assistant.rosters import league_rosters
from sleeper_assistant.team_names import team_names

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
FLEX_POSITIONS = frozenset({"RB", "WR", "TE"})
FORM_GAMES = 3
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


def recent_form(
    session: Session, season: str, week: int, scoring: Mapping[str, float]
) -> dict[str, float]:
    """Points per game over the last three games played before ``week``."""
    games: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for pid, wk, stats in session.execute(
        select(
            PlayerWeekStatsRow.player_id, PlayerWeekStatsRow.week, PlayerWeekStatsRow.stats
        ).where(PlayerWeekStatsRow.season == season, PlayerWeekStatsRow.week < week)
    ):
        played = stats.get("gp")
        if played is not None and played <= 0:
            continue
        games[pid].append((wk, score_stats(stats, scoring)))
    out: dict[str, float] = {}
    for pid, rows in games.items():
        last = [points for _, points in sorted(rows)[-FORM_GAMES:]]
        out[pid] = round(sum(last) / len(last), 2)
    return out


def _why(p: RankedPlayer, pool: int) -> str:
    bits: list[str] = []
    if p.projected is not None and "projection" in p.signal_ranks:
        bits.append(
            f"projected {p.projected:.1f} ({_ordinal(p.signal_ranks['projection'])} {p.position})"
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
            f"{p.matchup.opponent} {side} ranks {_ordinal(p.matchup.rank)} of {p.matchup.teams}"
        )
    if p.injury is not None:
        bits.append(f"listed {p.injury.status}")
    return "; ".join(bits) if bits else f"one of {pool} ranked"


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:  # noqa: PLR2004
        return f"{n}th"
    return f"{n}{({1: 'st', 2: 'nd', 3: 'rd'}).get(n % 10, 'th')}"


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


def build_rankings(
    session: Session,
    league: LeagueRow,
    week: int | None = None,
    sources: Sequence[str] | None = None,
) -> Rankings:
    season = league.season
    scoring = league.scoring_settings
    now = current_week(session, season)
    weeks = sorted(
        set(
            session.scalars(
                select(PlayerProjectionRow.week).where(PlayerProjectionRow.season == season)
            )
        )
        | set(session.scalars(select(NflGameRow.week).where(NflGameRow.season == season)))
    )
    chosen = week if week in weeks else now
    if chosen is None:
        return Rankings(
            league_id=league.league_id, week=None, current_week=now, weeks=weeks,
            signals={}, selected=[], unavailable=UNAVAILABLE, players=[],
        )  # fmt: skip

    projections = {
        row.player_id: score_projection(row.stats, scoring)
        for row in session.scalars(
            select(PlayerProjectionRow).where(
                PlayerProjectionRow.season == season, PlayerProjectionRow.week == chosen
            )
        )
    }
    form = recent_form(session, season, chosen, scoring)
    started: dict[str, float] = {}
    if chosen == now:  # ESPN's start share describes the current week only
        started = {
            row.player_id: row.started
            for row in session.scalars(select(PlayerOwnershipRow))
            if row.started is not None
        }
    implied = _implied_points(session, season, chosen)
    has = {
        "projection": bool(projections),
        "form": bool(form),
        "start": bool(started),
        "vegas": bool(implied),
    }
    signals = {s: SIGNAL_LABELS[s] for s in SIGNALS if has[s]}
    selected = [s for s in SIGNALS if s in (sources or []) and s in signals] or list(signals)
    candidates = {pid for pid, pts in projections.items() if pts > 0}
    players = {
        p.player_id: p
        for p in session.scalars(
            select(PlayerRow).where(
                PlayerRow.player_id.in_(candidates), PlayerRow.position.in_(POSITIONS)
            )
        )
    }

    rosters = league_rosters(session, league.league_id)
    team_name, _ = team_names(session, rosters)
    owner = {pid: r.roster_id for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]}
    games = games_for_week(session, season, chosen)
    defense = build_defense_table(session, season, scoring)

    def consensus(group: list[str]) -> dict[str, tuple[dict[str, int], float]]:
        """pid -> (signal ranks, average rank) for one pool of players."""
        values: dict[str, dict[str, float]] = {
            "projection": {pid: projections[pid] for pid in group if pid in projections},
            "form": {pid: form[pid] for pid in group if pid in form},
            "start": {pid: started[pid] for pid in group if pid in started},
            "vegas": {
                pid: implied[team] for pid in group if (team := players[pid].team or "") in implied
            },
        }
        by_signal = {s: _order(values[s]) for s in selected}
        out: dict[str, tuple[dict[str, int], float]] = {}
        for pid in group:
            ranks = {s: r[pid] for s, r in by_signal.items() if pid in r}
            if ranks:  # a player none of the chosen sources has is left out, not guessed
                out[pid] = (ranks, sum(ranks.values()) / len(ranks))
        return out

    by_position: dict[str, list[str]] = defaultdict(list)
    for pid, p in players.items():
        by_position[p.position or ""].append(pid)

    ranked: dict[str, RankedPlayer] = {}
    for position, pool in by_position.items():
        scores = consensus(pool)
        group = [pid for pid in pool if pid in scores]
        order = sorted(group, key=lambda pid: (scores[pid][1], -projections[pid], pid))
        # consensus first, then projected points; only a tie on both shares a rank
        positions_rank = _order({pid: (-scores[pid][1], projections[pid]) for pid in group})
        for pid in order:
            p = players[pid]
            ranks, score = scores[pid]
            game = games.get(p.team or "")
            ranked[pid] = RankedPlayer(
                player_id=pid,
                name=player_name(p),
                position=position,
                team=p.team,
                injury=injury_info({pid: p}, pid),
                game=game,
                matchup=matchup_rank(defense, position, game.opponent if game else None),
                owner_roster_id=owner.get(pid),
                owner_team=team_name.get(owner[pid]) if pid in owner else None,
                projected=round(projections[pid], 2) if pid in projections else None,
                form=form.get(pid),
                started_pct=started.get(pid),
                implied_points=implied.get(p.team or ""),
                signal_ranks=ranks,
                rank=positions_rank[pid],
                score=round(score, 2),
                spread=max(ranks.values()) - min(ranks.values()),
                sources=len(ranks),
                why="",
            )
    flex_group = [pid for pid, r in ranked.items() if r.position in FLEX_POSITIONS]
    flex_scores = consensus(flex_group)
    flex_rank = _order({pid: (-flex_scores[pid][1], projections[pid]) for pid in flex_group})
    for pid in flex_group:
        ranked[pid].flex_rank = flex_rank[pid]
    sizes: dict[str, int] = defaultdict(int)
    for r in ranked.values():
        sizes[r.position] += 1
    for r in ranked.values():
        r.why = _why(r, sizes[r.position])

    ordered = sorted(ranked.values(), key=lambda r: (r.position, r.rank, r.name))
    return Rankings(
        league_id=league.league_id,
        week=chosen,
        current_week=now,
        weeks=weeks,
        signals=signals,
        selected=selected,
        unavailable=UNAVAILABLE,
        players=ordered,
    )
