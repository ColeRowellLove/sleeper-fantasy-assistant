from datetime import UTC, datetime

from sqlalchemy.orm import Session

from sleeper_assistant.db import LeagueRow, RosterRow, SleeperUserRow, TransactionRow
from sleeper_assistant.sources.sleeper import SleeperTransaction
from sleeper_assistant.views.player_history import build_history, transaction_date


def _ms(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, 12, tzinfo=UTC).timestamp() * 1000)


def _tx(  # noqa: PLR0913, PLR0917
    tx_id: str, kind: str, created: int, adds: dict[str, int] | None = None,
    drops: dict[str, int] | None = None, status: str = "complete",
) -> TransactionRow:  # fmt: skip
    return TransactionRow(
        league_id="L1", transaction_id=tx_id, type=kind, status=status, week=1,
        created_ms=created, payload={"adds": adds, "drops": drops},
    )  # fmt: skip


def _setup(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="Family", season="2026", total_rosters=2,
        scoring_settings={}, roster_positions=[], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            SleeperUserRow(user_id="u1", username="cole", display_name="Cole"),
            SleeperUserRow(user_id="u2", username=None, display_name="Dad"),
            RosterRow(league_id="L1", roster_id=1, owner_id="u1", players=[], starters=[]),
            RosterRow(league_id="L1", roster_id=2, owner_id="u2", players=[], starters=[]),
        ]
    )
    return league


def test_the_transaction_keeps_who_got_and_who_lost_the_player() -> None:
    tx = SleeperTransaction.model_validate(
        {
            "transaction_id": "t",
            "type": "trade",
            "status": "complete",
            "leg": 2,
            "adds": {"p1": 1},
            "drops": {"p1": 2},
        }
    )
    assert tx.adds == {"p1": 1} and tx.drops == {"p1": 2}


def test_lists_his_adds_and_drops_newest_first_with_who_and_how(session: Session) -> None:
    league = _setup(session)
    session.add_all(
        [
            _tx("a", "waiver", _ms(2026, 10, 6), adds={"p1": 1}),
            _tx("b", "free_agent", _ms(2026, 10, 8), drops={"p1": 1}),
            _tx("c", "trade", _ms(2026, 10, 10), adds={"p1": 2}, drops={"p1": 1}),
            _tx("d", "waiver", _ms(2026, 10, 11), adds={"other": 2}),  # another player
            _tx("e", "waiver", _ms(2026, 10, 12), adds={"p1": 2}, status="failed"),
            _tx("f", "mystery", _ms(2026, 10, 13), adds={"p1": 2}),  # a type we do not know
        ]
    )
    session.commit()
    events = build_history(session, league, "p1")
    assert [(e.kind, e.source, e.manager, e.date) for e in events] == [
        ("added", "trade", "Dad", "2026-10-10"),
        ("dropped", "trade", "cole", "2026-10-10"),
        ("dropped", "free_agency", "cole", "2026-10-08"),
        ("added", "waivers", "cole", "2026-10-06"),
    ]


def test_a_player_nobody_moved_has_no_history(session: Session) -> None:
    league = _setup(session)
    session.commit()
    assert build_history(session, league, "p1") == []


def test_an_unknown_roster_has_no_manager(session: Session) -> None:
    league = _setup(session)
    session.add(_tx("a", "waiver", _ms(2026, 10, 6), adds={"p1": 9}))
    session.commit()
    assert [(e.manager, e.date) for e in build_history(session, league, "p1")] == [
        (None, "2026-10-06")
    ]


def test_a_missing_time_gives_no_date() -> None:
    assert transaction_date(None) is None
