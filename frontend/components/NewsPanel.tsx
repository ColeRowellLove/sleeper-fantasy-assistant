import type { NewsData } from "../lib/api";
import { sourceNote } from "../lib/news";
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
      {data.items.length === 0 ? (
        <p className="note">No headlines have been collected yet.</p>
      ) : (
        <NewsList items={data.items} myRosterId={myRosterId} label="Latest headlines" />
      )}
    </section>
  );
}
