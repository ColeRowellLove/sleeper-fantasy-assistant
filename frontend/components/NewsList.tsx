"use client";

import type { NewsItem } from "../lib/api";
import { newsFlags, sortNews, topicLabels } from "../lib/news";
import { useFavourite } from "./FavouriteProvider";
import LocalTime from "./LocalTime";
import ReasonChips, { type Reason } from "./ReasonChips";

/**
 * Headlines with their source and time, each linking to the article at the source (only the
 * headline is ever kept). Ones about your players or your favourite team come first and say so.
 */
export default function NewsList({
  items,
  myRosterId,
  label,
}: {
  items: readonly NewsItem[];
  myRosterId: number | null;
  label: string;
}) {
  const favourite = useFavourite();
  return (
    <ul className="news-list" aria-label={label}>
      {sortNews(items, myRosterId, favourite).map((item) => {
        const flags = newsFlags(item, myRosterId, favourite);
        const reasons: Reason[] = [
          ...(flags.mine ? [{ label: "Your player", stance: "info" as const }] : []),
          ...(flags.favourite ? [{ label: "Your favourite team", stance: "info" as const }] : []),
          ...topicLabels(item.topics).map((t) => ({ label: t })),
        ];
        return (
          <li key={item.id} className="news-item">
            <a href={item.link} target="_blank" rel="noopener noreferrer" className="news-title">
              {item.title}
              <span className="visually-hidden"> (opens {item.source} in a new tab)</span>
            </a>
            <p className="news-meta muted">
              <strong>{item.source}</strong>
              {item.published_at && (
                <>
                  {" · "}
                  <LocalTime iso={item.published_at} />
                </>
              )}
            </p>
            <ReasonChips reasons={reasons} label="Why it matters" />
          </li>
        );
      })}
    </ul>
  );
}
