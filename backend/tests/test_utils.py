import math
from datetime import UTC, datetime, timedelta, timezone

from sleeper_assistant.utils.cache import VersionedCache
from sleeper_assistant.utils.clock import utc_iso
from sleeper_assistant.utils.parse import (
    clean_text,
    espn_team_code,
    finite_number,
    finite_numbers,
    int_or_none,
    rounded_percent,
    string_list,
)
from sleeper_assistant.utils.text import ordinal


def test_numbers_from_untrusted_json_never_raise() -> None:
    assert finite_number("12.5") == 12.5 and finite_number(3) == 3.0
    for bad in (True, None, "x", math.inf, float("nan"), [1], {}):
        assert finite_number(bad) is None
    assert finite_numbers({"a": 1, "b": None, "c": "2", "d": "x"}) == {"a": 1.0, "c": 2.0}


def test_ints_text_percents_and_lists() -> None:
    assert int_or_none("7") == 7 and int_or_none(None) is None and int_or_none("x") is None
    assert clean_text("  hi ") == "hi" and clean_text("   ") is None and clean_text(4) is None
    assert rounded_percent(12.3456) == 12.35 and rounded_percent(True) is None
    assert rounded_percent("5") is None
    assert string_list([1, "a"]) == ["1", "a"] and string_list("ab") == []


def test_ordinals() -> None:
    words = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 11: "11th", 12: "12th", 13: "13th"}
    words |= {21: "21st", 22: "22nd", 23: "23rd", 100: "100th", 101: "101st", 111: "111th"}
    for n, expected in words.items():
        assert ordinal(n) == expected


def test_times_end_in_z_whether_or_not_they_carry_a_zone() -> None:
    assert utc_iso(None) is None
    assert utc_iso(datetime(2026, 10, 18, 17, 0)) == "2026-10-18T17:00:00Z"
    eastern = timezone(timedelta(hours=-4))
    assert utc_iso(datetime(2026, 10, 18, 13, 0, tzinfo=eastern)) == "2026-10-18T17:00:00Z"
    assert utc_iso(datetime(2026, 10, 18, 17, 0, tzinfo=UTC)) == "2026-10-18T17:00:00Z"


def test_a_versioned_cache_rebuilds_only_when_the_version_changes() -> None:
    cache: VersionedCache[str, int] = VersionedCache()
    builds: list[int] = []

    def build() -> int:
        builds.append(1)
        return len(builds)

    assert cache.get("k", (1, 1), build) == 1
    assert cache.get("k", (1, 1), build) == 1
    assert cache.get("k", (2, 1), build) == 2
    assert cache.get("other", (2, 1), build) == 3
    cache.clear()
    assert cache.get("k", (2, 1), build) == 4


def test_espn_team_codes_use_sleepers_spelling() -> None:
    assert espn_team_code("WSH") == "WAS" and espn_team_code("KC") == "KC"
    assert espn_team_code("") is None and espn_team_code(None) is None
