import type { TransactionItem } from "./api";

/** The headline of a transaction card: who did what, in words. */
export function transactionTitle(item: TransactionItem): string {
  const first = item.moves[0];
  const who = first?.manager ? `@${first.manager}` : (first?.team ?? "A team");
  switch (item.kind) {
    case "waiver":
      return `${who} claimed a player off waivers`;
    case "free_agent":
      return `${who} made a roster move`;
    case "trade": {
      const teams = item.moves.map((m) => m.team);
      return teams.length >= 2 ? `${teams.join(" and ")} made a trade` : "A trade was made";
    }
    case "commissioner":
      return "The commissioner moved players";
  }
}
