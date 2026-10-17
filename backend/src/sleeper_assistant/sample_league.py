"""A made-up league for looking at the app without Sleeper.

Load it with ``python -m sleeper_assistant.sample_league``.

Loads six fantasy teams, eight NFL teams and their players, a schedule with finished, live and
upcoming games, projections, past weeks' stats, a few alerts and the numbers the waiver page uses.
Every name is invented. The screenshots job and ``make preview-data`` use it, and a test calls every
league endpoint against it so the sample cannot drift from the real schema.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from sleeper_assistant.db import (
    AlertRow,
    LeagueRow,
    MatchupRow,
    NflGameRow,
    PlayerOwnershipRow,
    PlayerProjectionRow,
    PlayerRow,
    PlayerTrendRow,
    PlayerWeekStatsRow,
    RosterRow,
    SleeperUserRow,
    TeamDepthChartRow,
    UserLeagueRow,
    database_url,
    make_engine,
    make_session_factory,
)

LEAGUE_ID = "100001"
SEASON = "2026"
CURRENT_WEEK = 7
BYE_WEEK = 3  # one pair of teams is off this week, so a player's game log shows a bye
TEAMS = ["SF", "LAR", "DAL", "SEA", "WAS", "ARI", "KC", "BUF"]
SLOTS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "BN", "BN", "BN", "BN"]
SCORING = {
    "pass_yd": 0.04,
    "pass_td": 4.0,
    "pass_int": -2.0,
    "rush_yd": 0.1,
    "rush_td": 6.0,
    "rec": 1.0,
    "rec_yd": 0.1,
    "rec_td": 6.0,
    "fum_lost": -2.0,
    "fgm": 3.0,
    "xpm": 1.0,
    "sack": 1.0,
    "int": 2.0,
    "fum_rec": 2.0,
    "def_td": 6.0,
}
FIRST = [
    "Jayden",
    "Kyren",
    "Marcus",
    "Devon",
    "Tyrell",
    "Caleb",
    "Andre",
    "Malik",
    "Isaiah",
    "Cooper",
    "Trey",
    "Xavier",
    "Darnell",
    "Wesley",
    "Jalen",
    "Brock",
    "Elijah",
    "Nolan",
]
LAST = [
    "Daniels",
    "Williams",
    "Harrison",
    "Brooks",
    "Carter",
    "Whitfield",
    "Okafor",
    "Ramsey",
    "Lawson",
    "Pierce",
    "Sutton",
    "Hendricks",
    "Mallory",
    "Dixon",
    "Vega",
    "Castillo",
    "Boone",
    "Faulkner",
    "Gentry",
    "Holloway",
]
MANAGERS = [
    "Shough Around & Find Out",
    "Gridiron Gang",
    "Waiver Wolves",
    "Taco Tuesday",
    "Bench Warmers",
    "Dad Bods",
]
PER_TEAM = [("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("K", 1)]


def _stats(position: str, rng: random.Random, scale: float = 1.0) -> dict[str, float]:
    if position == "QB":
        return {
            "pass_cmp": 21 * scale,
            "pass_att": 33 * scale,
            "pass_yd": rng.uniform(190, 300) * scale,
            "pass_td": rng.uniform(1, 2.4) * scale,
            "pass_int": rng.uniform(0.3, 1) * scale,
            "rush_att": 4.0,
            "rush_yd": rng.uniform(8, 35) * scale,
        }
    if position == "RB":
        return {
            "rush_att": rng.uniform(10, 20) * scale,
            "rush_yd": rng.uniform(45, 95) * scale,
            "rush_td": rng.uniform(0.3, 0.9) * scale,
            "rec": rng.uniform(1.5, 4.5) * scale,
            "rec_tgt": 4.0,
            "rec_yd": rng.uniform(10, 38) * scale,
        }
    if position in ("WR", "TE"):
        return {
            "rec": rng.uniform(3, 7) * scale,
            "rec_tgt": rng.uniform(5, 10) * scale,
            "rec_yd": rng.uniform(35, 85) * scale,
            "rec_td": rng.uniform(0.2, 0.7) * scale,
        }
    if position == "K":
        return {
            "fgm": rng.uniform(1.3, 2.2) * scale,
            "fga": 2.2,
            "xpm": rng.uniform(1.5, 3) * scale,
        }
    return {
        "sack": rng.uniform(1.5, 3.5) * scale,
        "int": rng.uniform(0.4, 1.0) * scale,
        "fum_rec": 0.4,
        "pts_allow": rng.uniform(15, 28),
    }


def _players(rng: random.Random) -> list[PlayerRow]:
    names = [f"{f} {last}" for f in FIRST for last in LAST]
    rng.shuffle(names)
    players: list[PlayerRow] = []
    n = 0
    for team in TEAMS:
        for position, count in PER_TEAM:
            for _ in range(count + (2 if position in ("RB", "WR") else 0)):
                n += 1
                players.append(
                    PlayerRow(
                        player_id=f"s{n}",
                        full_name=names[n],
                        position=position,
                        team=team,
                        status="Active",
                        external_ids={},
                        bio={},
                    )
                )
        n += 1
        players.append(
            PlayerRow(
                player_id=team,
                full_name=f"{team} defense",
                position="DEF",
                team=team,
                status="Active",
                external_ids={},
                bio={},
            )
        )
    return players


def _depth_charts(session: Session, players: list[PlayerRow], now: datetime) -> None:
    """A simple depth chart per team: its QBs, RBs, WRs (split over three slots) and TEs."""
    for team in TEAMS:
        mine = [p for p in players if p.team == team]
        by_pos = {pos: [p for p in mine if p.position == pos] for pos in ("QB", "RB", "WR", "TE")}
        wrs = by_pos["WR"]

        def entry(p: PlayerRow) -> dict[str, str]:
            return {"name": p.full_name or "", "sleeper_id": p.player_id}

        slots = {
            "qb": by_pos["QB"],
            "rb": by_pos["RB"],
            "wr1": wrs[0::3],
            "wr2": wrs[1::3],
            "wr3": wrs[2::3],
            "te": by_pos["TE"],
        }
        chart = {"offense": {k: [entry(p) for p in v] for k, v in slots.items() if v}}
        session.add(TeamDepthChartRow(team=team, source="Sample", chart=chart, fetched_at=now))


def _draft(players: list[PlayerRow], rng: random.Random) -> list[list[PlayerRow]]:
    """Deal each fantasy team a roster that can fill the starting slots."""
    pools: dict[str, list[PlayerRow]] = {}
    for p in players:
        pools.setdefault(p.position or "", []).append(p)
    for pool in pools.values():
        rng.shuffle(pool)
    wants = {"QB": 1, "RB": 4, "WR": 5, "TE": 1, "K": 1, "DEF": 1}
    rosters: list[list[PlayerRow]] = [[] for _ in MANAGERS]
    for position, per_team in wants.items():
        for i in range(len(MANAGERS)):
            for _ in range(per_team):
                if pools[position]:
                    rosters[i].append(pools[position].pop())
    return rosters


def _starters(roster: list[PlayerRow]) -> list[str]:
    taken: set[str] = set()
    out: list[str] = []
    for slot in SLOTS[:9]:
        allowed = {"FLEX": {"RB", "WR", "TE"}}.get(slot, {slot})
        pick = next((p for p in roster if p.position in allowed and p.player_id not in taken), None)
        out.append(pick.player_id if pick else "0")
        if pick:
            taken.add(pick.player_id)
    return out


def seed(session: Session) -> None:
    """Fill an empty (migrated) database with the sample league."""
    rng = random.Random(7)
    now = datetime.now(UTC)
    players = _players(rng)
    session.add_all(players)
    _depth_charts(session, players, now)
    rosters = _draft(players, rng)
    free_agents = {p.player_id for p in players} - {p.player_id for r in rosters for p in r}

    session.add(
        LeagueRow(
            league_id=LEAGUE_ID,
            name="Sample League (made-up data)",
            season=SEASON,
            total_rosters=len(MANAGERS),
            scoring_settings=SCORING,
            roster_positions=SLOTS,
            settings={
                "waiver_day_of_week": 2,
                "waiver_type": 0,
                "trade_deadline": 11,
                "playoff_teams": 4,
                "playoff_week_start": 15,
                "num_teams": len(MANAGERS),
            },
            last_synced_at=now,
            last_viewed_at=now,
        )
    )
    for i in range(len(MANAGERS)):
        session.add(
            SleeperUserRow(user_id=f"u{i}", username=f"manager{i}", display_name=f"Manager {i}")
        )
    session.flush()
    for i, name in enumerate(MANAGERS):
        session.add(UserLeagueRow(user_id=f"u{i}", league_id=LEAGUE_ID, team_name=name))

    for i, roster in enumerate(rosters):
        session.add(
            RosterRow(
                league_id=LEAGUE_ID,
                roster_id=i + 1,
                owner_id=f"u{i}",
                players=[p.player_id for p in roster],
                starters=_starters(roster),
                reserve=[],
                taxi=[],
                wins=0,
                losses=0,
                ties=0,
                points_for=0.0,
                points_against=0.0,
            )
        )

    _schedule(session, now)
    _scores(session, players, rosters, rng)
    _projections(session, players, rng)
    _waiver_data(session, free_agents, now, rng)
    _alerts(session, rosters, now)
    session.commit()


def _round(week: int) -> list[tuple[str, str]]:
    """Who plays whom in a week: the teams rotate each week, and week 3 leaves one pair on a bye."""
    others = TEAMS[1:]
    shift = week % len(others)
    ring = [TEAMS[0], *others[shift:], *others[:shift]]
    games = [(ring[i], ring[len(ring) - 1 - i]) for i in range(len(ring) // 2)]
    return games[:3] if week == BYE_WEEK else games


def _schedule(session: Session, now: datetime) -> None:
    # weeks 1-6 are over; week 7 has a finished, a live and an upcoming game; KC and BUF have a bye
    pairs = [("SF", "LAR"), ("DAL", "SEA"), ("WAS", "ARI"), ("KC", "BUF")]
    for week in range(1, CURRENT_WEEK + 3):
        games = pairs[:3] if week == CURRENT_WEEK else _round(week)
        for j, (home, away) in enumerate(games):
            # week 7 is this week, so a live or upcoming game is never months in the past
            day = now + timedelta(days=7 * (week - CURRENT_WEEK) + j % 3 - 1)
            status = "complete" if week < CURRENT_WEEK else "pre_game"
            if week == CURRENT_WEEK:
                status = ["complete", "in_game", "pre_game"][j]
            done = status == "complete"
            session.add(
                NflGameRow(
                    game_id=f"w{week}g{j}",
                    season=SEASON,
                    week=week,
                    home=home,
                    away=away,
                    game_date=day.date().isoformat(),
                    status=status,
                    kickoff=day.replace(hour=17),
                    home_score=17 + (week * 3 + j * 5) % 14 if done else None,
                    away_score=14 + (week * 5 + j * 3) % 14 if done else None,
                    roof="outdoors",
                    surface="grass",
                    temp=64,
                    wind=7,
                    spread_line=-2.5,
                    total_line=45.5,
                )
            )


def _scores(
    session: Session, players: list[PlayerRow], rosters: list[list[PlayerRow]], rng: random.Random
) -> None:
    by_id = {p.player_id: p for p in players}
    wins = [0] * len(rosters)
    losses = [0] * len(rosters)
    totals = [0.0] * len(rosters)
    against = [0.0] * len(rosters)
    for week in range(1, CURRENT_WEEK + 1):
        scored: dict[int, tuple[list[str], list[float]]] = {}
        for i, roster in enumerate(rosters):
            starters = _starters(roster)
            pts = [round(rng.uniform(4, 24), 2) if week < CURRENT_WEEK else 0.0 for _ in starters]
            scored[i] = (starters, pts)
            if week < CURRENT_WEEK:
                for pid in starters:
                    if pid in by_id:
                        stats = _stats(by_id[pid].position or "", rng)
                        session.merge(
                            PlayerWeekStatsRow(
                                season=SEASON,
                                week=week,
                                player_id=pid,
                                team=by_id[pid].team,
                                stats={"gp": 1, **stats},
                                fetched_at=datetime.now(UTC),
                            )
                        )
        for a in range(0, len(rosters), 2):
            for me, other in ((a, a + 1), (a + 1, a)):
                starters, pts = scored[me]
                session.add(
                    MatchupRow(
                        league_id=LEAGUE_ID,
                        week=week,
                        roster_id=me + 1,
                        matchup_id=a // 2 + 1,
                        points=round(sum(pts), 2),
                        starters=starters,
                        starters_points=pts,
                        players=[p.player_id for p in rosters[me]],
                        players_points={},
                    )
                )
                if week < CURRENT_WEEK:
                    mine, theirs = sum(pts), sum(scored[other][1])
                    totals[me] += mine
                    against[me] += theirs
                    wins[me] += mine > theirs
                    losses[me] += mine < theirs
    for i in range(len(rosters)):
        row = session.get(RosterRow, (LEAGUE_ID, i + 1))
        assert row is not None
        row.wins, row.losses = wins[i], losses[i]
        row.points_for, row.points_against = round(totals[i], 2), round(against[i], 2)


def _projections(session: Session, players: list[PlayerRow], rng: random.Random) -> None:
    for week in (CURRENT_WEEK, CURRENT_WEEK + 1, CURRENT_WEEK + 2):
        for p in players:
            session.add(
                PlayerProjectionRow(
                    season=SEASON,
                    week=week,
                    player_id=p.player_id,
                    team=p.team,
                    stats=_stats(p.position or "", rng, rng.uniform(0.7, 1.15)),
                    fetched_at=datetime.now(UTC),
                )
            )


def _waiver_data(
    session: Session, free_agents: set[str], now: datetime, rng: random.Random
) -> None:
    for pid in sorted(free_agents):
        session.add(
            PlayerOwnershipRow(
                player_id=pid,
                owned=round(rng.uniform(2, 55), 1),
                started=round(rng.uniform(0, 25), 1),
                fetched_at=now,
            )
        )
        session.add(
            PlayerTrendRow(
                player_id=pid,
                adds=rng.randint(50, 9000),
                drops=rng.randint(10, 900),
                fetched_at=now,
            )
        )


def _alerts(session: Session, rosters: list[list[PlayerRow]], now: datetime) -> None:
    first = rosters[0][0]
    session.add(
        AlertRow(
            league_id=LEAGUE_ID,
            roster_id=1,
            kind="injury_out",
            dedupe_key=f"injury_out:{first.player_id}:sample",
            player_id=first.player_id,
            title=f"{first.full_name} ({first.position}, {first.team}) was ruled out",
            why="He starts for you in week 7. Best replacement on your bench: sample numbers.",
            data={"week": CURRENT_WEEK},
            created_at=now - timedelta(hours=3),
        )
    )


def main() -> None:
    url = database_url()
    if not url.startswith("sqlite"):
        raise SystemExit("the sample league only loads into a SQLite database, never a shared one")
    engine = make_engine(url)
    with make_session_factory(engine)() as session:
        if session.get(LeagueRow, LEAGUE_ID) is not None:
            print(f"league {LEAGUE_ID} is already loaded")
            return
        seed(session)
    print(f"loaded the sample league {LEAGUE_ID}")


if __name__ == "__main__":
    main()
