"""NFL news from public RSS feeds: headline, source, time and a link back, never article text.

Feeds are unofficial in the sense that their layout can change, so every parser failure raises and
the caller keeps the other feeds going. Only http(s) links are kept. Which feeds are read is set by
the ``NEWS_FEEDS`` environment variable (``name|url`` pairs separated by commas); the defaults are
the NFL headline feeds of ESPN and CBS Sports.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import NamedTuple
from xml.etree import ElementTree

import httpx

from sleeper_assistant.settings import load_settings

DEFAULT_FEEDS: tuple[tuple[str, str], ...] = (
    ("ESPN", "https://www.espn.com/espn/rss/nfl/news"),
    ("CBS Sports", "https://www.cbssports.com/rss/headlines/nfl/"),
)
MAX_BYTES = 2_000_000
MAX_TITLE = 280
USER_AGENT = "sleeper-assistant/0.1 (headline reader; links back to the source)"
_ATOM = "{http://www.w3.org/2005/Atom}"


class FeedError(ValueError):
    """A feed that is not the RSS or Atom we expect (or is unsafe to parse)."""


class NewsEntry(NamedTuple):
    source: str
    title: str
    link: str
    published: datetime | None


def configured_feeds() -> list[tuple[str, str]]:
    """The feeds to read: ``NEWS_FEEDS`` (``name|url,name|url``) or the defaults."""
    raw = load_settings().news_feeds
    if not raw:
        return list(DEFAULT_FEEDS)
    feeds: list[tuple[str, str]] = []
    for part in raw.split(","):
        name, _, url = part.partition("|")
        if name.strip() and url.strip().startswith(("https://", "http://")):
            feeds.append((name.strip(), url.strip()))
    return feeds


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()[:MAX_TITLE]


def _when(text: str | None) -> datetime | None:
    if not text or not text.strip():
        return None
    try:
        parsed = parsedate_to_datetime(text.strip())
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_feed(xml_text: str, source: str) -> list[NewsEntry]:
    """The entries of an RSS 2.0 or Atom feed; entries without a title or a web link are skipped."""
    prolog = re.split(r"<(?:rss|feed|rdf)\b", xml_text, maxsplit=1, flags=re.I)[0].upper()
    if "<!DOCTYPE" in prolog or "<!ENTITY" in prolog:  # only the prolog can declare entities
        raise FeedError(f"{source}: feeds with a DOCTYPE or entities are not read")
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        raise FeedError(f"{source}: not valid XML ({error})") from error
    entries: list[NewsEntry] = []
    items = root.findall(".//item") or root.findall(f".//{_ATOM}entry")
    if not items and root.tag not in {"rss", f"{_ATOM}feed", "feed"}:
        raise FeedError(f"{source}: not an RSS or Atom feed")
    for item in items:
        title = _clean(item.findtext("title") or item.findtext(f"{_ATOM}title"))
        link = (item.findtext("link") or "").strip()
        if not link:
            links = item.findall(f"{_ATOM}link")
            own = [x for x in links if x.get("rel", "alternate") == "alternate"]
            chosen = (own or links)[:1]
            link = (chosen[0].get("href") or "").strip() if chosen else ""
        published = _when(
            item.findtext("pubDate") or item.findtext(f"{_ATOM}updated")
            or item.findtext(f"{_ATOM}published")
        )  # fmt: skip
        if title and link.startswith(("https://", "http://")):
            entries.append(NewsEntry(source, title, link, published))
    return entries


def fetch_feed(http: httpx.Client, source: str, url: str) -> list[NewsEntry]:
    """Download and parse one feed (raises on HTTP errors, oversize bodies and bad XML)."""
    with http.stream(
        "GET", url, timeout=20.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as response:
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > MAX_BYTES:  # stop reading, never buffer an endless feed
                raise FeedError(f"{source}: the feed is larger than {MAX_BYTES} bytes")
        encoding = response.encoding or "utf-8"
    return parse_feed(bytes(body).decode(encoding, errors="replace"), source)
