"""A cache for a table that is only rebuilt when the data behind it changes."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class VersionedCache(Generic[K, V]):  # noqa: UP046 - TypeVar form keeps the 3.12 target simple
    """Keeps one value per key and rebuilds it only when the key's version changes.

    The version is a cheap fingerprint of the data the value was built from (for example the
    number of completed games), so many requests share one expensive build.
    """

    def __init__(self) -> None:
        self._items: dict[K, tuple[Hashable, V]] = {}

    def get(self, key: K, version: Hashable, build: Callable[[], V]) -> V:
        cached = self._items.get(key)
        if cached is not None and cached[0] == version:
            return cached[1]
        value = build()
        self._items[key] = (version, value)
        return value

    def clear(self) -> None:
        self._items.clear()
