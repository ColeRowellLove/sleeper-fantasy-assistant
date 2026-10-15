"""Read models for the league dashboard: standings, rosters and weekly lineups."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerRow,
    RosterRow,
    SleeperUserRow,
)

# Sleeper marks an empty starter slot with the player id "0".
EMPTY_SLOT = "0"
NON_STARTER_SLOTS = {"BN", "IR", "TAXI"}
# Matchup `players` also lists IR and taxi players; they are shown after the bench, not as bench.
_PARKED_ORDER = {"BN": 0, "IR": 1, "TAXI": 2}

Status = Literal["starter", "bench", "ir", "taxi"]
GameState = Literal["upcoming", "live", "final", "bye"]

# Sleeper schedule statuses -> what we show. Unknown statuses show nothing rather than a guess.
_STATUS_STATE: dict[str, GameState] = {
    "pre_game": "upcoming",
    "in_game": "live",
    "complete": "final",
}


class InjuryInfo(BaseModel):
    """Injury designation from Sleeper (Out, Doubtful, Questionable, IR, PUP, ...)."""

    status: str
    body_part: str | None = None


class GameInfo(BaseModel):
    """A player's NFL game in a week: upcoming, live, final, or the team is on a bye."""

    state: GameState
    date: str | None = None  # ISO date; Sleeper's schedule has no kickoff time
    opponent: str | None = None
    home: bool | None = None


class StandingsRow(BaseModel):
    rank: int
    roster_id: int
    team: str
    owner_id: str | None = None
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float


class RosterPlayer(BaseModel):
    player_id: str
    name: str
    position: str | None
    team: str | None
    status: Status
    slot: str | None  # lineup slot for starters, e.g. QB, RB, FLEX
    game: GameInfo | None = None  # this week's game (or bye) for the player's NFL team
    injury: InjuryInfo | None = None


class RosterView(BaseModel):
    roster_id: int
    team: str
    owner_id: str | None = None
    players: list[RosterPlayer]  # starters (slot order), bench, IR, taxi


class Dashboard(BaseModel):
    league_id: str
    name: str
    season: str
    week: int | None = None  # the current NFL week (first week with an unfinished game)
    standings: list[StandingsRow]
    rosters: list[RosterView]


class LineupPlayer(BaseModel):
    slot: str  # QB/RB/FLEX/... for starters, "BN" for bench
    player_id: str | None  # None for an empty starter slot
    name: str
    position: str | None
    team: str | None
    points: float | None
    game: GameInfo | None = None
    injury: InjuryInfo | None = None


class TeamLineup(BaseModel):
    roster_id: int
    team: str
    owner_id: str | None = None
    points: float
    starters: list[LineupPlayer]
    bench: list[LineupPlayer]


class MatchupView(BaseModel):
    matchup_id: int | None
    teams: list[TeamLineup]


class Lineups(BaseModel):
    week: int | None
    current_week: int | None = None  # weeks after this one have not been played yet
    weeks: list[int]
    matchups: list[MatchupView]


def starter_slots(league: LeagueRow) -> list[str]:
    """Lineup slot labels in the order Sleeper lists a roster's starters."""
    return [p for p in league.roster_positions if p not in NON_STARTER_SLOTS]


def _team_names(session: Session, rosters: list[RosterRow]) -> dict[int, str]:
    owner_ids = {r.owner_id for r in rosters if r.owner_id}
    names = {
        u.user_id: u.display_name
        for u in session.scalars(
            select(SleeperUserRow).where(SleeperUserRow.user_id.in_(owner_ids))
        )
    }
    return {r.roster_id: names.get(r.owner_id or "", f"Team {r.roster_id}") for r in rosters}


def _players(session: Session, player_ids: set[str]) -> dict[str, PlayerRow]:
    rows = session.scalars(select(PlayerRow).where(PlayerRow.player_id.in_(player_ids)))
    return {p.player_id: p for p in rows}


# Designations that carry no information for a fantasy manager are hidden.
_HIDDEN_INJURY_STATUSES = {"", "NA"}


def _injury(players: dict[str, PlayerRow], pid: str) -> InjuryInfo | None:
    p = players.get(pid)
    if p is None or not p.injury_status or p.injury_status in _HIDDEN_INJURY_STATUSES:
        return None
    return InjuryInfo(status=p.injury_status, body_part=p.injury_body_part or None)


def _display(players: dict[str, PlayerRow], pid: str) -> tuple[str, str | None, str | None]:
    p = players.get(pid)
    if p is None:
        return pid, None, None
    return p.full_name or pid, p.position, p.team


def current_week(session: Session, season: str) -> int | None:
    """The first week not yet fully played; the last week once the season is over.

    A week followed by a fully completed later week is treated as done even if one of its games
    never reached 'complete' (for example a postponed game), so it cannot pin the app to a week.
    """
    rows = session.execute(
        select(NflGameRow.week, NflGameRow.status).where(NflGameRow.season == season)
    ).all()
    if not rows:
        return None
    weeks = sorted({week for week, _ in rows})
    fully_complete = {w for w in weeks if all(s == "complete" for wk, s in rows if wk == w)}
    last_complete = max(fully_complete, default=0)
    for week in weeks:
        if week > last_complete:
            return week
    return weeks[-1]


def games_for_week(session: Session, season: str, week: int) -> dict[str, GameInfo]:
    """NFL team -> that team's game in the week; teams with no game in the week are on a bye."""
    games = list(session.scalars(select(NflGameRow).where(NflGameRow.season == season)))
    all_teams = {g.home for g in games} | {g.away for g in games}
    week_games = [g for g in games if g.week == week]
    playing = {g.home for g in week_games} | {g.away for g in week_games}
    out: dict[str, GameInfo] = {}
    for g in week_games:
        state = _STATUS_STATE.get(g.status)
        if state is None:
            continue
        out[g.home] = GameInfo(state=state, date=g.game_date, opponent=g.away, home=True)
        out[g.away] = GameInfo(state=state, date=g.game_date, opponent=g.home, home=False)
    if week_games:  # without any games in the week we cannot tell a bye from missing data
        for team in all_teams - playing:
            out[team] = GameInfo(state="bye")
    return out


def build_dashboard(session: Session, league: LeagueRow) -> Dashboard:
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    team = _team_names(session, rosters)
    owners = {r.roster_id: r.owner_id for r in rosters}
    players = _players(session, {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]})
    slots = starter_slots(league)
    week = current_week(session, league.season)
    games = games_for_week(session, league.season, week) if week else {}

    ordered = sorted(rosters, key=lambda r: (-r.wins, r.losses, -r.ties, -r.points_for))
    standings = [
        StandingsRow(
            rank=i,
            roster_id=r.roster_id,
            team=team[r.roster_id],
            owner_id=owners[r.roster_id],
            wins=r.wins,
            losses=r.losses,
            ties=r.ties,
            points_for=round(r.points_for, 2),
            points_against=round(r.points_against, 2),
        )
        for i, r in enumerate(ordered, start=1)
    ]

    views = [
        RosterView(
            roster_id=r.roster_id,
            team=team[r.roster_id],
            owner_id=owners[r.roster_id],
            players=_roster_players(r, players, slots, games),
        )
        for r in sorted(rosters, key=lambda r: r.roster_id)
    ]
    return Dashboard(
        league_id=league.league_id,
        name=league.name,
        season=league.season,
        week=week,
        standings=standings,
        rosters=views,
    )


def _roster_players(
    roster: RosterRow,
    players: dict[str, PlayerRow],
    slots: list[str],
    games: dict[str, GameInfo],
) -> list[RosterPlayer]:
    def make(pid: str, status: Status, slot: str | None = None) -> RosterPlayer:
        name, position, nfl_team = _display(players, pid)
        return RosterPlayer(
            player_id=pid,
            name=name,
            position=position,
            team=nfl_team,
            status=status,
            slot=slot,
            game=games.get(nfl_team) if nfl_team else None,
            injury=_injury(players, pid),
        )

    out: list[RosterPlayer] = []
    for i, pid in enumerate(roster.starters):
        if pid != EMPTY_SLOT:
            out.append(make(pid, "starter", slots[i] if i < len(slots) else None))

    placed = set(roster.starters) | set(roster.reserve) | set(roster.taxi)
    bench = [make(pid, "bench") for pid in roster.players if pid not in placed]
    bench.sort(key=lambda p: (p.position or "~", p.name))
    out.extend(bench)
    out.extend(make(pid, "ir") for pid in roster.reserve)
    out.extend(make(pid, "taxi") for pid in roster.taxi)
    return out


def build_lineups(session: Session, league: LeagueRow, week: int | None = None) -> Lineups:
    """Both teams' lineups per matchup for one week.

    Default week: the current NFL week when known, otherwise the latest week with scores.
    Weeks after the current one are upcoming: pairings with each team's current starters.
    """
    rows = list(session.scalars(select(MatchupRow).where(MatchupRow.league_id == league.league_id)))
    weeks = sorted({m.week for m in rows})
    current = current_week(session, league.season)
    if week is None:
        if current in weeks:
            week = current
        else:
            scored = [w for w in weeks if any(m.points for m in rows if m.week == w)]
            candidates = scored or weeks
            week = candidates[-1] if candidates else None
    if week is None or week not in weeks:
        return Lineups(week=None, current_week=current, weeks=weeks, matchups=[])

    week_rows = [m for m in rows if m.week == week]
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    team = _team_names(session, rosters)
    owners = {r.roster_id: r.owner_id for r in rosters}
    players = _players(session, {pid for m in week_rows for pid in [*m.starters, *m.players]})
    slots = starter_slots(league)
    games = games_for_week(session, league.season, week)
    # IR and taxi come from the current roster (past weeks use today's IR list)
    parked = {
        r.roster_id: {**{pid: "IR" for pid in r.reserve}, **{pid: "TAXI" for pid in r.taxi}}
        for r in rosters
    }

    by_matchup: dict[int, list[TeamLineup]] = {}
    for m in sorted(week_rows, key=lambda m: m.roster_id):
        lineup = _team_lineup(m, team, owners, players, slots, games, parked.get(m.roster_id, {}))
        # a missing matchup_id (bye/unscheduled) must not group unrelated teams together
        key = m.matchup_id if m.matchup_id is not None else -m.roster_id
        by_matchup.setdefault(key, []).append(lineup)

    matchups = [
        MatchupView(matchup_id=key if key > 0 else None, teams=teams)
        for key, teams in sorted(by_matchup.items(), key=lambda kv: abs(kv[0]))
    ]
    return Lineups(week=week, current_week=current, weeks=weeks, matchups=matchups)


def _team_lineup(  # noqa: PLR0913, PLR0917
    m: MatchupRow,
    team: dict[int, str],
    owners: dict[int, str | None],
    players: dict[str, PlayerRow],
    slots: list[str],
    games: dict[str, GameInfo],
    parked: dict[str, str],
) -> TeamLineup:
    points: dict[str, Any] = m.players_points

    def pts(pid: str) -> float | None:
        value = points.get(pid)
        return None if value is None else float(value)

    starters: list[LineupPlayer] = []
    for i, pid in enumerate(m.starters):
        slot = slots[i] if i < len(slots) else "FLEX"
        if pid == EMPTY_SLOT:
            starters.append(
                LineupPlayer(
                    slot=slot, player_id=None, name="Empty", position=None, team=None, points=None
                )
            )
            continue
        name, position, nfl_team = _display(players, pid)
        value = m.starters_points[i] if i < len(m.starters_points) else pts(pid)
        starters.append(
            LineupPlayer(
                slot=slot,
                player_id=pid,
                name=name,
                position=position,
                team=nfl_team,
                points=None if value is None else float(value),
                game=games.get(nfl_team) if nfl_team else None,
                injury=_injury(players, pid),
            )
        )

    bench = []
    for pid in m.players:
        if pid in m.starters:
            continue
        name, position, nfl_team = _display(players, pid)
        bench.append(
            LineupPlayer(
                slot=parked.get(pid, "BN"),
                player_id=pid,
                name=name,
                position=position,
                team=nfl_team,
                points=pts(pid),
                game=games.get(nfl_team) if nfl_team else None,
                injury=_injury(players, pid),
            )
        )
    bench.sort(key=lambda p: (_PARKED_ORDER.get(p.slot, 0), -(p.points or 0.0), p.name))
    return TeamLineup(
        roster_id=m.roster_id,
        team=team.get(m.roster_id, f"Team {m.roster_id}"),
        owner_id=owners.get(m.roster_id),
        points=round(m.points, 2),
        starters=starters,
        bench=bench,
    )
