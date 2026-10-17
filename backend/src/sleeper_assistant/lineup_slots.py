"""Which players can fill which lineup slots, and the best lineup a set of projections allows.

Used by the Start/Sit tool to suggest a lineup from projected points. Slots are filled most
restrictive first (QB, RB, WR, TE, K, DEF, then the flex slots from narrowest to widest), taking the
highest scorer who qualifies. That is exact whenever the flex slots nest, as FLEX inside SUPER_FLEX
does; leagues that mix REC_FLEX and WRRB_FLEX may be slightly off.
"""

from __future__ import annotations

NON_STARTER_SLOTS = frozenset({"BN", "IR", "TAXI"})  # bench, injured reserve and taxi squad

# which positions can fill a slot; a slot Sleeper adds later that we do not know counts as no slot
_ELIGIBLE: dict[str, frozenset[str]] = {
    "QB": frozenset({"QB"}),
    "RB": frozenset({"RB"}),
    "WR": frozenset({"WR"}),
    "TE": frozenset({"TE"}),
    "K": frozenset({"K"}),
    "DEF": frozenset({"DEF"}),
    "REC_FLEX": frozenset({"WR", "TE"}),
    "WRRB_FLEX": frozenset({"WR", "RB"}),
    "FLEX": frozenset({"RB", "WR", "TE"}),
    "SUPER_FLEX": frozenset({"QB", "RB", "WR", "TE"}),
}


def eligible_positions(slot: str, position: str) -> frozenset[str]:
    """The positions that can fill a slot; a slot we do not know takes just the player's own."""
    return _ELIGIBLE.get(slot, frozenset({position}))


def assign_lineup(
    slots: list[str], candidates: list[tuple[str, str, float]]
) -> list[tuple[str, str]]:
    """The best lineup as (slot, player_id) pairs, most restrictive slots filled first.

    ``candidates`` are (player_id, position, points). Slots nobody qualifies for stay empty.
    """
    order = sorted(
        ((i, s) for i, s in enumerate(slots) if s in _ELIGIBLE),
        key=lambda item: (len(_ELIGIBLE[item[1]]), item[0]),
    )
    taken: set[str] = set()
    pool = sorted(candidates, key=lambda c: -c[2])
    assigned: dict[int, tuple[str, str]] = {}
    for index, slot in order:
        for pid, position, _ in pool:
            if pid not in taken and position in _ELIGIBLE[slot]:
                taken.add(pid)
                assigned[index] = (slot, pid)
                break
    return [assigned[i] for i in sorted(assigned)]


def optimal_lineup(slots: list[str], candidates: list[tuple[str, str, float]]) -> list[str]:
    """Player ids of the best lineup, highest scorer first."""
    chosen = {pid for _, pid in assign_lineup(slots, candidates)}
    return [pid for pid, _, _ in sorted(candidates, key=lambda c: -c[2]) if pid in chosen]


def starter_slots(roster_positions: list[str]) -> list[str]:
    """Lineup slot labels in the order Sleeper lists a roster's starters (no bench, IR or taxi)."""
    return [p for p in roster_positions if p not in NON_STARTER_SLOTS]
