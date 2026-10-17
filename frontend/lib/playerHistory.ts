import type { PlayerDetail } from "./api";

type Event = NonNullable<PlayerDetail["history"]>[number];

export interface HistoryRow {
  key: string;
  /** "Added" or "Dropped". */
  move: string;
  /** "from Waivers by cole". */
  text: string;
  /** "Oct 10, 2026", or a dash without a date. */
  date: string;
}

const ADDED: Record<Event["source"], string> = {
  waivers: "from Waivers",
  free_agency: "from Free agency",
  trade: "in a trade to",
  commissioner: "by the commissioner to",
};

const DROPPED: Record<Event["source"], string> = {
  waivers: "to Waivers",
  free_agency: "to Free agency",
  trade: "in a trade from",
  commissioner: "by the commissioner from",
};

/** "Oct 10, 2026" from an ISO date. UTC, so server and browser agree. */
export function historyDate(date: string | null | undefined): string {
  if (!date) return "–";
  const parsed = new Date(`${date}T12:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return "–";
  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** The transaction list as rows of words: "Added | from Waivers by cole | Oct 10, 2026". */
export function historyRows(history: PlayerDetail["history"]): HistoryRow[] {
  return (history ?? []).map((e, i) => {
    const how = (e.kind === "added" ? ADDED : DROPPED)[e.source];
    const by = e.source === "trade" || e.source === "commissioner" ? " " : " by ";
    const bare = e.source === "trade" ? "in a trade" : how;
    return {
      key: `${i}-${e.date ?? ""}-${e.kind}`,
      move: e.kind === "added" ? "Added" : "Dropped",
      text: e.manager ? `${how}${by}${e.manager}` : bare,
      date: historyDate(e.date),
    };
  });
}
