import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TransactionsPanel from "../components/TransactionsPanel";
import type { TransactionItem, TransactionsData } from "../lib/api";
import { parseTab } from "../lib/league";
import { transactionTitle } from "../lib/transactions";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=transactions"),
}));

const waiver: TransactionItem = {
  transaction_id: "w",
  kind: "waiver",
  week: 6,
  created_at: "2026-10-16T12:00:00Z",
  moves: [
    {
      roster_id: 1,
      team: "Shough Around",
      manager: "colehrl",
      added: [{ player_id: "a", name: "Q. Judkins", position: "RB", team: "CLE" }],
      dropped: [{ player_id: "b", name: "Z. Charbonnet", position: "RB", team: "SEA" }],
    },
  ],
};

const trade: TransactionItem = {
  transaction_id: "t",
  kind: "trade",
  week: 6,
  created_at: null,
  moves: [
    { roster_id: 1, team: "Shough Around", added: [{ player_id: "a", name: "A" }], dropped: [] },
    { roster_id: 2, team: "Dad Bods", added: [], dropped: [{ player_id: "a", name: "A" }] },
  ],
};

const data: TransactionsData = { league_id: "1", transactions: [waiver, trade] };

describe("transactionTitle", () => {
  it("says who did what for each kind", () => {
    expect(transactionTitle(waiver)).toBe("@colehrl claimed a player off waivers");
    expect(transactionTitle({ ...waiver, kind: "free_agent" })).toBe("@colehrl made a roster move");
    expect(transactionTitle(trade)).toBe("Shough Around and Dad Bods made a trade");
    expect(transactionTitle({ ...waiver, kind: "commissioner" })).toBe(
      "The commissioner moved players",
    );
    expect(transactionTitle({ ...trade, moves: [] })).toBe("A trade was made");
  });

  it("is a page of the league", () => {
    expect(parseTab("transactions")).toBe("transactions");
  });
});

describe("TransactionsPanel", () => {
  it("shows a card per transaction with added and dropped players in words", () => {
    render(<TransactionsPanel data={data} leagueId="1" myRosterId={1} />);
    const cards = screen.getAllByRole("listitem").filter((li) => li.classList.contains("txn-card"));
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("@colehrl claimed a player off waivers")).toBeInTheDocument();
    expect(within(cards[0]).getByText("Added")).toBeInTheDocument();
    expect(within(cards[0]).getByText("Dropped")).toBeInTheDocument();
    expect(within(cards[0]).getByText("Q. Judkins")).toBeInTheDocument();
    expect(within(cards[0]).getByText("You")).toBeInTheDocument(); // your own move
    expect(within(cards[0]).getByRole("link", { name: "Shough Around" })).toHaveAttribute(
      "href",
      "/league/1?tab=rosters&roster=1",
    );
  });

  it("explains an empty board, and has no accessibility violations", async () => {
    render(
      <TransactionsPanel
        data={{ league_id: "1", transactions: [] }}
        leagueId="1"
        myRosterId={null}
      />,
    );
    expect(screen.getByText(/No adds, drops or trades/)).toBeInTheDocument();
    await expectNoA11yViolations(<TransactionsPanel data={data} leagueId="1" myRosterId={1} />);
  });
});
