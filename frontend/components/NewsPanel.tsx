"use client";

import { useState } from "react";

import type { NewsData } from "../lib/api";
import { NEWS_FILTERS, emptyNewsNote, filterNews, sourceNote, type NewsFilter } from "../lib/news";
import FilterChips from "./FilterChips";
import { useFavourite } from "./FavouriteProvider";
import NewsList from "./NewsList";
import NoteList from "./NoteList";

/** Headlines about NFL players and teams from public feeds; each one links to its source. */
export default function NewsPanel({
  data,
  myRosterId,
}: {
  data: NewsData;
  myRosterId: number | null;
}) {
  const favourite = useFavourite();
  const [filter, setFilter] = useState<NewsFilter>("all");
  const items = filterNews(data.items, filter, myRosterId, favourite);
  return (
    <section aria-labelledby="news-heading" className="news">
      <h2 id="news-heading">News</h2>
      <NoteList
        items={[
          sourceNote(data.sources) || "Headlines from public NFL feeds",
          "Only the headline is shown; the story opens at its source",
          "Your players and favourite team come first",
        ]}
      />
      <FilterChips
        label="Show news about"
        options={NEWS_FILTERS}
        value={filter}
        onChange={setFilter}
      />
      {items.length === 0 ? (
        <p className="note" role="status">
          {data.items.length === 0
            ? "No headlines have been collected yet."
            : emptyNewsNote(filter, myRosterId, favourite)}
        </p>
      ) : (
        <NewsList items={items} myRosterId={myRosterId} label="Latest headlines" />
      )}
    </section>
  );
}
