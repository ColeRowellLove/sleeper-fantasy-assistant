"""A one-line summary of how a player did in a game: ``18 car, 92 yds, 1 TD · 3 rec, 21 yds``.

Built from the week's stored stat line. Only categories that count in the league's scoring are
named (a league that does not score fumbles never shows them), plus the volume numbers that give
them meaning (carries, attempts). Groups run in the order that suits the position: a quarterback's
passing first, a back's rushing first, a receiver's catches first.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import PlayerProjectionRow, PlayerWeekStatsRow

# which group leads for a position; the rest follow when the player has numbers in them
_ORDER = {
    "QB": ("passing", "rushing", "receiving"),
    "RB": ("rushing", "receiving", "passing"),
    "WR": ("receiving", "rushing", "passing"),
    "TE": ("receiving", "rushing", "passing"),
}
_MIN_PAIR = 2


def _n(stats: Mapping[str, float], key: str) -> float:
    return float(stats.get(key) or 0.0)


def _count(value: float, *, tenths: bool = False) -> str:
    """A whole number; a projection's small counts (touchdowns, interceptions) keep a decimal."""
    return f"{value:.1f}" if tenths else str(round(value))


def _scores(scoring: Mapping[str, float], *keys: str) -> bool:
    return any(scoring.get(k) for k in keys)


def _passing(
    stats: Mapping[str, float], scoring: Mapping[str, float], *, proj: bool = False
) -> str:
    att = _n(stats, "pass_att")
    if not att and not _n(stats, "pass_yd"):
        return ""
    parts = [f"{_count(_n(stats, 'pass_cmp'))}/{_count(att)}"]
    if _scores(scoring, "pass_yd", "pass_cmp"):
        parts.append(f"{_count(_n(stats, 'pass_yd'))} yds")
    if _n(stats, "pass_td") and _scores(scoring, "pass_td"):
        parts.append(f"{_count(_n(stats, 'pass_td'), tenths=proj)} TD")
    if _n(stats, "pass_int") and _scores(scoring, "pass_int"):
        parts.append(f"{_count(_n(stats, 'pass_int'), tenths=proj)} INT")
    return ", ".join(parts)


def _rushing(
    stats: Mapping[str, float], scoring: Mapping[str, float], *, proj: bool = False
) -> str:
    car = _n(stats, "rush_att")
    if not car and not _n(stats, "rush_yd"):
        return ""
    parts = [f"{_count(car)} car"]
    if _scores(scoring, "rush_yd"):
        parts.append(f"{_count(_n(stats, 'rush_yd'))} yds")
    if _n(stats, "rush_td") and _scores(scoring, "rush_td"):
        parts.append(f"{_count(_n(stats, 'rush_td'), tenths=proj)} TD")
    return ", ".join(parts)


def _receiving(
    stats: Mapping[str, float], scoring: Mapping[str, float], *, proj: bool = False
) -> str:
    rec, tgt = _n(stats, "rec"), _n(stats, "rec_tgt")
    if not rec and not tgt and not _n(stats, "rec_yd"):
        return ""
    parts = [f"{_count(rec)} rec" + (f" on {_count(tgt)} tgt" if tgt else "")]
    if _scores(scoring, "rec_yd"):
        parts.append(f"{_count(_n(stats, 'rec_yd'))} yds")
    if _n(stats, "rec_td") and _scores(scoring, "rec_td"):
        parts.append(f"{_count(_n(stats, 'rec_td'), tenths=proj)} TD")
    return ", ".join(parts)


def _kicker(stats: Mapping[str, float], scoring: Mapping[str, float], *, proj: bool = False) -> str:
    fga, fgm, xpm = _n(stats, "fga"), _n(stats, "fgm"), _n(stats, "xpm")
    parts = []
    if fga or fgm:
        parts.append(f"{_count(fgm)}/{_count(fga)} FG")
    if xpm and _scores(scoring, "xpm"):
        parts.append(f"{_count(xpm, tenths=proj)} XP")
    return ", ".join(parts)


def _defense(
    stats: Mapping[str, float], scoring: Mapping[str, float], *, proj: bool = False
) -> str:
    parts = []
    for key, label in (("sack", "sack"), ("int", "INT"), ("fum_rec", "FR"), ("def_td", "TD")):
        if _n(stats, key) and _scores(scoring, key):
            parts.append(f"{_count(_n(stats, key), tenths=proj)} {label}")
    if "pts_allow" in stats:
        parts.append(f"{_count(_n(stats, 'pts_allow'))} pts allowed")
    return ", ".join(parts)


def stat_line(
    position: str | None,
    stats: Mapping[str, float],
    scoring: Mapping[str, float],
    *,
    proj: bool = False,
) -> str | None:
    """The summary for one player's game, or None when there is nothing to say.

    With ``proj`` the stats are a projection, so the small counts keep a decimal (1.6 TD)."""
    if position == "K":
        text = _kicker(stats, scoring, proj=proj)
    elif position == "DEF":
        text = _defense(stats, scoring, proj=proj)
    else:
        groups = {"passing": _passing, "rushing": _rushing, "receiving": _receiving}
        order = _ORDER.get(position or "", _ORDER["RB"])
        pieces = [groups[g](stats, scoring, proj=proj) for g in order]
        lost = _n(stats, "fum_lost")
        if lost and _scores(scoring, "fum_lost"):
            pieces.append(f"{_count(lost, tenths=proj)} FL")
        text = " · ".join(p for p in pieces if p)
    return text or None


def week_stat_lines(
    session: Session,
    season: str,
    week: int,
    players: Mapping[str, str | None],
    scoring: Mapping[str, float],
) -> dict[str, str]:
    """player_id -> summary for the week, for the given {player_id: position} players."""
    if not players:
        return {}
    out: dict[str, str] = {}
    for row in session.scalars(
        select(PlayerWeekStatsRow).where(
            PlayerWeekStatsRow.season == season,
            PlayerWeekStatsRow.week == week,
            PlayerWeekStatsRow.player_id.in_(set(players)),
        )
    ):
        if row.stats.get("gp") is not None and row.stats["gp"] <= 0:
            continue  # he did not play
        line = stat_line(players[row.player_id], row.stats, scoring)
        if line:
            out[row.player_id] = line
    return out


def projected_stat_lines(
    session: Session,
    season: str,
    week: int,
    players: Mapping[str, str | None],
    scoring: Mapping[str, float],
) -> dict[str, str]:
    """player_id -> what he is projected to do, for players whose game has not started."""
    if not players:
        return {}
    out: dict[str, str] = {}
    for row in session.scalars(
        select(PlayerProjectionRow).where(
            PlayerProjectionRow.season == season,
            PlayerProjectionRow.week == week,
            PlayerProjectionRow.player_id.in_(set(players)),
        )
    ):
        line = stat_line(players[row.player_id], row.stats, scoring, proj=True)
        if line:
            out[row.player_id] = line
    return out
