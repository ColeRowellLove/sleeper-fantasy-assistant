from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sleeper_assistant.core.sources.news_feed import (
    FeedError,
    configured_feeds,
    fetch_feed,
    parse_feed,
)
from sleeper_assistant.db import LeagueRow, NewsItemRow, PlayerRow, RosterRow
from sleeper_assistant.sync.news_sync import match_entry, name_index, sync_news
from sleeper_assistant.views.news import build_news, player_news

FIXTURE = (Path(__file__).parent / "fixtures" / "news_rss_sample.xml").read_text()


def _player(pid: str, name: str, position: str, team: str) -> PlayerRow:
    return PlayerRow(player_id=pid, full_name=name, position=position, team=team, external_ids={})


def test_a_feed_gives_titles_links_and_times_never_the_article() -> None:
    entries = parse_feed(FIXTURE, "Test")
    assert [e.title for e in entries] == [
        "Commanders QB Jayden Daniels questionable with a knee injury",
        "Texans sign a punter",
    ]
    assert entries[0].published is not None and entries[0].published.year == 2026
    assert entries[1].published is None  # a bad date is dropped, the item stays
    assert not hasattr(entries[0], "description")


def test_atom_feeds_are_read_too() -> None:
    atom = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Hi</title>'
        '<link href="https://x.test/a"/><updated>2026-10-17T10:00:00Z</updated></entry></feed>'
    )
    (entry,) = parse_feed(atom, "A")
    assert (entry.link, entry.published is not None) == ("https://x.test/a", True)


def test_feeds_with_entities_or_bad_xml_are_refused() -> None:
    with pytest.raises(FeedError):
        parse_feed('<!DOCTYPE x [<!ENTITY a "b">]><rss/>', "X")
    with pytest.raises(FeedError):
        parse_feed("<rss><oops", "X")


def test_feeds_can_be_set_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEWS_FEEDS", "One|https://a.test/rss, bad|ftp://x ,Two|https://b.test/rss")
    assert configured_feeds() == [("One", "https://a.test/rss"), ("Two", "https://b.test/rss")]


def test_headlines_are_matched_to_players_teams_and_topics(session: Session) -> None:
    session.add_all(
        [_player("p1", "Jayden Daniels", "QB", "WAS"), _player("p2", "Sam Smith", "WR", "NYJ")]
    )
    session.commit()
    index = name_index(session)
    players, teams, topics = match_entry(
        "Commanders QB Jayden Daniels questionable with a knee injury", index
    )
    assert (players, teams, topics) == (["p1"], ["WAS"], ["injury"])
    assert match_entry("Weather report for Sunday", index) == ([], [], [])


def _transport(pages: dict[str, str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        body = pages.get(request.url.host)
        return httpx.Response(200, text=body) if body else httpx.Response(503)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetching_a_feed_returns_its_entries() -> None:
    http = _transport({"a.test": FIXTURE})
    assert len(fetch_feed(http, "A", "https://a.test/rss")) == 2


def test_one_feed_down_keeps_the_others_and_repeats_are_not_stored_twice(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEWS_FEEDS", "Up|https://up.test/rss,Down|https://down.test/rss")
    session.add(_player("p1", "Jayden Daniels", "QB", "WAS"))
    session.commit()
    http = _transport({"up.test": FIXTURE})
    assert sync_news(session, http) == 2
    assert sync_news(session, http) == 0
    rows = list(session.scalars(select(NewsItemRow)))
    assert {r.source for r in rows} == {"Up"}
    assert next(r for r in rows if r.player_ids).player_ids == ["p1"]


def test_every_feed_failing_is_an_error(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEWS_FEEDS", "Down|https://down.test/rss")
    with pytest.raises(RuntimeError):
        sync_news(session, _transport({}))


def test_the_board_marks_which_teams_own_the_players_named(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEWS_FEEDS", "Up|https://up.test/rss")
    league = LeagueRow(
        league_id="L1", name="x", season="2026", total_rosters=2, scoring_settings={},
        roster_positions=[], settings={},
    )  # fmt: skip
    session.add_all(
        [
            league,
            _player("p1", "Jayden Daniels", "QB", "WAS"),
            RosterRow(league_id="L1", roster_id=2, owner_id=None, players=["p1"], starters=[]),
        ]
    )
    session.commit()
    sync_news(session, _transport({"up.test": FIXTURE}))
    view = build_news(session, league)
    assert view.sources == ["Up"]
    first = next(i for i in view.items if i.players)
    assert (first.roster_ids, first.players[0].name) == ([2], "Jayden Daniels")
    assert [i.title[:7] for i in player_news(session, "p1")] == ["Command"]


def test_a_team_name_inside_a_longer_word_is_not_a_team(session: Session) -> None:
    index = name_index(session)
    assert match_entry("Coaches praise new training programs", index) == ([], [], [])
    assert match_entry("Rams add a coach", index)[1] == ["LAR"]


def test_doctype_text_inside_an_item_is_not_a_declaration() -> None:
    xml = (
        "<rss><channel><item><title>Hello</title><link>https://x.test/1</link>"
        "<description><![CDATA[<!DOCTYPE html>]]></description></item></channel></rss>"
    )
    assert [e.title for e in parse_feed(xml, "X")] == ["Hello"]


def test_atom_prefers_the_alternate_link() -> None:
    xml = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title>'
        '<link rel="replies" href="https://x.test/comments"/>'
        '<link rel="alternate" href="https://x.test/story"/></entry></feed>'
    )
    assert parse_feed(xml, "A")[0].link == "https://x.test/story"


def test_an_oversize_feed_is_refused_while_reading() -> None:
    http = _transport({"big.test": "<rss>" + "x" * 2_100_000 + "</rss>"})
    with pytest.raises(FeedError):
        fetch_feed(http, "Big", "https://big.test/rss")


def test_an_edited_headline_is_refreshed(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEWS_FEEDS", "Up|https://up.test/rss")
    session.add(_player("p1", "Jayden Daniels", "QB", "WAS"))
    session.commit()
    sync_news(session, _transport({"up.test": FIXTURE}))
    edited = FIXTURE.replace("questionable with a knee injury", "ruled out")
    sync_news(session, _transport({"up.test": edited}))
    titles = [r.title for r in session.scalars(select(NewsItemRow))]
    assert "Commanders QB Jayden Daniels ruled out" in titles
