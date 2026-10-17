# ruff: noqa: E501
from sqlalchemy.orm import Session

from sleeper_assistant.db import LeagueRow, PlayerRow, RosterRow, SleeperUserRow, TransactionRow
from sleeper_assistant.views.transactions import build_transactions


def _tx(  # noqa: PLR0913, PLR0917

    tx_id: str, kind: str, created: int | None, adds: dict[str, int] | None = None,
    drops: dict[str, int] | None = None, status: str = "complete",
) -> TransactionRow:  # fmt: skip
    return TransactionRow(
        league_id="L1", transaction_id=tx_id, type=kind, status=status, week=3,
        created_ms=created, payload={"adds": adds, "drops": drops},
    )  # fmt: skip


def _setup(session: Session) -> LeagueRow:
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=2, scoring_settings={},
        roster_positions=[], settings={},
    )  # fmt: skip
    session.add(league)
    session.add_all(
        [
            SleeperUserRow(user_id="u1", username="cole", display_name="Cole"),
            SleeperUserRow(user_id="u2", username="dad", display_name="Dad"),
            RosterRow(league_id="L1", roster_id=1, owner_id="u1", players=[], starters=[]),
            RosterRow(league_id="L1", roster_id=2, owner_id="u2", players=[], starters=[]),
            PlayerRow(player_id="a", full_name="Q. Judkins", position="RB", team="CLE", external_ids={}),
            PlayerRow(player_id="b", full_name="Z. Charbonnet", position="RB", team="SEA", external_ids={}),
        ]
    )  # fmt: skip
    return league


def test_a_waiver_claim_shows_the_player_in_and_the_player_out_for_the_team(
    session: Session,
) -> None:
    league = _setup(session)
    session.add(_tx("w", "waiver", 1_760_000_000_000, adds={"a": 1}, drops={"b": 1}))
    session.commit()
    (item,) = build_transactions(session, league).transactions
    assert (item.kind, item.week) == ("waiver", 3)
    assert item.created_at is not None and item.created_at.year == 2025
    (move,) = item.moves
    assert (move.roster_id, move.manager) == (1, "Cole")
    assert [p.name for p in move.added] == ["Q. Judkins"]
    assert [(p.name, p.position, p.team) for p in move.dropped] == [("Z. Charbonnet", "RB", "SEA")]


def test_a_trade_lists_what_each_team_got_and_gave(session: Session) -> None:
    league = _setup(session)
    session.add(_tx("t", "trade", 2, adds={"a": 1, "b": 2}, drops={"a": 2, "b": 1}))
    session.commit()
    (item,) = build_transactions(session, league).transactions
    assert [(m.roster_id, [p.player_id for p in m.added], [p.player_id for p in m.dropped])
            for m in item.moves] == [(1, ["a"], ["b"]), (2, ["b"], ["a"])]  # fmt: skip


def test_newest_first_and_only_completed_known_moves_with_players(session: Session) -> None:
    league = _setup(session)
    session.add_all(
        [
            _tx("old", "free_agent", 1, adds={"a": 1}),
            _tx("new", "free_agent", 9, drops={"b": 2}),
            _tx("failed", "waiver", 20, adds={"a": 1}, status="failed"),
            _tx("odd", "mystery", 30, adds={"a": 1}),
            _tx("empty", "waiver", 40),  # no players (a draft pick or FAAB-only move)
            _tx("nodate", "waiver", None, adds={"a": 2}),
        ]
    )
    session.commit()
    ids = [t.transaction_id for t in build_transactions(session, league).transactions]
    assert ids == ["new", "old", "nodate"]  # a missing time sorts as the oldest


def test_an_unknown_player_and_roster_still_show(session: Session) -> None:
    league = _setup(session)
    session.add(_tx("x", "waiver", 5, adds={"zz": 9}))
    session.commit()
    (item,) = build_transactions(session, league).transactions
    move = item.moves[0]
    assert (move.team, move.manager) == ("Team 9", None)
    assert move.added[0].name == "zz"
