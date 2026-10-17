import type { NewsItem } from "./api";

const TOPIC_LABELS: Record<string, string> = {
  injury: "Injury",
  depth: "Depth chart",
  trade: "Trade",
  waivers: "Roster move",
};

/** The words for a headline's topics, in the order the feed matched them. */
export function topicLabels(topics: readonly string[]): string[] {
  return topics.flatMap((t) => (TOPIC_LABELS[t] ? [TOPIC_LABELS[t]] : []));
}

/** Why a headline matters to this viewer: it names one of their players, or their favourite team. */
export function newsFlags(
  item: NewsItem,
  myRosterId: number | null,
  favourite: string | null,
): { mine: boolean; favourite: boolean } {
  return {
    mine: myRosterId !== null && item.roster_ids.includes(myRosterId),
    favourite: favourite !== null && item.teams.includes(favourite),
  };
}

/** Your headlines first, then your favourite team's, keeping the newest-first order inside each. */
export function sortNews(
  items: readonly NewsItem[],
  myRosterId: number | null,
  favourite: string | null,
): NewsItem[] {
  const rank = (item: NewsItem) => {
    const f = newsFlags(item, myRosterId, favourite);
    return f.mine ? 0 : f.favourite ? 1 : 2;
  };
  return items
    .map((item, i) => ({ item, i }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.i - b.i)
    .map((x) => x.item);
}

/** The sources present, for the "from" note. */
export function sourceNote(sources: readonly string[]): string {
  return sources.length === 0 ? "" : `From ${sources.join(" and ")}`;
}
