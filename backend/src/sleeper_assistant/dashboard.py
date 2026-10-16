"""Read models for the league dashboard: standings, rosters and weekly lineups."""

from __future__ import annotations

from datetime import UTC, datetime
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
    UserLeagueRow,
)
from sleeper_assistant.live import LiveGame, current_games, describe, fraction_elapsed
from sleeper_assistant.live import window_open as live_window_open
from sleeper_assistant.live_projection import live_projection
from sleeper_assistant.projections import projected_points
from sleeper_assistant.win_probability import StarterState, matchup_chances

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
    date: str | None = None  # ISO date
    kickoff: str | None = None  # ISO UTC timestamp, once the schedule publishes a time
    team: str | None = None  # the NFL team this game is for
    team_score: int | None = None  # live or final score, from this team's side
    opponent_score: int | None = None
    period_text: str | None = None  # where a live game is: "Q2 2:24", "Halftime"; "Final" when over
    elapsed: float | None = None  # share of the game played, 0 to 1; None when the clock is unknown
    opponent: str | None = None
    home: bool | None = None


class StandingsRow(BaseModel):
    rank: int
    roster_id: int
    team: str
    manager: str | None = None  # the manager's Sleeper username
    owner_id: str | None = None
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    streak: str | None = None  # e.g. "3W" (three straight wins) or "2L"


class RosterPlayer(BaseModel):
    player_id: str
    name: str
    position: str | None
    team: str | None
    status: Status
    slot: str | None  # lineup slot for starters, e.g. QB, RB, FLEX
    game: GameInfo | None = None  # this week's game (or bye) for the player's NFL team
    injury: InjuryInfo | None = None
    projected: float | None = (
        None  # this week, scored with the league's rules; None = no projection
    )
    points: float | None = None  # this week's actual points once the game has started
    projected_pregame: float | None = None  # the projection frozen before kickoff


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
    projected: float | None = None  # live: equals the score once the game is over
    projected_pregame: float | None = None  # the projection frozen before kickoff
    projection_missing: bool = False  # no projection was stored, so the 0 above is an assumption


class TeamLineup(BaseModel):
    roster_id: int
    team: str
    owner_id: str | None = None
    points: float
    projected: float | None = (
        None  # sum of the starters' live projections; None when there are none
    )
    projected_pregame: float | None = None  # the same, from the projections frozen before kickoff
    win_probability: float | None = (
        None  # chance to win from projections; None = nothing fair to say
    )
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


def _team_names(
    session: Session, rosters: list[RosterRow]
) -> tuple[dict[int, str], dict[int, str]]:
    """(roster_id -> team name, roster_id -> manager's username). The team name is what the
    manager chose in Sleeper, falling back to their username."""
    owner_ids = {r.owner_id for r in rosters if r.owner_id}
    league_ids = {r.league_id for r in rosters}
    managers = {
        u.user_id: u.display_name
        for u in session.scalars(
            select(SleeperUserRow).where(SleeperUserRow.user_id.in_(owner_ids))
        )
    }
    chosen = {
        link.user_id: link.team_name
        for link in session.scalars(
            select(UserLeagueRow).where(
                UserLeagueRow.user_id.in_(owner_ids), UserLeagueRow.league_id.in_(league_ids)
            )
        )
        if link.team_name
    }
    manager = {r.roster_id: managers.get(r.owner_id or "", f"Team {r.roster_id}") for r in rosters}
    team = {r.roster_id: chosen.get(r.owner_id or "", manager[r.roster_id]) for r in rosters}
    return team, manager


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


def _utc_iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    if moment.tzinfo is None:  # SQLite drops the zone; everything is stored as UTC
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _live_games(week_games: list[NflGameRow], week: int) -> dict[tuple[str, str], LiveGame]:
    """ESPN's live status for this week's games, only while a game could be on (else empty)."""
    in_progress = any(g.status == "in_game" for g in week_games)
    if not live_window_open([g.kickoff for g in week_games], in_progress):
        return {}
    return {(g.home, g.away): g for g in current_games() if g.week in (None, week)}


def games_for_week(session: Session, season: str, week: int) -> dict[str, GameInfo]:
    """NFL team -> that team's game in the week; teams with no game in the week are on a bye."""
    games = list(session.scalars(select(NflGameRow).where(NflGameRow.season == season)))
    all_teams = {g.home for g in games} | {g.away for g in games}
    week_games = [g for g in games if g.week == week]
    playing = {g.home for g in week_games} | {g.away for g in week_games}
    live_by_game = _live_games(week_games, week)
    out: dict[str, GameInfo] = {}
    for g in week_games:
        state = _STATUS_STATE.get(g.status)
        if state is None:
            continue
        kickoff = _utc_iso(g.kickoff)
        live = live_by_game.get((g.home, g.away))
        game_state = live.state if live else state  # ESPN is fresher than Sleeper's schedule
        home_score, away_score = (
            (live.home_score, live.away_score) if live else (g.home_score, g.away_score)
        )
        if game_state == "upcoming":
            home_score = away_score = None
        words = describe(live) if live else ("Final" if game_state == "final" else None)
        played = {"upcoming": 0.0, "final": 1.0}.get(game_state)
        if live is not None and game_state == "live":
            played = fraction_elapsed(live)
        out[g.home] = GameInfo(
            state=game_state, date=g.game_date, kickoff=kickoff, opponent=g.away, home=True,
            team=g.home, team_score=home_score, opponent_score=away_score, period_text=words,
            elapsed=played,
        )  # fmt: skip
        out[g.away] = GameInfo(
            state=game_state, date=g.game_date, kickoff=kickoff, opponent=g.home, home=False,
            team=g.away, team_score=away_score, opponent_score=home_score, period_text=words,
            elapsed=played,
        )  # fmt: skip
    if week_games:  # without any games in the week we cannot tell a bye from missing data
        for team in all_teams - playing:
            out[team] = GameInfo(state="bye")
    return out


def build_dashboard(session: Session, league: LeagueRow) -> Dashboard:
    rosters = list(
        session.scalars(select(RosterRow).where(RosterRow.league_id == league.league_id))
    )
    team, manager = _team_names(session, rosters)
    owners = {r.roster_id: r.owner_id for r in rosters}
    players = _players(session, {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]})
    slots = starter_slots(league)
    week = current_week(session, league.season)
    games = games_for_week(session, league.season, week) if week else {}
    projected = (
        projected_points(
            session,
            league.season,
            week,
            league.scoring_settings,
            {pid for r in rosters for pid in [*r.players, *r.reserve, *r.taxi]},
        )
        if week
        else {}
    )

    earned = _week_points(session, league.league_id, week) if week else {}

    ordered = sorted(rosters, key=lambda r: (-r.wins, r.losses, -r.ties, -r.points_for))
    standings = [
        StandingsRow(
            rank=i,
            roster_id=r.roster_id,
            team=team[r.roster_id],
            manager=manager[r.roster_id],
            owner_id=owners[r.roster_id],
            wins=r.wins,
            losses=r.losses,
            ties=r.ties,
            points_for=round(r.points_for, 2),
            points_against=round(r.points_against, 2),
            streak=r.streak,
        )
        for i, r in enumerate(ordered, start=1)
    ]

    views = [
        RosterView(
            roster_id=r.roster_id,
            team=team[r.roster_id],
            owner_id=owners[r.roster_id],
            players=_roster_players(
                r, players, slots, games, projected, earned.get(r.roster_id, {})
            ),
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


def _week_points(session: Session, league_id: str, week: int) -> dict[int, dict[str, float]]:
    """roster_id -> player_id -> the points Sleeper credited that roster's player this week."""
    out: dict[int, dict[str, float]] = {}
    for m in session.scalars(
        select(MatchupRow).where(MatchupRow.league_id == league_id, MatchupRow.week == week)
    ):
        out[m.roster_id] = {
            pid: float(value)
            for pid, value in (m.players_points or {}).items()
            if value is not None
        }
    return out


def _points_so_far(game: GameInfo | None, value: float | None) -> float | None:
    """A player's points once his game has started; before that there is nothing to show (not 0)."""
    if value is None or game is None or game.state not in ("live", "final"):
        return None
    return round(value, 2)


def _roster_players(  # noqa: PLR0913, PLR0917
    roster: RosterRow,
    players: dict[str, PlayerRow],
    slots: list[str],
    games: dict[str, GameInfo],
    projected: dict[str, float],
    earned: dict[str, float],
) -> list[RosterPlayer]:
    def make(pid: str, status: Status, slot: str | None = None) -> RosterPlayer:
        name, position, nfl_team = _display(players, pid)
        game = games.get(nfl_team) if nfl_team else None
        pregame = projected.get(pid, 0.0)
        scored = _points_so_far(game, earned.get(pid))
        return RosterPlayer(
            player_id=pid,
            name=name,
            position=position,
            team=nfl_team,
            status=status,
            slot=slot,
            game=game,
            injury=_injury(players, pid),
            projected=_live(pregame, scored, game),
            projected_pregame=pregame,
            points=scored,
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
    team, _ = _team_names(session, rosters)
    owners = {r.roster_id: r.owner_id for r in rosters}
    players = _players(session, {pid for m in week_rows for pid in [*m.starters, *m.players]})
    slots = starter_slots(league)
    games = games_for_week(session, league.season, week)
    projected = projected_points(
        session,
        league.season,
        week,
        league.scoring_settings,
        {pid for m in week_rows for pid in [*m.starters, *m.players]},
    )
    # IR and taxi come from the current roster (past weeks use today's IR list)
    parked = {
        r.roster_id: {**{pid: "IR" for pid in r.reserve}, **{pid: "TAXI" for pid in r.taxi}}
        for r in rosters
    }

    by_matchup: dict[int, list[TeamLineup]] = {}
    for m in sorted(week_rows, key=lambda m: m.roster_id):
        lineup = _team_lineup(
            m, team, owners, players, slots, games, parked.get(m.roster_id, {}), projected
        )
        # a missing matchup_id (bye/unscheduled) must not group unrelated teams together
        key = m.matchup_id if m.matchup_id is not None else -m.roster_id
        by_matchup.setdefault(key, []).append(lineup)

    for teams in by_matchup.values():
        if len(teams) == 2:  # noqa: PLR2004 - a matchup is two teams
            _set_win_probability(teams[0], teams[1])

    matchups = [
        MatchupView(matchup_id=key if key > 0 else None, teams=teams)
        for key, teams in sorted(by_matchup.items(), key=lambda kv: abs(kv[0]))
    ]
    return Lineups(week=week, current_week=current, weeks=weeks, matchups=matchups)


def _starter_states(team: TeamLineup) -> list[StarterState]:
    return [
        StarterState(
            p.game.state if p.game else None,
            p.points,
            None if p.projection_missing else p.projected,
            pregame=None if p.projection_missing else p.projected_pregame,
            elapsed=p.game.elapsed if p.game else None,
        )
        for p in team.starters
        if p.player_id is not None  # an empty slot scores nothing and projects nothing
    ]


def _set_win_probability(a: TeamLineup, b: TeamLineup) -> None:
    chances = matchup_chances(_starter_states(a), _starter_states(b))
    if chances is not None:
        a.win_probability, b.win_probability = chances


def _live(pregame: float, scored: float | None, game: GameInfo | None) -> float:
    """The projection now: the pre-game one before kickoff, the score once the game is over."""
    return live_projection(
        pregame, scored, game.state if game else None, game.elapsed if game else None
    )


def _team_projection(starters: list[LineupPlayer], *, pregame: bool = False) -> float | None:
    """Sum of the starters' projections, or None when no starter has one (never a misleading 0)."""
    values: list[float] = []
    for p in starters:
        value = p.projected_pregame if pregame else p.projected
        if value is not None:
            values.append(value)
    return round(sum(values), 2) if values else None


def _team_lineup(  # noqa: PLR0913, PLR0917
    m: MatchupRow,
    team: dict[int, str],
    owners: dict[int, str | None],
    players: dict[str, PlayerRow],
    slots: list[str],
    games: dict[str, GameInfo],
    parked: dict[str, str],
    projected: dict[str, float],
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
        game = games.get(nfl_team) if nfl_team else None
        pregame = projected.get(pid, 0.0)
        starters.append(
            LineupPlayer(
                slot=slot,
                player_id=pid,
                name=name,
                position=position,
                team=nfl_team,
                points=None if value is None else float(value),
                game=game,
                injury=_injury(players, pid),
                projected=_live(pregame, None if value is None else float(value), game),
                projected_pregame=pregame,
                projection_missing=pid not in projected,
            )
        )

    bench = []
    for pid in m.players:
        if pid in m.starters:
            continue
        name, position, nfl_team = _display(players, pid)
        game = games.get(nfl_team) if nfl_team else None
        pregame = projected.get(pid, 0.0)
        bench.append(
            LineupPlayer(
                slot=parked.get(pid, "BN"),
                player_id=pid,
                name=name,
                position=position,
                team=nfl_team,
                points=pts(pid),
                game=game,
                injury=_injury(players, pid),
                projected=_live(pregame, pts(pid), game),
                projected_pregame=pregame,
                projection_missing=pid not in projected,
            )
        )
    bench.sort(key=lambda p: (_PARKED_ORDER.get(p.slot, 0), -(p.points or 0.0), p.name))
    return TeamLineup(
        roster_id=m.roster_id,
        team=team.get(m.roster_id, f"Team {m.roster_id}"),
        owner_id=owners.get(m.roster_id),
        points=round(m.points, 2),
        projected=_team_projection(starters),
        projected_pregame=_team_projection(starters, pregame=True),
        starters=starters,
        bench=bench,
    )
