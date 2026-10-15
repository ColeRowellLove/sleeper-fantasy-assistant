"""Player ID crosswalk: Sleeper id <-> nflverse gsis / ESPN / Yahoo / Sportradar / etc.

v1 is built from the external ids Sleeper's player DB carries. Later sources (nflverse ID map,
FantasyPros, FantasyCalc) add ids through :func:`link`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.db import CrosswalkRow, PlayerRow

# source name -> CrosswalkRow column
SOURCE_COLUMNS = {
    "gsis": "gsis_id",
    "espn": "espn_id",
    "yahoo": "yahoo_id",
    "sportradar": "sportradar_id",
    "fantasypros": "fantasypros_id",
    "fantasycalc": "fantasycalc_id",
}
# Sources whose ids come from Sleeper's own player DB (rebuilt every time, may be cleared).
SLEEPER_SOURCES = ("gsis", "espn", "yahoo", "sportradar")

# Positions that matter for fantasy; others (OL, LB, ...) are not expected to match.
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
# Kickers and defenses have no gsis id in Sleeper's data; only skill positions must have one,
# and only those count toward the match rate.
REQUIRE_GSIS = {"QB", "RB", "WR", "TE"}


def _column(source: str) -> str:
    try:
        return SOURCE_COLUMNS[source]
    except KeyError:
        valid = ", ".join(sorted(SOURCE_COLUMNS))
        raise ValueError(f"unknown crosswalk source {source!r}; expected one of: {valid}") from None


@dataclass
class CrosswalkReport:
    total: int = 0  # skill-position players that should have a gsis id
    matched: int = 0
    unmatched: list[str] = field(default_factory=list)  # Sleeper ids

    @property
    def match_rate(self) -> float:
        return self.matched / self.total if self.total else 1.0


def build_crosswalk(session: Session) -> CrosswalkReport:
    """Rebuild crosswalk rows from the players table and report unmatched skill players.

    Includes every fantasy-position player on an NFL team (any status, so IR and practice-squad
    players resolve). Sleeper-sourced ids are overwritten, including cleared; ids added by other
    sources (fantasypros/fantasycalc) are kept.
    """
    report = CrosswalkReport()
    existing = {row.player_id: row for row in session.scalars(select(CrosswalkRow))}
    for player in session.scalars(select(PlayerRow)):
        if player.position not in FANTASY_POSITIONS or player.team is None:
            continue
        row = existing.get(player.player_id)
        if row is None:
            row = CrosswalkRow(player_id=player.player_id)
            session.add(row)
        for source in SLEEPER_SOURCES:
            value = player.external_ids.get(source)
            setattr(row, SOURCE_COLUMNS[source], None if value is None else str(value))

        if player.position in REQUIRE_GSIS:
            report.total += 1
            if row.gsis_id:
                report.matched += 1
            else:
                report.unmatched.append(player.player_id)
    session.commit()
    return report


def link(
    session: Session, player_id: str, source: str, external_id: str, *, commit: bool = True
) -> None:
    """Attach another source's id to a player (used by later ingest jobs).

    Pass ``commit=False`` when linking in bulk and commit once at the end.
    """
    column = _column(source)
    row = session.get(CrosswalkRow, player_id)
    if row is None:
        row = CrosswalkRow(player_id=player_id)
        session.add(row)
    setattr(row, column, external_id)
    if commit:
        session.commit()


def resolve(session: Session, source: str, external_id: str) -> str | None:
    """Return the Sleeper player id for another source's id, or None.

    If several players share the id (bad source data) the lowest Sleeper id wins, deterministically.
    """
    column = getattr(CrosswalkRow, _column(source))
    return session.scalar(
        select(CrosswalkRow.player_id)
        .where(column == str(external_id))
        .order_by(CrosswalkRow.player_id)
        .limit(1)
    )
